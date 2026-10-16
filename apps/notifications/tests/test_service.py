"""Against a real PostgreSQL with the core API's migrations applied. Skipped without TEST_DATABASE_URL.

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/mediflow_test pytest
"""
import json
import os
import threading
import time
from zoneinfo import ZoneInfo

import psycopg
import pytest

from app import create_app, listener, store
from app.auth import AuthError
from app.channels import LogEmail
from app.config import Settings

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")
LAGOS = ZoneInfo("Africa/Lagos")


class TokenIsUserId:
    """Stands in for the JWKS check: 'Bearer 7' is user 7."""
    def verify(self, header):
        try:
            return int((header or "").removeprefix("Bearer "))
        except ValueError:
            raise AuthError("Authentication credentials were not provided.") from None


@pytest.fixture
def db():
    with psycopg.connect(DSN, autocommit=True) as conn:
        try:
            conn.execute("""TRUNCATE notifications_delivery, notifications_notification, operations_auditlog,
                patients_appointment, patients_visit, patients_patient, patients_department, accounts_user
                RESTART IDENTITY CASCADE""")
        except psycopg.errors.UndefinedTable:
            pytest.fail("schema missing: run the core API migrations on the test database first")
        yield Fixture(conn)


class Fixture:
    def __init__(self, conn):
        self.conn = conn
        self.nurse = self.user("nurse", "nurse")
        self.reception = self.user("reception", "reception")
        self.lab = self.user("lab", "lab")
        self.ada_user = self.user("ada", "student", email="ada@example.com")
        self.ada = self.patient("Ada Obi", self.ada_user)
        self.bola = self.patient("Bola Ade", self.user("bola", "student"))
        self.opd = self.one("INSERT INTO patients_department (name, code, active) VALUES ('Outpatient', 'opd', true) RETURNING id")

    def one(self, sql, args=()):
        return self.conn.execute(sql, args).fetchone()[0]

    def user(self, name, role, email=""):
        return self.one("""INSERT INTO accounts_user (password, is_superuser, username, first_name, last_name, email,
            is_staff, is_active, date_joined, role, display_name) VALUES ('!', false, %s, '', '', %s, false, true, now(), %s, %s)
            RETURNING id""", (name, email, role, name.title()))

    def patient(self, name, user_id):
        return self.one("""INSERT INTO patients_patient (hospital_number, full_name, sex, phone, address, next_of_kin,
            next_of_kin_phone, allergies, medical_history, complaint, diagnosis, treatment, notes, created_at, updated_at, user_id)
            VALUES (%s, %s, 'Female', '0800', '', '', '', '', '', '', '', '', '', now(), now(), %s) RETURNING id""",
                        (f"MF-{name[:3]}", name, user_id))

    def visit(self, patient, esi, status="waiting"):
        return self.one("""INSERT INTO patients_visit (visit_number, esi, status, arrival_mode, checked_in_at, department_id,
            patient_id, avpu, chief_complaint) VALUES (gen_random_uuid()::text, %s, %s, 'walk_in', now(), %s, %s, 'A', 'private')
            RETURNING id""", (esi, status, self.opd, patient))

    def appointment(self, patient, actor, status="requested"):
        appt = self.one("""INSERT INTO patients_appointment (reference, patient_id, department_id, scheduled_for, reason, status,
            staff_note, requested_by_id, created_at, updated_at)
            VALUES ('A-1', %s, %s, '2026-10-20 08:30+00', 'private reason', %s, 'Bring your card', %s, now(), now()) RETURNING id""",
                        (patient, self.opd, status, actor))
        return appt

    def audit(self, actor, action, entity, entity_id):
        self.conn.execute("""INSERT INTO operations_auditlog (action, entity_type, entity_id, details, created_at, actor_id)
            VALUES (%s, %s, %s, '{}', now(), %s)""", (action, entity, str(entity_id), actor))

    def inbox(self, user_id):
        return [r[0] for r in self.conn.execute(
            "SELECT title FROM notifications_notification WHERE recipient_id = %s ORDER BY id", (user_id,))]


