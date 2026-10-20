package api

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

// ---- fake store methods for appointments

func (f *fakeStore) PatientIDForUser(_ context.Context, userID int64) (int64, error) {
	if id, ok := f.links[userID]; ok {
		return id, nil
	}
	return 0, store.ErrNotFound
}

func (f *fakeStore) ListAppointments(_ context.Context, filter store.AppointmentFilter) ([]store.Appointment, error) {
	var out []store.Appointment
	for _, a := range f.appts {
		if filter.PatientID == 0 || a.PatientID == filter.PatientID {
			out = append(out, a)
		}
	}
	return out, nil
}

func (f *fakeStore) CreateAppointment(_ context.Context, _ store.User, in store.NewAppointment) (store.Appointment, error) {
	f.gotAppt = in
	if f.apptErr != nil {
		return store.Appointment{}, f.apptErr
	}
	return store.Appointment{ID: 30, Reference: "A-1234ABCD", PatientID: in.PatientID, DepartmentID: in.DepartmentID,
		ScheduledFor: in.ScheduledFor, Status: in.Status, Reason: in.Reason, RequestedBy: strPtr("student"), HandledBy: strPtr("reception")}, nil
}

func (f *fakeStore) AppointmentAction(_ context.Context, _ store.User, _ int64, action string, up store.AppointmentUpdate) (store.Appointment, error) {
	f.gotAction, f.gotUpdate = action, up
	if action == "check_in" && up.CheckInAllowed != nil {
		if msg := up.CheckInAllowed(f.appts[0].ScheduledFor); msg != "" {
			return store.Appointment{}, store.ValidationError{"non_field_errors": {msg}}
		}
	}
	return f.appts[0], nil
}

func (f *fakeStore) Schedule(_ context.Context, departmentID int64, base flow.Schedule) (flow.Schedule, error) {
	f.gotScheduleDept = departmentID
	if f.schedule != nil {
		return *f.schedule, nil
	}
	return base, nil
}

func strPtr(s string) *string { return &s }

// apptFixture: student (user 3) owns patient 8, which has one confirmed appointment today at 14:30.
func apptFixture() (*fakeStore, http.Handler) {
	f, s := newFixture()
	f.links = map[int64]int64{3: 8}
	f.appts = []store.Appointment{{ID: 30, Reference: "A-1234ABCD", PatientID: 8, PatientName: "Ada", DepartmentName: "Outpatient",
		ScheduledFor: time.Date(2026, 10, 13, 14, 30, 0, 0, lagos), Status: flow.ApptConfirmed,
		RequestedBy: strPtr("student"), HandledBy: strPtr("reception")}}
	return f, s.Routes()
}

// ---- tests

func TestStudentRequestsForOwnRecordOnly(t *testing.T) {
	f, h := apptFixture()
	rec, body := call(t, h, "POST", "/api/appointments", "user-3",
		`{"patient": 999, "department": 1, "date": "2026-10-14", "time": "09:30", "reason": "cough"}`)
	if rec.Code != 201 {
		t.Fatalf("status %d %v", rec.Code, body)
	}
	if f.gotAppt.PatientID != 8 || f.gotAppt.Status != flow.ApptRequested || f.gotAppt.Reason != "cough" {
		t.Fatalf("students book for their own record, as a request (patient field ignored): %+v", f.gotAppt)
	}
	if !f.gotAppt.ScheduledFor.Equal(time.Date(2026, 10, 14, 9, 30, 0, 0, lagos)) {
		t.Fatalf("slot must be read in hospital time: %v", f.gotAppt.ScheduledFor)
	}
	if body["requested_by"] != nil || body["handled_by"] != nil || body["date"] != "2026-10-14" || body["time"] != "09:30" {
		t.Fatalf("patients get no staff usernames; date and time are local: %v", body)
	}
}

func TestUnlinkedStudentIsToldWhatToDo(t *testing.T) {
	f, h := apptFixture()
	f.links = map[int64]int64{}
	rec, body := call(t, h, "POST", "/api/appointments", "user-3", `{"department": 1, "date": "2026-10-14", "time": "09:30"}`)
	if rec.Code != 400 || !strings.Contains(body["detail"].(string), "linked") {
		t.Fatalf("got %d %v", rec.Code, body)
	}
}

func TestStaffBookingIsConfirmedAndNeedsAPatient(t *testing.T) {
	f, h := apptFixture()
	if rec, body := call(t, h, "POST", "/api/appointments", "user-6", `{"department": 1, "date": "2026-10-14", "time": "09:30"}`); rec.Code != 400 || body["patient"] == nil {
		t.Fatalf("staff must choose a patient: %d %v", rec.Code, body)
	}
	rec, _ := call(t, h, "POST", "/api/appointments", "user-6", `{"patient": 7, "department": 1, "date": "2026-10-14", "time": "09:30"}`)
	if rec.Code != 201 || f.gotAppt.PatientID != 7 || f.gotAppt.Status != flow.ApptConfirmed {
		t.Fatalf("staff booking: %d %+v", rec.Code, f.gotAppt)
	}
}

func TestSlotValidation(t *testing.T) {
	_, h := apptFixture()
	for slot, field := range map[string]string{
		`"date": "2026-10-17", "time": "10:00"`: "time", // Saturday
		`"date": "2026-10-14", "time": "18:00"`: "time", // after hours
		`"date": "2026-10-12", "time": "10:00"`: "time", // yesterday
		`"date": "14/10/2026", "time": "10:00"`: "date",
		`"date": "2026-10-14"`:                  "date",
	} {
		rec, body := call(t, h, "POST", "/api/appointments", "user-3", `{"department": 1, `+slot+`}`)
		if rec.Code != 400 || body[field] == nil {
			t.Errorf("%s: want 400 with %q, got %d %v", slot, field, rec.Code, body)
		}
	}
}

