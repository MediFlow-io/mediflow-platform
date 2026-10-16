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
