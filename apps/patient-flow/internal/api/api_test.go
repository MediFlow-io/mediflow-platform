package api

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"mediflow/patient-flow/internal/auth"
	"mediflow/patient-flow/internal/events"
	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

var lagos, _ = time.LoadLocation("Africa/Lagos")
var now = time.Date(2026, 10, 13, 12, 0, 0, 0, lagos)

// ---- fakes

type fakeTokens struct{}

// Tokens look like "user-<id>"; anything else is invalid.
func (fakeTokens) Verify(_ context.Context, token string) (*auth.Claims, error) {
	id, ok := strings.CutPrefix(token, "user-")
	if !ok {
		return nil, auth.ErrInvalidToken
	}
	return &auth.Claims{UserID: id}, nil
}

type fakeStore struct {
	users       map[int64]store.User
	visits      []store.Visit
	today       []store.DashboardRow
	active      []store.DashboardRow
	checkInErr  error
	gotFilter   store.VisitFilter
	gotCheckIn  store.CheckIn
	gotPatch    store.VisitPatch
	transitions []string
	reportRows  []store.ReportRow
	appts       []store.Appointment
	links       map[int64]int64 // user id -> patient id
	gotAppt     store.NewAppointment
	gotAction   string
	gotUpdate   store.AppointmentUpdate
	apptErr     error
	reportSince time.Time
	reportUntil time.Time
}

func (f *fakeStore) Ping(context.Context) error { return nil }
func (f *fakeStore) UserByID(_ context.Context, id int64) (store.User, error) {
	u, ok := f.users[id]
	if !ok {
		return u, store.ErrNotFound
	}
	return u, nil
}
func (f *fakeStore) ListVisits(_ context.Context, filter store.VisitFilter) ([]store.Visit, error) {
	f.gotFilter = filter
	return f.visits, nil
}
func (f *fakeStore) GetVisit(_ context.Context, id int64) (store.Visit, error) {
	for _, v := range f.visits {
		if v.ID == id {
			return v, nil
		}
	}
	return store.Visit{}, store.ErrNotFound
}
func (f *fakeStore) CheckIn(_ context.Context, _ store.User, in store.CheckIn) (store.Visit, error) {
	f.gotCheckIn = in
	if f.checkInErr != nil {
		return store.Visit{}, f.checkInErr
	}
	return f.visits[0], nil
}
func (f *fakeStore) UpdateVisit(_ context.Context, _ store.User, id int64, p store.VisitPatch) (store.Visit, error) {
	f.gotPatch = p
	return f.GetVisit(context.Background(), id)
}
func (f *fakeStore) Transition(_ context.Context, actor store.User, id int64, action string) (store.Visit, error) {
	v, err := f.GetVisit(context.Background(), id)
	if err != nil {
		return v, err
	}
	t, err := flow.Check(action, actor.Role, v.Status)
	if err != nil {
		return v, err
	}
	f.transitions = append(f.transitions, action)
	v.Status = t.To
	return v, nil
}
func (f *fakeStore) DashboardData(context.Context, time.Time, time.Time) ([]store.DashboardRow, []store.DashboardRow, error) {
	return f.today, f.active, nil
}

func (f *fakeStore) ReportRows(_ context.Context, since, until time.Time) ([]store.ReportRow, error) {
	f.reportSince, f.reportUntil = since, until
	return f.reportRows, nil
}

