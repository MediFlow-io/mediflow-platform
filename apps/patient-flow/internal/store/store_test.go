package store

// Integration tests against real PostgreSQL. They need the core API's schema:
//
//	(cd apps/core-api && POSTGRES_DB=mediflow_test ... python manage.py migrate)
//	TEST_DATABASE_URL=postgres://user:pass@localhost:5432/mediflow_test go test ./...
//
// They are skipped when TEST_DATABASE_URL is unset, and refuse to run against a database whose
// name doesn't end in "_test", because they TRUNCATE tables.

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/url"
	"os"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"mediflow/patient-flow/internal/events"
	"mediflow/patient-flow/internal/flow"
)

type fixture struct {
	pool                *pgxpool.Pool
	s                   *Store
	nurse, reception    User
	opd, closed         int64
	patient, otherPatnt int64
}

func setup(t *testing.T) *fixture {
	t.Helper()
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	u, err := url.Parse(dsn)
	if err != nil || !strings.HasSuffix(strings.TrimPrefix(u.Path, "/"), "_test") {
		t.Fatalf("refusing to run: database name must end in _test (%s)", u.Path)
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	if _, err := pool.Exec(ctx, `TRUNCATE operations_auditlog, patients_visit, patients_patient, patients_department, accounts_user RESTART IDENTITY CASCADE`); err != nil {
		t.Fatalf("schema missing? run the core API migrations first: %v", err)
	}
	f := &fixture{pool: pool, s: New(pool)}
	user := func(name, role string) User {
		var id int64
		must(t, pool.QueryRow(ctx, `INSERT INTO accounts_user (password, is_superuser, username, first_name, last_name, email,
			is_staff, is_active, date_joined, role, display_name) VALUES ('!', false, $1, '', '', '', false, true, now(), $2, $3) RETURNING id`,
			name, role, strings.ToUpper(name[:1])+name[1:]).Scan(&id))
		return User{ID: id, Username: name, Role: role, Active: true}
	}
	f.nurse, f.reception = user("nurse", flow.Nurse), user("reception", flow.Reception)
	dept := func(name, code string, active bool) (id int64) {
		must(t, pool.QueryRow(ctx, `INSERT INTO patients_department (name, code, active) VALUES ($1, $2, $3) RETURNING id`, name, code, active).Scan(&id))
		return
	}
	f.opd, f.closed = dept("Outpatient", "opd", true), dept("Closed Clinic", "closed", false)
	patient := func(name string) (id int64) {
		must(t, pool.QueryRow(ctx, `INSERT INTO patients_patient (hospital_number, full_name, sex, phone, address, next_of_kin,
			next_of_kin_phone, allergies, medical_history, complaint, diagnosis, treatment, notes, created_at, updated_at)
			VALUES ($1, $2, 'Female', '0', '', '', '', '', '', '', '', '', '', now(), now()) RETURNING id`, "MF-"+name, name).Scan(&id))
		return
	}
	f.patient, f.otherPatnt = patient("Ada"), patient("Bola")
	return f
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}

func auditActions(t *testing.T, f *fixture) []string {
	rows, err := f.pool.Query(context.Background(), `SELECT action FROM operations_auditlog ORDER BY id`)
	must(t, err)
	defer rows.Close()
	var out []string
	for rows.Next() {
		var a string
		must(t, rows.Scan(&a))
		out = append(out, a)
	}
	return out
}

func TestCheckInAndLifecycle(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	if !regexp.MustCompile(`^V-[0-9A-F]{10}$`).MatchString(v.Number) || v.Status != flow.Waiting || v.ArrivalMode != "walk_in" {
		t.Fatalf("unexpected visit %+v", v)
	}
	v, err = f.s.Transition(ctx, f.reception, v.ID, "call")
	must(t, err)
	if v.Status != flow.Called || v.CalledAt == nil {
		t.Fatalf("call: %+v", v)
	}
	v, err = f.s.Transition(ctx, f.nurse, v.ID, "start")
	must(t, err)
	if v.Status != flow.InProgress || v.StartedAt == nil || v.ClinicianID == nil || *v.ClinicianID != f.nurse.ID || *v.ClinicianName != "Nurse" {
		t.Fatalf("start should assign the clinician: %+v", v)
	}
	v, err = f.s.Transition(ctx, f.nurse, v.ID, "complete")
	must(t, err)
	if v.Status != flow.Completed || v.CompletedAt == nil {
		t.Fatalf("complete: %+v", v)
	}
	want := []string{"visit.checked_in", "visit.call", "visit.start", "visit.complete"}
	if got := auditActions(t, f); strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("audit trail %v, want %v", got, want)
	}
	var details map[string]any
	must(t, f.pool.QueryRow(ctx, `SELECT details FROM operations_auditlog WHERE action = 'visit.checked_in'`).Scan(&details))
	if details["department"] != "opd" || details["esi"] != 3.0 {
		t.Fatalf("audit details %v", details)
	}
}

