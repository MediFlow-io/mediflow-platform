package store

import (
	"context"
	"errors"
	"regexp"
	"sync"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
)

// student creates a login account linked to the fixture's first patient.
func student(t *testing.T, f *fixture) User {
	t.Helper()
	ctx := context.Background()
	var id int64
	must(t, f.pool.QueryRow(ctx, `INSERT INTO accounts_user (password, is_superuser, username, first_name, last_name, email,
		is_staff, is_active, date_joined, role, display_name) VALUES ('!', false, 'stu', '', '', '', false, true, now(), 'student', 'Stu')
		RETURNING id`).Scan(&id))
	_, err := f.pool.Exec(ctx, `UPDATE patients_patient SET user_id = $1 WHERE id = $2`, id, f.patient)
	must(t, err)
	return User{ID: id, Username: "stu", Role: flow.Student, Active: true}
}

func slot(days int) time.Time {
	return time.Now().Add(time.Duration(days) * 24 * time.Hour).Truncate(time.Minute)
}

func TestAppointmentRequestConfirmCheckIn(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	stu := student(t, f)
	if id, err := f.s.PatientIDForUser(ctx, stu.ID); err != nil || id != f.patient {
		t.Fatalf("link lookup: %d %v", id, err)
	}
	a, err := f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(2), Reason: "cough", Status: flow.ApptRequested})
	must(t, err)
	if !regexp.MustCompile(`^A-[0-9A-F]{8}$`).MatchString(a.Reference) || a.Status != flow.ApptRequested || *a.RequestedBy != "stu" || a.HandledBy != nil {
		t.Fatalf("request: %+v", a)
	}
	note, moved := "Come at 10", slot(3)
	a, err = f.s.AppointmentAction(ctx, f.reception, a.ID, "confirm", AppointmentUpdate{Note: &note, ScheduledFor: &moved})
	must(t, err)
	if a.Status != flow.ApptConfirmed || a.StaffNote != "Come at 10" || !a.ScheduledFor.Equal(moved) || *a.HandledBy != "reception" {
		t.Fatalf("confirm: %+v", a)
	}
	hr := 77
	a, err = f.s.AppointmentAction(ctx, f.reception, a.ID, "check_in", AppointmentUpdate{CheckIn: &CheckIn{ESI: 4, Vitals: Vitals{HeartRate: &hr}}})
	must(t, err)
	if a.Status != flow.ApptCheckedIn || a.VisitID == nil {
		t.Fatalf("check-in: %+v", a)
	}
	v, err := f.s.GetVisit(ctx, *a.VisitID)
	must(t, err)
	if v.PatientID != f.patient || v.Status != flow.Waiting || v.ArrivalMode != "appointment" || *v.Vitals.HeartRate != 77 {
		t.Fatalf("visit created from appointment: %+v", v)
	}
	got := auditActions(t, f)
	want := []string{"appointment.requested", "appointment.confirm", "visit.checked_in", "appointment.check_in"}
	if len(got) != 4 || got[0] != want[0] || got[1] != want[1] || got[2] != want[2] || got[3] != want[3] {
		t.Fatalf("audit %v, want %v", got, want)
	}
}

func TestCheckInIsAllOrNothing(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	a, err := f.s.CreateAppointment(ctx, f.reception, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(1), Status: flow.ApptConfirmed})
	must(t, err)
	if a.Status != flow.ApptConfirmed || *a.HandledBy != "reception" {
		t.Fatalf("staff booking is confirmed: %+v", a)
	}
	_, err = f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3}) // already in the queue
	must(t, err)
	var ve ValidationError
	if _, err := f.s.AppointmentAction(ctx, f.reception, a.ID, "check_in", AppointmentUpdate{CheckIn: &CheckIn{ESI: 3}}); !errors.As(err, &ve) {
		t.Fatalf("second active visit must be refused: %v", err)
	}
	a, err = f.s.GetAppointment(ctx, a.ID)
	must(t, err)
	if a.Status != flow.ApptConfirmed || a.VisitID != nil {
		t.Fatalf("a failed check-in must leave the appointment untouched: %+v", a)
	}
	msg := "not today"
	if _, err := f.s.AppointmentAction(ctx, f.reception, a.ID, "check_in", AppointmentUpdate{CheckIn: &CheckIn{ESI: 3},
		CheckInAllowed: func(time.Time) string { return msg }}); !errors.As(err, &ve) || ve["non_field_errors"][0] != msg {
		t.Fatalf("the day check must be applied: %v", err)
	}
}

func TestPatientsCanOnlyCancelTheirOwn(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	stu := student(t, f)
	mine, err := f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(2), Status: flow.ApptRequested})
	must(t, err)
	other, err := f.s.CreateAppointment(ctx, f.reception, NewAppointment{PatientID: f.otherPatnt, DepartmentID: f.opd, ScheduledFor: slot(2), Status: flow.ApptConfirmed})
	must(t, err)
	if _, err := f.s.AppointmentAction(ctx, stu, other.ID, "cancel", AppointmentUpdate{}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("someone else's appointment must look like it doesn't exist: %v", err)
	}
	var fe *flow.Error
	if _, err := f.s.AppointmentAction(ctx, stu, mine.ID, "confirm", AppointmentUpdate{}); !errors.As(err, &fe) || fe.Status != 403 {
		t.Fatalf("patients can't confirm: %v", err)
	}
	a, err := f.s.AppointmentAction(ctx, stu, mine.ID, "cancel", AppointmentUpdate{})
	must(t, err)
	if a.Status != flow.ApptCancelled || a.HandledBy != nil {
		t.Fatalf("own cancel: %+v", a)
	}
}

func TestOpenAppointmentLimitUnderConcurrency(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	stu := student(t, f)
	var wg sync.WaitGroup
	var mu sync.Mutex
	created, refused := 0, 0
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			_, err := f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd,
				ScheduledFor: slot(2 + i), Status: flow.ApptRequested})
			mu.Lock()
			defer mu.Unlock()
			var ve ValidationError
			switch {
			case err == nil:
				created++
			case errors.As(err, &ve):
				refused++
			default:
				t.Errorf("unexpected error: %v", err)
			}
		}(i)
	}
	wg.Wait()
	if created != flow.MaxOpenAppointmentsPerPatient || refused != 10-flow.MaxOpenAppointmentsPerPatient {
		t.Fatalf("want exactly %d created, got created=%d refused=%d", flow.MaxOpenAppointmentsPerPatient, created, refused)
	}
	var ve ValidationError
	if _, err := f.s.CreateAppointment(ctx, f.reception, NewAppointment{PatientID: f.patient, DepartmentID: f.closed, ScheduledFor: slot(9), Status: flow.ApptConfirmed}); !errors.As(err, &ve) {
		t.Fatalf("closed department must refuse bookings: %v", err)
	}
	list, err := f.s.ListAppointments(ctx, AppointmentFilter{PatientID: f.patient, Statuses: []string{"requested"}})
	must(t, err)
	if len(list) != 3 || !list[0].ScheduledFor.Before(list[1].ScheduledFor) {
		t.Fatalf("list should be oldest slot first: %d", len(list))
	}
}
