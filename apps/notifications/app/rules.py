"""Which notifications an event produces. Pure functions: no database, easy to test.

The patient-flow service publishes events on the PostgreSQL channel `mediflow_visits` (see
apps/patient-flow/internal/store). The listener loads the facts an event refers to into a `Facts` and
asks `plan()` what to send.

Notification text never includes clinical details (complaint, vitals, triage level): only where and when.
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


def when(dt: datetime | None) -> str:
    return dt.strftime("%a %d %b, %H:%M") if dt else "a time to be confirmed"


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

    # Any queue change can move someone to the front. Tell them once per visit.
    if f.next_visit and f.next_user:
        notes.append(Note(f.next_user, "visit.next", "You're next",
                          f"You're first in the queue for {f.department}. Please stay close.", "home",
                          f"{f.next_user}:visit:{f.next_visit}:next"))
    return notes