func newFixture() (*fakeStore, *Server) {
	clinician := "Dr. Demo"
	clinicianID := int64(2)
	called := now.Add(-10 * time.Minute)
	f := &fakeStore{
		users: map[int64]store.User{
			1: {ID: 1, Username: "nurse", Role: flow.Nurse, Active: true},
			2: {ID: 2, Username: "doctor", Role: flow.Doctor, Active: true},
			3: {ID: 3, Username: "student", Role: flow.Student, Active: true},
			4: {ID: 4, Username: "gone", Role: flow.Admin, Active: false},
			5: {ID: 5, Username: "it", Role: flow.IT, Active: true},
			6: {ID: 6, Username: "reception", Role: flow.Reception, Active: true},
		},
		visits: []store.Visit{
			{ID: 10, Number: "V-AAAAAAAAAA", PatientID: 7, PatientName: "Urgent Case", PatientHospitalNumber: "MF-1",
				DepartmentID: 1, DepartmentCode: "opd", DepartmentName: "Outpatient", ESI: 1, Status: flow.Waiting,
				ArrivalMode: "walk_in", CheckedInAt: now.Add(-5 * time.Minute)},
			{ID: 11, Number: "V-BBBBBBBBBB", PatientID: 8, PatientName: "Ada", PatientHospitalNumber: "MF-2",
				DepartmentID: 1, DepartmentCode: "opd", DepartmentName: "Outpatient", ESI: 3, Status: flow.Called,
				ArrivalMode: "walk_in", CheckedInAt: now.Add(-42 * time.Minute), CalledAt: &called,
				ClinicianID: &clinicianID, ClinicianName: &clinician},
		},
	}
	return f, &Server{Store: f, Tokens: fakeTokens{}, Hub: events.NewHub(), Loc: lagos,
		Log: slog.New(slog.NewTextHandler(io.Discard, nil)), Now: func() time.Time { return now }, Heartbeat: time.Hour,
		Schedule: flow.DefaultSchedule(lagos)}
}

func call(t *testing.T, h http.Handler, method, path, token, body string) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var obj map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &obj)
	return rec, obj
}

// ---- tests

func TestAuthentication(t *testing.T) {
	_, s := newFixture()
	h := s.Routes()
	cases := []struct {
		token string
		want  int
	}{
		{"", 401},
		{"garbage", 401},
		{"user-999", 401}, // user no longer exists
		{"user-4", 401},   // deactivated: takes effect immediately, whatever the token says
		{"user-3", 403},   // students never see the queue
		{"user-5", 403},   // IT has no access to patient data
		{"user-1", 200},
	}
	for _, c := range cases {
		if rec, _ := call(t, h, "GET", "/api/visits", c.token, ""); rec.Code != c.want {
			t.Errorf("token %q: got %d, want %d", c.token, rec.Code, c.want)
		}
	}
}