func TestCheckInRules(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	var ve ValidationError
	if _, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 9}); !errors.As(err, &ve) || ve["esi"] == nil {
		t.Fatalf("ESI out of range should fail: %v", err)
	}
	if _, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: 99999, DepartmentID: f.opd, ESI: 3}); !errors.As(err, &ve) || ve["patient"] == nil {
		t.Fatalf("unknown patient should fail: %v", err)
	}
	if _, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.closed, ESI: 3}); !errors.As(err, &ve) || ve["department"][0] != "This department is not active." {
		t.Fatalf("inactive department should fail: %v", err)
	}
	_, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	if _, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3}); !errors.As(err, &ve) || ve["patient"][0] != "This patient already has an active visit." {
		t.Fatalf("second active visit should fail: %v", err)
	}
	if got := auditActions(t, f); len(got) != 1 {
		t.Fatalf("failed check-ins must not be audited or half-written: %v", got)
	}
}

func TestConcurrentCheckInsCreateOneVisit(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	var wg sync.WaitGroup
	var mu sync.Mutex
	ok, rejected := 0, 0
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
			mu.Lock()
			defer mu.Unlock()
			var ve ValidationError
			switch {
			case err == nil:
				ok++
			case errors.As(err, &ve):
				rejected++
			default:
				t.Errorf("unexpected error: %v", err)
			}
		}()
	}
	wg.Wait()
	if ok != 1 || rejected != 9 {
		t.Fatalf("want exactly one visit created, got ok=%d rejected=%d", ok, rejected)
	}
}

func TestConcurrentTransitionsApplyOnce(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	var wg sync.WaitGroup
	var mu sync.Mutex
	codes := map[int]int{}
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := f.s.Transition(ctx, f.reception, v.ID, "call")
			mu.Lock()
			defer mu.Unlock()
			var fe *flow.Error
			if err == nil {
				codes[200]++
			} else if errors.As(err, &fe) {
				codes[fe.Status]++
			} else {
				t.Errorf("unexpected error: %v", err)
			}
		}()
	}
	wg.Wait()
	if codes[200] != 1 || codes[409] != 4 {
		t.Fatalf("want one success and four conflicts, got %v", codes)
	}
}

func TestTransitionErrors(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	var fe *flow.Error
	if _, err := f.s.Transition(ctx, f.reception, v.ID, "start"); !errors.As(err, &fe) || fe.Status != 403 {
		t.Fatalf("reception can't start: %v", err)
	}
	if _, err := f.s.Transition(ctx, f.nurse, v.ID, "complete"); !errors.As(err, &fe) || fe.Status != 409 {
		t.Fatalf("can't complete a waiting visit: %v", err)
	}
	if _, err := f.s.Transition(ctx, f.nurse, 999999, "call"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("unknown visit: %v", err)
	}
	var status string
	must(t, f.pool.QueryRow(ctx, `SELECT status FROM patients_visit WHERE id = $1`, v.ID).Scan(&status))
	if status != "waiting" {
		t.Fatalf("refused transitions must not change the visit, status=%s", status)
	}
}

