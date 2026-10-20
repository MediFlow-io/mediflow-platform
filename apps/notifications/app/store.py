"""All SQL. This service is the only writer of notifications_notification and notifications_delivery
(ADR-0002); the tables are created by the core API's migrations. Everything else is read-only here."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg import Connection
from psycopg.rows import dict_row

from . import channels
from .rules import URGENT_ESI, DueAppointment, Facts, LongWait, Note, delay_notes, plan, reminder_notes

FRONT_DESK = ("admin", "doctor", "nurse", "reception")  # mirrors CanManageAppointments in patient-flow

COLUMNS = "id, kind, title, body, link, created_at, read_at"


def as_json(row: dict) -> dict:
    return {
        "id": row["id"], "kind": row["kind"], "title": row["title"], "body": row["body"], "link": row["link"],
        "createdAt": row["created_at"].isoformat(), "readAt": row["read_at"].isoformat() if row["read_at"] else None,
    }


# --- API side ---------------------------------------------------------------------------------------------

def active_user(conn: Connection, user_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, role, is_active FROM accounts_user WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return row if row and row["is_active"] else None


def list_for(conn: Connection, user_id: int, *, unread_only: bool, limit: int, before: int | None) -> list[dict]:
    sql = f"SELECT {COLUMNS} FROM notifications_notification WHERE recipient_id = %s"
    args: list = [user_id]
    if unread_only:
        sql += " AND read_at IS NULL"
    if before:
        sql += " AND id < %s"
        args.append(before)
    sql += " ORDER BY id DESC LIMIT %s"
    args.append(limit)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, args)
        return [as_json(r) for r in cur.fetchall()]


def unread_count(conn: Connection, user_id: int) -> int:
    row = conn.execute("SELECT count(*) FROM notifications_notification WHERE recipient_id = %s AND read_at IS NULL",
                       (user_id,)).fetchone()
    return row[0]


def mark_read(conn: Connection, user_id: int, notification_id: int) -> bool:
    """False if it isn't this user's (so nobody can probe other people's ids)."""
    row = conn.execute("""UPDATE notifications_notification SET read_at = coalesce(read_at, now())
                          WHERE id = %s AND recipient_id = %s RETURNING id""", (notification_id, user_id)).fetchone()
    return row is not None


def mark_all_read(conn: Connection, user_id: int) -> int:
    cur = conn.execute("UPDATE notifications_notification SET read_at = now() WHERE recipient_id = %s AND read_at IS NULL",
                       (user_id,))
    return cur.rowcount


# --- Settings and preferences -----------------------------------------------------------------------------

@dataclass(frozen=True)
class QueueSettings:
    turn_near_ahead: int = 2
    long_wait_minutes: int = 60


def queue_settings(cur) -> QueueSettings:
    """clinic_queuesettings (edited from the admin console), or the defaults."""
    cur.execute("SELECT turn_near_ahead, long_wait_minutes FROM clinic_queuesettings WHERE id = 1")
    row = cur.fetchone()
    if not row:
        return QueueSettings()
    values = list(row.values()) if isinstance(row, dict) else list(row)
    return QueueSettings(*values)


def preferences(conn: Connection, user_id: int) -> dict:
    row = conn.execute("SELECT email, sms FROM notifications_preference WHERE user_id = %s", (user_id,)).fetchone()
    return {"email": row[0], "sms": row[1]} if row else {"email": True, "sms": True}


def set_preferences(conn: Connection, user_id: int, changes: dict) -> dict:
    current = {**preferences(conn, user_id), **changes}
    conn.execute("""INSERT INTO notifications_preference (user_id, email, sms, updated_at) VALUES (%s, %s, %s, now())
                    ON CONFLICT (user_id) DO UPDATE SET email = EXCLUDED.email, sms = EXCLUDED.sms, updated_at = now()""",
                 (user_id, current["email"], current["sms"]))
    return current


# --- Event side -------------------------------------------------------------------------------------------

def _queue_front(cur, department_id: int, near: int, f: Facts) -> None:
    # Same order as the queue in patient-flow: triage level, then arrival.
    cur.execute("""SELECT v.id, p.user_id FROM patients_visit v JOIN patients_patient p ON p.id = v.patient_id
                   WHERE v.department_id = %s AND v.status = 'waiting'
                   ORDER BY v.esi, v.checked_in_at, v.id LIMIT %s""", (department_id, near + 1))
    rows = cur.fetchall()
    if rows:
        f.next_visit, f.next_user = rows[0]["id"], rows[0]["user_id"]
    f.near = [(r["id"], r["user_id"], ahead) for ahead, r in enumerate(rows[1:], start=1)]


def _urgent_staff(cur, department_id: int, now: datetime) -> list[int]:
    """Doctors and nurses rostered for the department now; if nobody is rostered, every active one."""
    cur.execute("""SELECT DISTINCT u.id FROM clinic_staffshift s JOIN accounts_user u ON u.id = s.user_id
                   WHERE s.department_id = %s AND u.is_active AND u.role IN ('doctor', 'nurse')
                     AND s.weekday = %s AND s.starts <= %s AND s.ends > %s ORDER BY u.id""",
                (department_id, now.isoweekday() % 7, now.time(), now.time()))
    staff = [r["id"] for r in cur.fetchall()]
    if staff:
        return staff
    cur.execute("SELECT id FROM accounts_user WHERE is_active AND role IN ('doctor', 'nurse') ORDER BY id")
    return [r["id"] for r in cur.fetchall()]


def load_facts(conn: Connection, event: dict, tz: ZoneInfo) -> Facts | None:
    """None when the row is gone (nothing to say)."""
    f = Facts()
    action = event.get("action", "")
    with conn.cursor(row_factory=dict_row) as cur:
        if appointment_id := event.get("appointmentId"):
            cur.execute("""SELECT a.id, a.scheduled_for, a.staff_note, a.visit_id, a.department_id, d.name AS department,
                                  p.user_id, p.full_name, v.esi
                           FROM patients_appointment a JOIN patients_department d ON d.id = a.department_id
                           JOIN patients_patient p ON p.id = a.patient_id
                           LEFT JOIN patients_visit v ON v.id = a.visit_id WHERE a.id = %s""", (appointment_id,))
            row = cur.fetchone()
            if not row:
                return None
            f.appointment_id, f.visit_id, f.staff_note = row["id"], row["visit_id"], row["staff_note"]
            f.scheduled_for = row["scheduled_for"].astimezone(tz)
            entity, entity_id = "appointment", appointment_id
        elif visit_id := event.get("visitId"):
            cur.execute("""SELECT v.id, v.department_id, v.esi, d.name AS department, p.user_id, p.full_name
                           FROM patients_visit v JOIN patients_department d ON d.id = v.department_id
                           JOIN patients_patient p ON p.id = v.patient_id WHERE v.id = %s""", (visit_id,))
            row = cur.fetchone()
            if not row:
                return None
            f.visit_id = row["id"]
            entity, entity_id = "visit", visit_id
        else:
            return None
        f.department, f.patient_user, f.patient_name, f.esi = row["department"], row["user_id"], row["full_name"], row["esi"]

        audit_action = "visit.triage_changed" if action == "triage" else action
        cur.execute("""SELECT actor_id FROM operations_auditlog WHERE entity_type = %s AND entity_id = %s AND action = %s
                       ORDER BY id DESC LIMIT 1""", (entity, str(entity_id), audit_action))
        if audit := cur.fetchone():
            f.actor = audit["actor_id"]
        if action in ("appointment.requested", "appointment.cancel"):
            cur.execute("SELECT id FROM accounts_user WHERE is_active AND role = ANY(%s) ORDER BY id", (list(FRONT_DESK),))
            f.front_desk = [r["id"] for r in cur.fetchall()]
        if action == "triage" and f.visit_id:
            cur.execute("""SELECT from_esi FROM patients_triagechange WHERE visit_id = %s
                           ORDER BY changed_at DESC, id DESC LIMIT 1""", (f.visit_id,))
            if change := cur.fetchone():
                f.previous_esi = change["from_esi"]
        if f.visit_id and f.esi is not None and f.esi <= URGENT_ESI:
            f.urgent_staff = _urgent_staff(cur, row["department_id"], datetime.now(tz))
        if f.visit_id:
            _queue_front(cur, row["department_id"], queue_settings(cur).turn_near_ahead, f)
    return f


def save(conn: Connection, notes: list[Note], senders: list) -> list[int]:
    """Inserts the notifications that don't exist yet, then sends them on the extra channels."""
    created = []
    for n in notes:
        row = conn.execute("""INSERT INTO notifications_notification
                                  (recipient_id, kind, title, body, link, dedupe_key, created_at)
                              VALUES (%s, %s, %s, %s, %s, %s, now())
                              ON CONFLICT (dedupe_key) DO NOTHING RETURNING id""",
                           (n.recipient, n.kind, n.title, n.body, n.link, n.dedupe_key)).fetchone()
        if row:
            created.append(row[0])
            if senders:
                _deliver(conn, row[0], n.recipient, senders)
    return created


MAX_ATTEMPTS = 3


def _contact(conn: Connection, user_id: int) -> channels.Contact:
    row = conn.execute("""SELECT u.email, coalesce((SELECT phone FROM patients_patient WHERE user_id = u.id LIMIT 1), '')
                          FROM accounts_user u WHERE u.id = %s""", (user_id,)).fetchone()
    return channels.Contact(email=row[0] if row else "", phone=row[1] if row else "")


def _retry_at(status: str, attempts: int):
    """Failed deliveries are retried after 2, then 4 minutes; then we give up (None)."""
    if status != "failed" or attempts >= MAX_ATTEMPTS:
        return None
    return timedelta(minutes=2 ** attempts)


def _deliver(conn: Connection, notification_id: int, user_id: int, senders: list) -> None:
    contact, wanted = _contact(conn, user_id), preferences(conn, user_id)
    for sender in senders:
        if not wanted.get(sender.name, True):
            status, detail = "skipped", "turned off by the user"
        else:
            status, detail = channels.deliver(sender, contact)
        backoff = _retry_at(status, 1)
        conn.execute("""INSERT INTO notifications_delivery (notification_id, channel, status, detail, created_at, attempts, next_attempt_at)
                        VALUES (%s, %s, %s, %s, now(), 1, now() + %s)""",
                     (notification_id, sender.name, status, detail, backoff))


def handle_event(conn: Connection, event: dict, tz: ZoneInfo, senders: list | None = None) -> list[int]:
    """One event → its notifications, in one transaction. Returns the ids created."""
    with conn.transaction():
        facts = load_facts(conn, event, tz)
        if facts is None:
            return []
        return save(conn, plan(event, facts), senders or [])


# --- Scheduled jobs (app/scheduler.py runs these every minute) ---------------------------------------------

def due_reminders(conn: Connection, tz: ZoneInfo) -> list[DueAppointment]:
    """Confirmed appointments about a day away, or within the hour, for patients with an account."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT a.id, p.user_id, d.name AS department, a.scheduled_for,
                              CASE WHEN a.scheduled_for <= now() + interval '1 hour' THEN 'hour' ELSE 'day' END AS window
                       FROM patients_appointment a JOIN patients_patient p ON p.id = a.patient_id
                       JOIN patients_department d ON d.id = a.department_id
                       WHERE a.status = 'confirmed' AND p.user_id IS NOT NULL AND (
                             a.scheduled_for > now() AND a.scheduled_for <= now() + interval '1 hour'
                          OR a.scheduled_for > now() + interval '23 hours' AND a.scheduled_for <= now() + interval '24 hours')""")
        return [DueAppointment(r["id"], r["user_id"], r["department"], r["scheduled_for"].astimezone(tz), r["window"])
                for r in cur.fetchall()]


