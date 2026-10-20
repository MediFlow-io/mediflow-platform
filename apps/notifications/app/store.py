"""All SQL. This service is the only writer of notifications_notification and notifications_delivery
(ADR-0002); the tables are created by the core API's migrations. Everything else is read-only here."""
from zoneinfo import ZoneInfo

from psycopg import Connection
from psycopg.rows import dict_row

from . import channels
from .rules import Facts, Note, plan

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


# --- Event side -------------------------------------------------------------------------------------------

def _head_of_queue(cur, department_id: int, f: Facts) -> None:
    # Same order as the queue in patient-flow: triage level, then arrival.
    cur.execute("""SELECT v.id, p.user_id FROM patients_visit v JOIN patients_patient p ON p.id = v.patient_id
                   WHERE v.department_id = %s AND v.status = 'waiting'
                   ORDER BY v.esi, v.checked_in_at, v.id LIMIT 1""", (department_id,))
    if row := cur.fetchone():
        f.next_visit, f.next_user = row["id"], row["user_id"]


def load_facts(conn: Connection, event: dict, tz: ZoneInfo) -> Facts | None:
    """None when the row is gone (nothing to say)."""
    f = Facts()
    with conn.cursor(row_factory=dict_row) as cur:
        if appointment_id := event.get("appointmentId"):
            cur.execute("""SELECT a.id, a.scheduled_for, a.staff_note, a.visit_id, a.department_id, d.name AS department,
                                  p.user_id, p.full_name
                           FROM patients_appointment a JOIN patients_department d ON d.id = a.department_id
                           JOIN patients_patient p ON p.id = a.patient_id WHERE a.id = %s""", (appointment_id,))
            row = cur.fetchone()
            if not row:
                return None
            f.appointment_id, f.visit_id, f.staff_note = row["id"], row["visit_id"], row["staff_note"]
            f.scheduled_for = row["scheduled_for"].astimezone(tz)
            entity, entity_id = "appointment", appointment_id
        elif visit_id := event.get("visitId"):
            cur.execute("""SELECT v.id, v.department_id, d.name AS department, p.user_id, p.full_name
                           FROM patients_visit v JOIN patients_department d ON d.id = v.department_id
                           JOIN patients_patient p ON p.id = v.patient_id WHERE v.id = %s""", (visit_id,))
            row = cur.fetchone()
            if not row:
                return None
            f.visit_id = row["id"]
            entity, entity_id = "visit", visit_id
        else:
            return None
        f.department, f.patient_user, f.patient_name = row["department"], row["user_id"], row["full_name"]

        cur.execute("""SELECT actor_id FROM operations_auditlog WHERE entity_type = %s AND entity_id = %s AND action = %s
                       ORDER BY id DESC LIMIT 1""", (entity, str(entity_id), event.get("action", "")))
        if audit := cur.fetchone():
            f.actor = audit["actor_id"]
        if event.get("action") in ("appointment.requested", "appointment.cancel"):
            cur.execute("SELECT id FROM accounts_user WHERE is_active AND role = ANY(%s) ORDER BY id", (list(FRONT_DESK),))
            f.front_desk = [r["id"] for r in cur.fetchall()]
        if f.visit_id:
            _head_of_queue(cur, row["department_id"], f)
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


def _deliver(conn: Connection, notification_id: int, user_id: int, senders: list) -> None:
    contact = conn.execute("""SELECT u.email, coalesce((SELECT phone FROM patients_patient WHERE user_id = u.id LIMIT 1), '')
                              FROM accounts_user u WHERE u.id = %s""", (user_id,)).fetchone()
    contact = channels.Contact(email=contact[0] if contact else "", phone=contact[1] if contact else "")
    for sender in senders:
        status, detail = channels.deliver(sender, contact)
        conn.execute("""INSERT INTO notifications_delivery (notification_id, channel, status, detail, created_at)
                        VALUES (%s, %s, %s, %s, now())""", (notification_id, sender.name, status, detail))


def handle_event(conn: Connection, event: dict, tz: ZoneInfo, senders: list | None = None) -> list[int]:
    """One event → its notifications, in one transaction. Returns the ids created."""
    with conn.transaction():
        facts = load_facts(conn, event, tz)
        if facts is None:
            return []
        return save(conn, plan(event, facts), senders or [])
