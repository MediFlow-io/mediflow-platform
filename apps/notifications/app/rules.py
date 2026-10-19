"""Which notifications an event or a scheduled check produces. Pure functions: no database, easy to test.

The patient-flow service publishes events on the PostgreSQL channel `mediflow_visits` (see
apps/patient-flow/internal/store). The listener loads the facts an event refers to into a `Facts` and
asks `plan()` what to send. The scheduler (app/scheduler.py) asks `reminder_notes()` and `delay_notes()`.

This module is the one place for notification wording. Text for patients never includes clinical
details (complaint, vitals, triage level): only where and when. Staff alerts may name the ESI level,
which staff see on the queue anyway, but never the patient's complaint.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Note:
    recipient: int
    kind: str
    title: str
    body: str
    link: str
    # Unique per notification: the same event handled twice produces it once.
    dedupe_key: str


@dataclass
class Facts:
    department: str = ""                  # display name
    patient_user: int | None = None       # account linked to the patient record, if any
    patient_name: str = ""
    visit_id: int | None = None
    appointment_id: int | None = None
    scheduled_for: datetime | None = None  # already in the clinic's time zone
    staff_note: str = ""
    actor: int | None = None              # who made the change (from the audit log)
    front_desk: list[int] = field(default_factory=list)  # staff who handle appointment requests
    # After the change: the first waiting visit in the department's queue, and its patient's account.
    next_visit: int | None = None
    next_user: int | None = None
    # The next few behind them: (visit, account or None, people ahead), for "your turn is near".
    near: list[tuple[int, int | None, int]] = field(default_factory=list)
    esi: int | None = None                # the visit's triage level now
    previous_esi: int | None = None       # before a triage change
    urgent_staff: list[int] = field(default_factory=list)  # clinicians to alert about ESI 1–2


URGENT_ESI = 2  # ESI 1 and 2 page the clinicians


def when(dt: datetime | None) -> str:
    return dt.strftime("%a %d %b, %H:%M") if dt else "a time to be confirmed"


def people(n: int) -> str:
    return f"{n} {'person is' if n == 1 else 'people are'}"


def plan(event: dict, f: Facts) -> list[Note]:
    action = event.get("action", "")
    notes: list[Note] = []

    def to_patient(kind, title, body, link, key):
        if f.patient_user:
            notes.append(Note(f.patient_user, kind, title, body, link, f"{f.patient_user}:{key}"))

    visit, appt = f.visit_id, f.appointment_id
    if action == "call":
        to_patient("visit.called", "You've been called", f"Please go to {f.department} now.", "home",
                   f"visit:{visit}:called")
    elif action in ("checked_in", "appointment.check_in"):
        to_patient("visit.checked_in", "You're checked in", f"You're in the queue for {f.department}.", "home",
                   f"visit:{visit}:checked_in")
    elif action == "cancel":
        to_patient("visit.cancelled", "Visit cancelled",
                   f"Your visit to {f.department} was cancelled. Ask at the front desk if this is unexpected.", "home",
                   f"visit:{visit}:cancelled")
    elif action == "appointment.booked":
        to_patient("appointment.booked", "Appointment booked", f"{f.department}, {when(f.scheduled_for)}.",
                   "appointments", f"appt:{appt}:booked")
    elif action == "appointment.confirm":
        body = f"{f.department}, {when(f.scheduled_for)}."
        if f.staff_note:
            body += f" Note from the clinic: {f.staff_note}"
        to_patient("appointment.confirmed", "Appointment confirmed", body, "appointments", f"appt:{appt}:confirmed")
    elif action == "appointment.decline":
        body = f"The clinic couldn't take your {f.department} request for {when(f.scheduled_for)}."
        if f.staff_note:
            body += f" Note from the clinic: {f.staff_note}"
        to_patient("appointment.declined", "Appointment request declined", body, "appointments",
                   f"appt:{appt}:declined")
    elif action == "appointment.cancel":
        if f.actor is not None and f.actor == f.patient_user:
            # The patient cancelled: tell the front desk, not the patient.
            for staff in f.front_desk:
                notes.append(Note(staff, "appointment.cancelled", "Appointment cancelled",
                                  f"{f.patient_name} cancelled their {f.department} appointment for {when(f.scheduled_for)}.",
                                  "appointments", f"{staff}:appt:{appt}:cancelled"))
        else:
            to_patient("appointment.cancelled", "Appointment cancelled",
                       f"The clinic cancelled your {f.department} appointment for {when(f.scheduled_for)}.",
                       "appointments", f"appt:{appt}:cancelled")
    elif action == "appointment.requested":
        for staff in f.front_desk:
            if staff == f.actor:
                continue
            notes.append(Note(staff, "appointment.requested", "New appointment request",
                              f"{f.patient_name} asked for {f.department} on {when(f.scheduled_for)}.",
                              "appointments", f"{staff}:appt:{appt}:requested"))

    # An urgent patient arriving, or being escalated to ESI 1–2, pages the clinicians.
    arrived = action in ("checked_in", "appointment.check_in")
    escalated = action == "triage" and f.previous_esi is not None and f.esi is not None and f.esi < f.previous_esi
    if visit and f.esi is not None and f.esi <= URGENT_ESI and (arrived or escalated):
        for staff in f.urgent_staff:
            if staff == f.actor:
                continue
            notes.append(Note(staff, "visit.urgent", "Urgent patient waiting",
                              f"An ESI {f.esi} patient is waiting in {f.department}. Check the queue.", "queue",
                              f"{staff}:visit:{visit}:urgent:{f.esi}"))

    # Any queue change can move someone to the front, or close to it. Tell each person once per visit.
    if f.next_visit and f.next_user:
        notes.append(Note(f.next_user, "visit.next", "You're next",
                          f"You're first in the queue for {f.department}. Please stay close.", "home",
                          f"{f.next_user}:visit:{f.next_visit}:next"))
    for near_visit, user, ahead in f.near:
        if user:
            notes.append(Note(user, "visit.near", "Your turn is near",
                              f"{people(ahead)} ahead of you in {f.department}. Please make your way back if you stepped out.",
                              "home", f"{user}:visit:{near_visit}:near"))
    return notes


# --- Scheduled checks -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class DueAppointment:
    id: int
    user: int
    department: str
    scheduled_for: datetime  # clinic time zone
    window: str              # "day" (about 24 h before) or "hour" (within the hour)


def reminder_notes(due: list[DueAppointment]) -> list[Note]:
    notes = []
    for a in due:
        if a.window == "day":
            title, body = "Appointment tomorrow", f"Reminder: {a.department}, {when(a.scheduled_for)}."
        else:
            title, body = "Appointment soon", f"Your {a.department} appointment is at {a.scheduled_for:%H:%M}. Please arrive a few minutes early."
        notes.append(Note(a.user, "appointment.reminder", title, body + " Cancel in the app if you can't make it.",
                          "appointments", f"{a.user}:appt:{a.id}:remind:{a.window}"))
    return notes


@dataclass(frozen=True)
class LongWait:
    visit: int
    user: int
    department: str
    waited_minutes: int


def delay_notes(waits: list[LongWait]) -> list[Note]:
    return [Note(w.user, "visit.delay", "Sorry for the wait",
                 f"You've waited about {w.waited_minutes} min in {w.department}. More urgent patients are seen first, "
                 "but you haven't been forgotten. Tell the front desk straight away if you feel worse.",
                 "home", f"{w.user}:visit:{w.visit}:delay")
            for w in waits]
