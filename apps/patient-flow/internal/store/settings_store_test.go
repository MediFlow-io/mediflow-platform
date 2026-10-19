package store

import (
	"context"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
)

func TestScheduleComesFromSettingsTables(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	lagos, _ := time.LoadLocation("Africa/Lagos")
	base, _ := flow.ParseSchedule(lagos, "00:00-23:59", "Sun-Sat") // the env fallback

	got, err := f.s.Schedule(ctx, f.opd, base)
	must(t, err)
	if got.Describe() != base.Describe() || got.SlotLength != 15*time.Minute {
		t.Fatalf("nothing saved: want the fallback, got %q", got.Describe())
	}

	exec := func(sql string, args ...any) {
		t.Helper()
		_, err := f.pool.Exec(ctx, sql, args...)
		must(t, err)
	}
	for d := 1; d <= 5; d++ {
		exec(`INSERT INTO clinic_servicehours (department_id, weekday, opens, closes) VALUES (NULL, $1, '08:00', '16:00')`, d)
	}
	exec(`INSERT INTO clinic_servicehours (department_id, weekday, opens, closes) VALUES ($1, 6, '09:00', '12:30')`, f.closed)
	holiday := time.Now().In(lagos).AddDate(0, 0, 3).Format("2006-01-02")
	exec(`INSERT INTO clinic_holiday (date, name) VALUES ($1, 'Founders Day'), (current_date - 30, 'Old')`, holiday)
	exec(`INSERT INTO clinic_queuesettings (id, esi1_target_minutes, esi2_target_minutes, esi3_target_minutes, esi4_target_minutes,
		esi5_target_minutes, long_wait_minutes, turn_near_ahead, slot_minutes, max_days_ahead, min_notice_minutes,
		max_open_appointments, updated_at) VALUES (1, 0, 10, 30, 60, 120, 45, 2, 30, 14, 60, 1, now())`)

	got, err = f.s.Schedule(ctx, f.opd, base)
	must(t, err)
	if got.Describe() != "Mon Tue Wed Thu Fri, 08:00–16:00" {
		t.Errorf("clinic default hours: %q", got.Describe())
	}
	if got.SlotLength != 30*time.Minute || got.MaxAhead != 14*24*time.Hour || got.MinNotice != time.Hour {
		t.Errorf("booking rules: %+v", got)
	}
	if got.Holidays[holiday] != "Founders Day" || len(got.Holidays) != 1 {
		t.Errorf("upcoming holidays only: %v", got.Holidays)
	}
	if own, _ := f.s.Schedule(ctx, f.closed, base); own.Describe() != "Sat, 09:00–12:30" {
		t.Errorf("a department's own hours replace the default: %q", own.Describe())
	}
	qs, err := f.s.QueueSettings(ctx)
	must(t, err)
	if qs.LongWaitMinutes != 45 || qs.ESITargetMinutes[2] != 10 {
		t.Errorf("queue settings: %+v", qs)
	}

	// max_open_appointments = 1: the second open appointment is refused.
	stu := student(t, f)
	_, err = f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(2), Status: flow.ApptRequested})
	must(t, err)
	if _, err = f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(3), Status: flow.ApptRequested}); err == nil {
		t.Error("the limit from settings should apply")
	}
}

func TestRescheduleAsksSlotAllowed(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	stu := student(t, f)
	a, err := f.s.CreateAppointment(ctx, stu, NewAppointment{PatientID: f.patient, DepartmentID: f.opd, ScheduledFor: slot(2), Status: flow.ApptRequested})
	must(t, err)
	moved := slot(4)
	var askedDept int64
	_, err = f.s.AppointmentAction(ctx, f.reception, a.ID, "confirm", AppointmentUpdate{ScheduledFor: &moved,
		SlotAllowed: func(dept int64, _ time.Time) (string, error) {
			askedDept = dept
			return "The clinic is closed then.", nil
		}})
	if ve, ok := err.(ValidationError); !ok || ve["time"][0] != "The clinic is closed then." || askedDept != f.opd {
		t.Fatalf("want a time error for department %d, got %v (asked %d)", f.opd, err, askedDept)
	}
	if got, _ := f.s.GetAppointment(ctx, a.ID); got.Status != flow.ApptRequested {
		t.Error("a refused reschedule must not confirm")
	}
}
