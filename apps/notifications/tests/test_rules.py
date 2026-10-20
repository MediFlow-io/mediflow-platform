from datetime import datetime
from zoneinfo import ZoneInfo

from app import channels
from app.rules import Facts, plan

LAGOS = ZoneInfo("Africa/Lagos")
WHEN = datetime(2026, 10, 20, 9, 30, tzinfo=LAGOS)


def facts(**kw):
    base = dict(department="Outpatient", patient_user=7, patient_name="Ada Obi", visit_id=11, front_desk=[2, 3])
    return Facts(**{**base, **kw})


def kinds(notes):
    return [(n.recipient, n.kind) for n in notes]


def test_call_tells_the_patient_where_to_go():
    [n] = plan({"action": "call", "visitId": 11}, facts())
    assert (n.recipient, n.kind, n.title) == (7, "visit.called", "You've been called")
    assert n.body == "Please go to Outpatient now."
    assert n.dedupe_key == "7:visit:11:called"


def test_unlinked_patient_gets_nothing():
    assert plan({"action": "call"}, facts(patient_user=None)) == []


def test_the_new_head_of_the_queue_hears_they_are_next():
    notes = plan({"action": "call"}, facts(next_visit=12, next_user=8))
    assert kinds(notes) == [(7, "visit.called"), (8, "visit.next")]
    assert notes[1].dedupe_key == "8:visit:12:next"  # once per visit, however many events follow


def test_next_is_skipped_for_unlinked_patients():
    assert kinds(plan({"action": "complete"}, facts(next_visit=12, next_user=None))) == []


def test_appointment_confirmation_includes_time_and_note():
    f = facts(visit_id=None, appointment_id=5, scheduled_for=WHEN, staff_note="Bring your health card")
    [n] = plan({"action": "appointment.confirm"}, f)
    assert n.title == "Appointment confirmed" and n.link == "appointments"
    assert n.body == "Outpatient, Tue 20 Oct, 09:30. Note from the clinic: Bring your health card"


def test_request_goes_to_front_desk_but_not_whoever_made_it():
    f = facts(visit_id=None, appointment_id=5, scheduled_for=WHEN, actor=3)
    notes = plan({"action": "appointment.requested"}, f)
    assert kinds(notes) == [(2, "appointment.requested")]
    assert notes[0].body == "Ada Obi asked for Outpatient on Tue 20 Oct, 09:30."


def test_cancel_by_patient_tells_staff_cancel_by_staff_tells_patient():
    f = facts(visit_id=None, appointment_id=5, scheduled_for=WHEN, actor=7)
    assert kinds(plan({"action": "appointment.cancel"}, f)) == [(2, "appointment.cancelled"), (3, "appointment.cancelled")]
    f.actor = 2
    [n] = plan({"action": "appointment.cancel"}, f)
    assert (n.recipient, n.body) == (7, "The clinic cancelled your Outpatient appointment for Tue 20 Oct, 09:30.")


def test_no_clinical_details_leave_by_email_or_sms():
    assert "Outpatient" not in channels.GENERIC_MESSAGE


def test_delivery_statuses():
    contact = channels.Contact(email="ada@example.com", phone="")
    assert channels.deliver(channels.LogEmail(), contact) == ("sent", "")
    assert channels.deliver(channels.LogSMS(), contact) == ("skipped", "no sms address")

    class Broken(channels.LogEmail):
        def send(self, to, message):
            raise RuntimeError("provider down")

    assert channels.deliver(Broken(), contact) == ("failed", "provider down")


def test_unknown_channel_is_a_startup_error():
    try:
        channels.build(["pager"])
    except ValueError as exc:
        assert "pager" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_urgent_arrival_pages_clinicians_but_not_whoever_checked_them_in():
    f = facts(esi=2, urgent_staff=[20, 21], actor=21)
    notes = [n for n in plan({"action": "checked_in"}, f) if n.kind == "visit.urgent"]
    assert [(n.recipient, n.link, n.dedupe_key) for n in notes] == [(20, "queue", "20:visit:11:urgent:2")]
    assert notes[0].body == "An ESI 2 patient is waiting in Outpatient. Check the queue."
    assert not [n for n in plan({"action": "checked_in"}, facts(esi=3, urgent_staff=[20])) if n.kind == "visit.urgent"]


def test_only_escalation_into_esi_1_2_pages():
    up = facts(esi=2, previous_esi=4, urgent_staff=[20])
    assert [n.kind for n in plan({"action": "triage"}, up)] == ["visit.urgent"]
    down = facts(esi=2, previous_esi=1, urgent_staff=[20])
    assert plan({"action": "triage"}, down) == []
    # A call isn't an arrival: no page.
    assert plan({"action": "call"}, facts(esi=1, urgent_staff=[20], patient_user=None)) == []


def test_turn_is_near_for_the_people_behind_the_next():
    f = facts(patient_user=None, next_visit=12, next_user=8, near=[(13, 9, 1), (14, None, 2), (15, 10, 2)])
    notes = plan({"action": "complete"}, f)
    assert [(n.recipient, n.kind) for n in notes] == [(8, "visit.next"), (9, "visit.near"), (10, "visit.near")]
    assert notes[1].body.startswith("1 person is ahead of you in Outpatient.")
    assert notes[2].dedupe_key == "10:visit:15:near"


def test_scheduled_wording():
    from app.rules import DueAppointment, LongWait, delay_notes, reminder_notes
    day, hour = reminder_notes([DueAppointment(5, 7, "Outpatient", WHEN, "day"), DueAppointment(6, 7, "Outpatient", WHEN, "hour")])
    assert (day.title, day.dedupe_key) == ("Appointment tomorrow", "7:appt:5:remind:day")
    assert day.body == "Reminder: Outpatient, Tue 20 Oct, 09:30. Cancel in the app if you can't make it."
    assert hour.title == "Appointment soon" and "at 09:30" in hour.body
    [delay] = delay_notes([LongWait(11, 7, "Outpatient", 75)])
    assert delay.dedupe_key == "7:visit:11:delay" and "about 75 min in Outpatient" in delay.body
    assert "feel worse" in delay.body