func TestUpdateAndList(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	a, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 4})
	must(t, err)
	b, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.otherPatnt, DepartmentID: f.opd, ESI: 4})
	must(t, err)
	esi := 1
	clinician := &f.nurse.ID
	updated, err := f.s.UpdateVisit(ctx, f.reception, b.ID, VisitPatch{ESI: &esi, ClinicianID: &clinician})
	must(t, err)
	if updated.ESI != 1 || updated.ClinicianID == nil || *updated.ClinicianID != f.nurse.ID {
		t.Fatalf("update not applied: %+v", updated)
	}
	list, err := f.s.ListVisits(ctx, VisitFilter{Statuses: []string{"waiting"}, Department: "opd"})
	must(t, err)
	if len(list) != 2 || list[0].ID != b.ID || list[1].ID != a.ID {
		t.Fatalf("queue order should be ESI first: %+v", list)
	}
	since := time.Now().Add(-time.Hour)
	if list, _ := f.s.ListVisits(ctx, VisitFilter{PatientID: f.patient, Since: &since}); len(list) != 1 || list[0].ID != a.ID {
		t.Fatalf("patient filter: %+v", list)
	}
	closed := f.closed
	var ve ValidationError
	if _, err := f.s.UpdateVisit(ctx, f.reception, a.ID, VisitPatch{DepartmentID: &closed}); !errors.As(err, &ve) {
		t.Fatalf("moving to an inactive department should fail: %v", err)
	}
	today, active, err := f.s.DashboardData(ctx, time.Now().Add(-time.Hour), time.Now().Add(time.Hour))
	must(t, err)
	if len(today) != 2 || len(active) != 2 {
		t.Fatalf("dashboard data: today=%d active=%d", len(today), len(active))
	}
}

func TestEventsArriveAfterCommitOnly(t *testing.T) {
	f := setup(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hub := events.NewHub()
	sub, stop := hub.Subscribe()
	defer stop()
	go events.Listen(ctx, f.pool, NotifyChannel, hub, slog.New(slog.NewTextHandler(io.Discard, nil)))
	time.Sleep(300 * time.Millisecond) // let LISTEN register

	// A refused transition (nothing committed) must not produce an event...
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 3})
	must(t, err)
	first := waitEvent(t, sub)
	if first.Action != "checked_in" || first.VisitID != v.ID || first.Department != "opd" {
		t.Fatalf("check-in event: %+v", first)
	}
	_, _ = f.s.Transition(ctx, f.nurse, v.ID, "complete") // 409: rolled back
	// ...while a committed one does.
	_, err = f.s.Transition(ctx, f.reception, v.ID, "call")
	must(t, err)
	if e := waitEvent(t, sub); e.Action != "call" || e.Status != "called" {
		t.Fatalf("expected the call event next (the refused complete must not emit), got %+v", e)
	}
}

func waitEvent(t *testing.T, sub <-chan []byte) Event {
	t.Helper()
	select {
	case raw := <-sub:
		var e Event
		must(t, json.Unmarshal(raw, &e))
		return e
	case <-time.After(5 * time.Second):
		t.Fatal("no event received")
	}
	return Event{}
}

func TestReportRowsRange(t *testing.T) {
	f := setup(t)
	ctx := context.Background()
	v, err := f.s.CheckIn(ctx, f.reception, CheckIn{PatientID: f.patient, DepartmentID: f.opd, ESI: 2})
	must(t, err)
	_, err = f.s.Transition(ctx, f.nurse, v.ID, "start")
	must(t, err)
	rows, err := f.s.ReportRows(ctx, time.Now().Add(-time.Hour), time.Now().Add(time.Hour))
	must(t, err)
	if len(rows) != 1 || rows[0].DepartmentName != "Outpatient" || rows[0].ESI != 2 || rows[0].StartedAt == nil {
		t.Fatalf("report rows: %+v", rows)
	}
	if rows, _ := f.s.ReportRows(ctx, time.Now().Add(time.Hour), time.Now().Add(2*time.Hour)); len(rows) != 0 {
		t.Fatalf("out-of-range visits must not be returned: %+v", rows)
	}
}