def long_waits(conn: Connection) -> list[LongWait]:
    """Patients with an account who have waited longer than the clinic's long-wait threshold today."""
    with conn.cursor(row_factory=dict_row) as cur:
        threshold = queue_settings(cur).long_wait_minutes
        if threshold <= 0:
            return []
        cur.execute("""SELECT v.id, p.user_id, d.name AS department,
                              floor(extract(epoch FROM now() - v.checked_in_at) / 60)::int AS waited
                       FROM patients_visit v JOIN patients_patient p ON p.id = v.patient_id
                       JOIN patients_department d ON d.id = v.department_id
                       WHERE v.status = 'waiting' AND p.user_id IS NOT NULL
                         AND v.checked_in_at < now() - make_interval(mins => %s)
                         AND v.checked_in_at > now() - interval '24 hours'""", (threshold,))
        return [LongWait(r["id"], r["user_id"], r["department"], r["waited"]) for r in cur.fetchall()]


def retry_failed(conn: Connection, senders: list) -> int:
    """Retries failed email/SMS deliveries that are due. Returns how many were attempted."""
    by_name = {s.name: s for s in senders}
    attempted = 0
    with conn.transaction():
        rows = conn.execute("""SELECT d.id, d.channel, d.attempts, n.recipient_id FROM notifications_delivery d
                               JOIN notifications_notification n ON n.id = d.notification_id
                               WHERE d.status = 'failed' AND d.next_attempt_at <= now()
                               ORDER BY d.next_attempt_at LIMIT 50 FOR UPDATE OF d SKIP LOCKED""").fetchall()
        for delivery_id, channel, attempts, user_id in rows:
            sender = by_name.get(channel)
            if sender is None:  # channel switched off since: stop retrying
                conn.execute("UPDATE notifications_delivery SET next_attempt_at = NULL WHERE id = %s", (delivery_id,))
                continue
            status, detail = channels.deliver(sender, _contact(conn, user_id))
            attempts += 1
            conn.execute("""UPDATE notifications_delivery SET status = %s, detail = %s, attempts = %s,
                                   next_attempt_at = now() + %s WHERE id = %s""",
                         (status, detail, attempts, _retry_at(status, attempts), delivery_id))
            attempted += 1
    return attempted


def run_scheduled(conn: Connection, tz: ZoneInfo, senders: list) -> dict:
    """One pass of every scheduled job. Each notification's dedupe key makes repeats harmless."""
    with conn.transaction():
        reminders = save(conn, reminder_notes(due_reminders(conn, tz)), senders)
    with conn.transaction():
        delays = save(conn, delay_notes(long_waits(conn)), senders)
    return {"reminders": len(reminders), "delays": len(delays), "retried": retry_failed(conn, senders)}