func TestMyAppointments(t *testing.T) {
	_, h := apptFixture()
	rec, _ := call(t, h, "GET", "/api/appointments/mine", "user-3", "")
	var got struct {
		Linked       bool              `json:"linked"`
		Schedule     string            `json:"schedule"`
		Appointments []appointmentJSON `json:"appointments"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if !got.Linked || len(got.Appointments) != 1 || got.Appointments[0].HandledBy != nil || got.Schedule == "" {
		t.Fatalf("mine: %s", rec.Body)
	}
	if rec, _ := call(t, h, "GET", "/api/appointments/mine", "user-1", ""); !strings.Contains(rec.Body.String(), `"linked":false`) {
		t.Fatalf("staff without a patient record get an empty, unlinked answer: %s", rec.Body)
	}
}

func TestStaffListIsStaffOnly(t *testing.T) {
	_, h := apptFixture()
	if rec, _ := call(t, h, "GET", "/api/appointments", "user-3", ""); rec.Code != 403 {
		t.Fatalf("students can't list everyone's appointments: %d", rec.Code)
	}
	if rec, _ := call(t, h, "GET", "/api/appointments?date=2026-10-13&status=requested,confirmed", "user-6", ""); rec.Code != 200 {
		t.Fatalf("reception lists appointments: %d", rec.Code)
	}
}

func TestActionsValidateTheirInput(t *testing.T) {
	f, h := apptFixture()
	if rec, body := call(t, h, "POST", "/api/appointments/30/decline", "user-6", `{}`); rec.Code != 400 || body["note"] == nil {
		t.Fatalf("decline needs a note: %d %v", rec.Code, body)
	}
	call(t, h, "POST", "/api/appointments/30/confirm", "user-6", `{"date": "2026-10-15", "time": "11:00", "note": "See you then"}`)
	if f.gotAction != "confirm" || f.gotUpdate.ScheduledFor == nil || *f.gotUpdate.Note != "See you then" {
		t.Fatalf("confirm with reschedule: %+v", f.gotUpdate)
	}
	if rec, body := call(t, h, "POST", "/api/appointments/30/check_in", "user-6", `{}`); rec.Code != 400 || body["esi"] == nil {
		t.Fatalf("check-in needs an ESI: %d %v", rec.Code, body)
	}
	rec, _ := call(t, h, "POST", "/api/appointments/30/check_in", "user-6", `{"esi": 4, "vitals": {"heart_rate": 80}}`)
	if rec.Code != 200 || f.gotUpdate.CheckIn.ESI != 4 || *f.gotUpdate.CheckIn.Vitals.HeartRate != 80 {
		t.Fatalf("check-in: %d %+v", rec.Code, f.gotUpdate.CheckIn)
	}
	// Only on the appointment's own day: move it to tomorrow and check-in is refused.
	f.appts[0].ScheduledFor = f.appts[0].ScheduledFor.AddDate(0, 0, 1)
	if rec, _ := call(t, h, "POST", "/api/appointments/30/check_in", "user-6", `{"esi": 4}`); rec.Code != 400 || !strings.Contains(rec.Body.String(), "walk-in") {
		t.Fatalf("check-in on the wrong day: %d %s", rec.Code, rec.Body)
	}
	if rec, _ := call(t, h, "POST", "/api/appointments/30/postpone", "user-6", `{}`); rec.Code != 404 {
		t.Fatalf("unknown action: %d", rec.Code)
	}
}

func TestSlotsUseTheDepartmentScheduleAndHolidays(t *testing.T) {
	f, h := apptFixture()
	sched := flow.DefaultSchedule(lagos)
	sched.Holidays = map[string]string{"2026-10-14": "Founders Day"}
	f.schedule = &sched
	rec, body := call(t, h, "POST", "/api/appointments", "user-3", `{"department": 4, "date": "2026-10-14", "time": "09:30"}`)
	if rec.Code != 400 || body["time"].([]any)[0] != "The clinic is closed on Wed 14 Oct (Founders Day)." || f.gotScheduleDept != 4 {
		t.Fatalf("holiday booking: %d %v (department %d)", rec.Code, body, f.gotScheduleDept)
	}
	rec, body = call(t, h, "GET", "/api/appointments/mine", "user-3", "")
	if rec.Code != 200 || f.gotScheduleDept != 0 {
		t.Fatalf("mine uses the clinic-wide schedule: %d (department %d)", rec.Code, f.gotScheduleDept)
	}
	holidays := body["holidays"].([]any)
	if len(holidays) != 1 || holidays[0].(map[string]any)["name"] != "Founders Day" {
		t.Fatalf("holidays: %v", body["holidays"])
	}
	// Rescheduling passes a slot check that uses the appointment's department.
	call(t, h, "POST", "/api/appointments/30/confirm", "user-6", `{"date": "2026-10-14", "time": "10:00"}`)
	if f.gotUpdate.SlotAllowed == nil {
		t.Fatal("confirm must pass SlotAllowed")
	}
	if msg, err := f.gotUpdate.SlotAllowed(4, time.Date(2026, 10, 14, 10, 0, 0, 0, lagos)); err != nil || msg == "" {
		t.Fatalf("slot check on a holiday: %q %v", msg, err)
	}
}
