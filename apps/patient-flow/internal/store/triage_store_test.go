package store

import (
	"context"
	"errors"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
)

func TestTriageChangesAreLoggedWithoutReasonInAudit(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)

	v, err = f.s.ChangeTriage(ctx, f.nurse, v.ID, 2, "SpO2 dropped to 89%")
	must(t, err)
	if v.ESI != 2 {
		t.Fatalf("esi: %d", v.ESI)
	}
	if _, err := f.s.ChangeTriage(ctx, f.nurse, v.ID, 2, "again"); err == nil {
		t.Error("same level should be refused")
	}
	// An ESI edit through PATCH is logged too.
	four := 4
	_, err = f.s.UpdateVisit(ctx, f.reception, v.ID, VisitPatch{ESI: &four, ESIReason: "entered wrongly"})
	must(t, err)

	history, err := f.s.TriageHistory(ctx, v.ID)
	must(t, err)
	if len(history) != 2 || history[0].FromESI != 3 || history[0].ToESI != 2 || history[0].Reason != "SpO2 dropped to 89%" ||
		history[1].ToESI != 4 || *history[0].ChangedBy != "Nurse" {
		t.Fatalf("history: %+v", history)
	}
	var details string
	must(t, f.pool.QueryRow(ctx, `SELECT details::text FROM operations_auditlog WHERE action = 'visit.triage_changed' ORDER BY id LIMIT 1`).Scan(&details))
	if details != `{"to": 2, "from": 3, "direction": "escalated"}` {
		t.Errorf("audit must hold levels only: %s", details)
	}

	_, err = f.s.Transition(ctx, f.nurse, v.ID, "call")
	must(t, err)
	_, err = f.s.Transition(ctx, f.nurse, v.ID, "start")
	must(t, err)
	var fe *flow.Error
	if _, err := f.s.ChangeTriage(ctx, f.nurse, v.ID, 1, "late"); !errors.As(err, &fe) || fe.Status != 409 {
		t.Errorf("no triage change once the consultation started: %v", err)
	}
}

func TestQueueStats(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		_, err := f.pool.Exec(ctx, sql, args...)
		must(t, err)
	}
	// Two completed visits of 10 and 20 minutes, one in progress.
	for i, minutes := range []int{10, 20} {
		v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: []int64{f.patient, f.otherPatnt}[i], DepartmentID: f.opd, ESI: 3})
		must(t, err)
		exec(`UPDATE patients_visit SET status = 'completed', started_at = now() - make_interval(mins => $1), completed_at = now() WHERE id = $2`, minutes, v.ID)
	}
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	exec(`UPDATE patients_visit SET status = 'in_progress', started_at = now() WHERE id = $1`, v.ID)

	lagos, _ := time.LoadLocation("Africa/Lagos")
	local := time.Now().In(lagos)
	var doctor int64
	must(t, f.pool.QueryRow(ctx, `INSERT INTO accounts_user (password, is_superuser, username, first_name, last_name, email,
		is_staff, is_active, date_joined, role, display_name) VALUES ('!', false, 'doc', '', '', '', false, true, now(), 'doctor', 'Doc')
		RETURNING id`).Scan(&doctor))
	for _, user := range []int64{doctor, f.nurse.ID} { // nurses don't count as doctors
		exec(`INSERT INTO clinic_staffshift (user_id, department_id, weekday, starts, ends) VALUES ($1, $2, $3, '00:00', '23:59:59')`,
			user, f.opd, int(local.Weekday()))
	}

	stats, err := f.s.QueueStats(ctx, local)
	must(t, err)
	opd := stats["opd"]
	if opd.AvgServiceMinutes < 14.9 || opd.AvgServiceMinutes > 15.1 || opd.ActiveConsults != 1 || opd.DoctorsOnShift != 1 {
		t.Fatalf("opd stats: %+v", opd)
	}
	if closed := stats["closed"]; closed.AvgServiceMinutes != 0 || closed.ActiveConsults != 0 {
		t.Errorf("an idle department has zero stats: %+v", closed)
	}
}