func TestVisitJSONMatchesContract(t *testing.T) {
	_, s := newFixture()
	rec, _ := call(t, s.Routes(), "GET", "/api/visits/11", "user-1", "")
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	keys := make([]string, 0, len(got))
	for k := range got {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	// Additive changes only: chief_complaint, pain_score and vitals were added with vitals storage.
	want := []string{"arrival_mode", "assigned_clinician", "assigned_clinician_name", "called_at", "checked_in_at",
		"chief_complaint", "completed_at", "department", "department_code", "department_name", "esi", "id",
		"pain_score", "patient", "patient_hospital_number", "patient_name", "started_at", "status", "visit_number", "vitals"}
	if !reflect.DeepEqual(keys, want) {
		t.Fatalf("visit fields changed:\n got %v\nwant %v", keys, want)
	}
	if got["checked_in_at"] != "2026-10-13T11:18:00+01:00" || got["started_at"] != nil || got["assigned_clinician_name"] != "Dr. Demo" {
		t.Fatalf("unexpected values: %v", got)
	}
}

func TestVisitFilters(t *testing.T) {
	f, s := newFixture()
	call(t, s.Routes(), "GET", "/api/visits?status=called,in_progress&department=opd&patient=8&today=true", "user-1", "")
	g := f.gotFilter
	if !reflect.DeepEqual(g.Statuses, []string{"called", "in_progress"}) || g.Department != "opd" || g.PatientID != 8 {
		t.Fatalf("filter not parsed: %+v", g)
	}
	if g.Since == nil || !g.Since.Equal(time.Date(2026, 10, 13, 0, 0, 0, 0, lagos)) || !g.Until.Equal(g.Since.AddDate(0, 0, 1)) {
		t.Fatalf("today should be the hospital's local day: %v - %v", g.Since, g.Until)
	}
}

func TestCheckInValidation(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	rec, body := call(t, h, "POST", "/api/visits", "user-6", `{"patient": "abc"}`)
	if rec.Code != 400 || body["department"] == nil || body["esi"] == nil || body["patient"] == nil {
		t.Fatalf("want field errors for all three fields, got %d %v", rec.Code, body)
	}
	rec, _ = call(t, h, "POST", "/api/visits", "user-6", `{"patient": "7", "department": 1, "esi": 2}`)
	if rec.Code != 201 || f.gotCheckIn != (store.CheckIn{PatientID: 7, DepartmentID: 1, ESI: 2}) {
		t.Fatalf("numeric strings should be accepted like before: %d %+v", rec.Code, f.gotCheckIn)
	}
	f.checkInErr = store.ValidationError{"patient": {"This patient already has an active visit."}}
	rec, body = call(t, h, "POST", "/api/visits", "user-6", `{"patient": 7, "department": 1, "esi": 2}`)
	if rec.Code != 400 || !strings.Contains(rec.Body.String(), "already has an active visit") {
		t.Fatalf("store validation errors should pass through as 400: %d %v", rec.Code, body)
	}
	if rec, _ := call(t, h, "POST", "/api/visits", "user-6", `not json`); rec.Code != 400 {
		t.Fatalf("bad JSON should be 400, got %d", rec.Code)
	}
}

func TestOnlyEditorsCanPatchAndStatusIsReadOnly(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	if rec, _ := call(t, h, "PATCH", "/api/visits/10", "user-1", `{"esi": 2}`); rec.Code != 403 {
		t.Fatalf("nurses check in but don't edit visits: got %d", rec.Code)
	}
	rec, _ := call(t, h, "PATCH", "/api/visits/10", "user-6", `{"esi": 2, "status": "completed", "assigned_clinician": null}`)
	if rec.Code != 200 || f.gotPatch.ESI == nil || *f.gotPatch.ESI != 2 || f.gotPatch.ClinicianID == nil || *f.gotPatch.ClinicianID != nil {
		t.Fatalf("patch not applied as expected: %d %+v", rec.Code, f.gotPatch)
	}
	if rec, _ := call(t, h, "PATCH", "/api/visits/10", "user-6", `{"patient": 8}`); rec.Code != 400 {
		t.Fatalf("moving a visit to another patient must be refused, got %d", rec.Code)
	}
}

func TestTransitions(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	rec, body := call(t, h, "POST", "/api/visits/11/start", "user-1", "")
	if rec.Code != 200 || body["status"] != "in_progress" {
		t.Fatalf("nurse should start a called visit: %d %v", rec.Code, body)
	}
	rec, body = call(t, h, "POST", "/api/visits/10/complete", "user-2", "")
	if rec.Code != 409 || body["detail"] != "Cannot complete a visit that is waiting." {
		t.Fatalf("want 409 with the lifecycle message, got %d %v", rec.Code, body)
	}
	if rec, _ := call(t, h, "POST", "/api/visits/10/start", "user-6", ""); rec.Code != 403 {
		t.Fatalf("reception can't start consultations: got %d", rec.Code)
	}
	for _, path := range []string{"/api/visits/999/call", "/api/visits/10/teleport", "/api/visits/abc/call"} {
		if rec, _ := call(t, h, "POST", path, "user-2", ""); rec.Code != 404 {
			t.Errorf("%s: want 404, got %d", path, rec.Code)
		}
	}
	if !reflect.DeepEqual(f.transitions, []string{"start"}) {
		t.Fatalf("only the allowed transition should reach the store: %v", f.transitions)
	}
}

func TestQueueReportsRealWaitAndPosition(t *testing.T) {
	_, s := newFixture()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/queue?department=opd", nil)
	req.Header.Set("Authorization", "Bearer user-1")
	s.Routes().ServeHTTP(rec, req)
	var q []map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &q); err != nil || len(q) != 2 {
		t.Fatalf("bad queue response: %s", rec.Body)
	}
	first, second := q[0], q[1]
	if first["status"] != "Urgent" || first["position"] != 1.0 || first["wait"] != "5 min" || first["arrival"] != "11:55" {
		t.Errorf("first entry wrong: %v", first)
	}
	if second["position"] != 2.0 || second["waitingMinutes"] != 42.0 || second["status"] != "Waiting" {
		t.Errorf("second entry wrong: %v", second)
	}
}