def test_call_notifies_patient_and_next_in_line_once(db):
    called = db.visit(db.ada, esi=3, status="called")
    db.visit(db.bola, esi=4)
    event = {"visitId": called, "action": "call", "status": "called", "department": "opd"}
    assert len(store.handle_event(db.conn, event, LAGOS)) == 2
    assert store.handle_event(db.conn, event, LAGOS) == []  # same event again: nothing new
    assert db.inbox(db.ada_user) == ["You've been called"]
    body = db.conn.execute("SELECT body FROM notifications_notification WHERE kind = 'visit.called'").fetchone()[0]
    assert "private" not in body


def test_appointment_request_reaches_front_desk_only(db):
    appt = db.appointment(db.ada, db.ada_user)
    db.audit(db.ada_user, "appointment.requested", "appointment", appt)
    store.handle_event(db.conn, {"appointmentId": appt, "action": "appointment.requested"}, LAGOS)
    assert db.inbox(db.nurse) == ["New appointment request"] == db.inbox(db.reception)
    assert db.inbox(db.lab) == [] and db.inbox(db.ada_user) == []
    body = db.conn.execute("SELECT body FROM notifications_notification LIMIT 1").fetchone()[0]
    assert body == "Ada Obi asked for Outpatient on Tue 20 Oct, 09:30."  # stored UTC, shown in clinic time


def test_confirmation_is_delivered_on_extra_channels(db):
    appt = db.appointment(db.ada, db.ada_user, status="confirmed")
    db.audit(db.nurse, "appointment.confirm", "appointment", appt)
    [nid] = store.handle_event(db.conn, {"appointmentId": appt, "action": "appointment.confirm"}, LAGOS, [LogEmail()])
    assert db.inbox(db.ada_user) == ["Appointment confirmed"]
    assert db.conn.execute("SELECT channel, status FROM notifications_delivery WHERE notification_id = %s",
                           (nid,)).fetchall() == [("email", "sent")]


def test_api_lists_and_marks_read_only_own_notifications(db):
    called = db.visit(db.ada, esi=3, status="called")
    store.handle_event(db.conn, {"visitId": called, "action": "call"}, LAGOS)
    other = db.visit(db.bola, esi=3, status="called")
    store.handle_event(db.conn, {"visitId": other, "action": "call"}, LAGOS)

    app = create_app(Settings(database_url=DSN, listen=False), verifier=TokenIsUserId())
    client = app.test_client()
    auth = {"Authorization": f"Bearer {db.ada_user}"}

    assert client.get("/api/notifications").status_code == 401
    res = client.get("/api/notifications", headers=auth).get_json()
    assert res["unread"] == 1 and [n["title"] for n in res["results"]] == ["You've been called"]
    mine = res["results"][0]["id"]
    bolas = db.one("SELECT id FROM notifications_notification WHERE recipient_id <> %s", (db.ada_user,))

    assert client.post(f"/api/notifications/{bolas}/read", headers=auth).status_code == 404
    assert client.post(f"/api/notifications/{mine}/read", headers=auth).get_json() == {"unread": 0}
    assert client.get("/api/notifications?unread=1", headers=auth).get_json()["results"] == []
    assert client.get("/api/notifications?limit=x", headers=auth).status_code == 400

    db.conn.execute("UPDATE accounts_user SET is_active = false WHERE id = %s", (db.ada_user,))
    assert client.get("/api/notifications/unread-count", headers=auth).status_code == 401
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_listener_turns_live_events_into_notifications(db):
    called = db.visit(db.ada, esi=3, status="called")
    stop = threading.Event()
    thread = threading.Thread(target=listener.run, args=(DSN, LAGOS, [], stop), daemon=True)
    thread.start()
    try:
        deadline = time.time() + 10
        while time.time() < deadline and not db.inbox(db.ada_user):
            db.conn.execute("SELECT pg_notify('mediflow_visits', %s)", (json.dumps({"visitId": called, "action": "call"}),))
            time.sleep(0.3)
        assert db.inbox(db.ada_user) == ["You've been called"]
    finally:
        stop.set()
        thread.join(timeout=10)