func TestDashboard(t *testing.T) {
	at := func(m int) *time.Time { v := now.Add(time.Duration(m) * time.Minute); return &v }
	today := []store.DashboardRow{
		{PatientID: 1, DepartmentName: "Outpatient", Status: flow.Completed, CheckedInAt: *at(-90), CalledAt: at(-60)},   // waited 30
		{PatientID: 2, DepartmentName: "Outpatient", Status: flow.InProgress, CheckedInAt: *at(-40), StartedAt: at(-15)}, // waited 25
		{PatientID: 2, DepartmentName: "Emergency", Status: flow.Waiting, ESI: 2, CheckedInAt: *at(-20)},
	}
	active := []store.DashboardRow{
		today[1], today[2],
		{PatientID: 3, DepartmentName: "Outpatient", Status: flow.Waiting, ESI: 4, CheckedInAt: now.AddDate(0, 0, -1)}, // left over from yesterday
	}
	d := buildDashboard(today, active, now)
	want := map[string]any{
		"patientsToday": 2, "currentlyWaiting": 2, "inConsultation": 1, "completedToday": 1, "emergencyCases": 1,
		"averageWaitMinutes": 28, "longestCurrentWaitMinutes": 24 * 60,
	}
	for k, v := range want {
		if d[k] != v {
			t.Errorf("%s = %v, want %v", k, d[k], v)
		}
	}
	depts := d["byDepartment"].([]departmentCount)
	if len(depts) != 2 || depts[0].Name != "Emergency" || depts[1].Total != 2 {
		t.Errorf("byDepartment wrong: %+v", depts)
	}
	empty := buildDashboard(nil, nil, now)
	if empty["averageWaitMinutes"] != nil || empty["longestCurrentWaitMinutes"] != nil {
		t.Errorf("no data should give null averages: %v", empty)
	}
}

func TestDashboardAllowsITButNotStudents(t *testing.T) {
	_, s := newFixture()
	if rec, _ := call(t, s.Routes(), "GET", "/api/dashboard", "user-5", ""); rec.Code != 200 {
		t.Fatalf("IT should see flow numbers: %d", rec.Code)
	}
	if rec, _ := call(t, s.Routes(), "GET", "/api/dashboard", "user-3", ""); rec.Code != 403 {
		t.Fatalf("students should not: %d", rec.Code)
	}
}

func TestQueueEventsStream(t *testing.T) {
	_, s := newFixture()
	srv := httptest.NewServer(s.Routes())
	defer srv.Close()
	req, _ := http.NewRequest("GET", srv.URL+"/api/queue/events", nil)
	req.Header.Set("Authorization", "Bearer user-1")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.Header.Get("Content-Type") != "text/event-stream" {
		t.Fatalf("content type %q", resp.Header.Get("Content-Type"))
	}
	reader := bufio.NewReader(resp.Body)
	if line, _ := reader.ReadString('\n'); line != ": connected\n" {
		t.Fatalf("unexpected first line %q", line)
	}
	deadline := time.Now().Add(2 * time.Second)
	for s.Hub.Subscribers() == 0 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	s.Hub.Publish([]byte(`{"visitId":10,"action":"call"}`))
	var got []string
	for len(got) < 2 {
		line, err := reader.ReadString('\n')
		if errors.Is(err, io.EOF) {
			break
		}
		if line = strings.TrimSpace(line); line != "" {
			got = append(got, line)
		}
	}
	if !reflect.DeepEqual(got, []string{"event: visit", `data: {"visitId":10,"action":"call"}`}) {
		t.Fatalf("unexpected event lines: %q", got)
	}
}

func TestHealth(t *testing.T) {
	_, s := newFixture()
	if rec, body := call(t, s.Routes(), "GET", "/healthz", "", ""); rec.Code != 200 || body["status"] != "ok" {
		t.Fatalf("health: %d %v", rec.Code, body)
	}
}
