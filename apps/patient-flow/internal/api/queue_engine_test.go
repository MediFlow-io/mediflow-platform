package api

import (
	"encoding/json"
	"errors"
	"net/http/httptest"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

func waitingVisit(id int64, dept string, esi int, waited time.Duration) store.Visit {
	return store.Visit{ID: id, Number: "V-X", PatientID: id, PatientName: "P", DepartmentCode: dept, DepartmentName: dept,
		ESI: esi, Status: flow.Waiting, CheckedInAt: now.Add(-waited)}
}

func queueList(t *testing.T, f *fakeStore, s *Server) []queueEntry {
	t.Helper()
	req := httptest.NewRequest("GET", "/api/queue", nil)
	req.Header.Set("Authorization", "Bearer user-1")
	rec := httptest.NewRecorder()
	s.Routes().ServeHTTP(rec, req)
	var out []queueEntry
	if rec.Code != 200 || json.Unmarshal(rec.Body.Bytes(), &out) != nil {
		t.Fatalf("queue: %d %s", rec.Code, rec.Body)
	}
	return out
}

func TestQueueHasEstimatesAndTargetsPerDepartment(t *testing.T) {
	f, s := newFixture()
	// Already in queue order (ESI, then arrival), across two departments.
	f.visits = []store.Visit{
		waitingVisit(1, "opd", 2, 15*time.Minute), // ESI 2 target 10 → over
		waitingVisit(2, "er", 3, 5*time.Minute),
		waitingVisit(3, "opd", 3, 20*time.Minute),
		waitingVisit(4, "opd", 4, 40*time.Minute),
	}
	f.stats = map[string]flow.DeptStats{"opd": {AvgServiceMinutes: 10, ActiveConsults: 2}, "er": {AvgServiceMinutes: 30}}
	q := queueList(t, f, s)
	type row struct {
		ahead, est, target int
		over               bool
	}
	want := []row{{0, 0, 10, true}, {0, 0, 30, false}, {1, 5, 30, false}, {2, 10, 60, false}}
	for i, w := range want {
		got := row{q[i].AheadInDepartment, *q[i].EstimatedWaitMinutes, q[i].TargetMinutes, q[i].OverTarget}
		if got != w {
			t.Errorf("entry %d: got %+v, want %+v", i, got, w)
		}
	}
	if q[2].Position != 3 {
		t.Error("the overall position is unchanged")
	}

	f.statsErr = errors.New("db hiccup")
	if q := queueList(t, f, s); q[0].EstimatedWaitMinutes != nil || !q[0].OverTarget {
		t.Error("without stats the queue is still served, with targets but no estimates")
	}
}

func TestTriageChangeNeedsClinicalRoleAndReason(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	if rec, _ := call(t, h, "POST", "/api/visits/10/triage", "user-6", `{"esi": 2, "reason": "x"}`); rec.Code != 403 {
		t.Errorf("reception may not change triage: %d", rec.Code)
	}
	rec, body := call(t, h, "POST", "/api/visits/10/triage", "user-1", `{"esi": 2}`)
	if rec.Code != 400 || body["reason"] == nil {
		t.Errorf("reason is required: %d %v", rec.Code, body)
	}
	rec, body = call(t, h, "POST", "/api/visits/10/triage", "user-1", `{"esi": 2, "reason": "  SpO2 89%  "}`)
	if rec.Code != 200 || body["esi"].(float64) != 2 {
		t.Fatalf("change: %d %v", rec.Code, body)
	}
	if f.gotTriage[0] != int64(10) || f.gotTriage[1] != 2 || f.gotTriage[2] != "SpO2 89%" {
		t.Errorf("passed to store: %v", f.gotTriage)
	}
	// The literal route wins over the generic /{action} one.
	if f.transitions != nil {
		t.Errorf("must not be treated as a lifecycle action: %v", f.transitions)
	}

	by := "Nurse Demo"
	f.triage = []store.TriageChange{{FromESI: 3, ToESI: 2, Reason: "SpO2 89%", ChangedBy: &by, ChangedAt: now}}
	req := httptest.NewRequest("GET", "/api/visits/10/triage", nil)
	req.Header.Set("Authorization", "Bearer user-2")
	out := httptest.NewRecorder()
	h.ServeHTTP(out, req)
	var history []triageChangeJSON
	if out.Code != 200 || json.Unmarshal(out.Body.Bytes(), &history) != nil || history[0].Direction != "escalated" {
		t.Fatalf("history: %d %s", out.Code, out.Body)
	}
}

func TestMyQueuePosition(t *testing.T) {
	f, s := newFixture()
	h := s.Routes()
	if _, body := call(t, h, "GET", "/api/queue/me", "user-3", ""); body["linked"] != false {
		t.Errorf("unlinked: %v", body)
	}
	f.links = map[int64]int64{3: 3}
	f.visits = []store.Visit{waitingVisit(1, "opd", 2, time.Minute), waitingVisit(3, "opd", 4, time.Minute)}
	f.stats = map[string]flow.DeptStats{"opd": {AvgServiceMinutes: 12}}
	// The fake returns every visit for both queries; the student's own is found by id.
	f.visits = append([]store.Visit{waitingVisit(3, "opd", 4, time.Minute)}, f.visits...)
	_, body := call(t, h, "GET", "/api/queue/me", "user-3", "")
	if body["active"] != true || body["status"] != "waiting" {
		t.Fatalf("active visit: %v", body)
	}
}

func TestDashboardDepartmentLoad(t *testing.T) {
	f, s := newFixture()
	f.active = []store.DashboardRow{
		{DepartmentName: "Outpatient", Status: flow.Waiting, ESI: 3, CheckedInAt: now.Add(-90 * time.Minute)},
		{DepartmentName: "Outpatient", Status: flow.Waiting, ESI: 4, CheckedInAt: now.Add(-5 * time.Minute)},
		{DepartmentName: "Outpatient", Status: flow.InProgress, ESI: 3, CheckedInAt: now.Add(-50 * time.Minute)},
		{DepartmentName: "Emergency", Status: flow.Waiting, ESI: 1, CheckedInAt: now.Add(-2 * time.Minute)},
	}
	_, body := call(t, s.Routes(), "GET", "/api/dashboard", "user-1", "")
	if body["overTarget"].(float64) != 2 || body["longWaits"].(float64) != 1 || body["longWaitMinutes"].(float64) != 60 {
		t.Fatalf("totals: %v", body)
	}
	load := body["departmentLoad"].([]any)
	opd := load[1].(map[string]any)
	if load[0].(map[string]any)["name"] != "Emergency" || opd["waiting"].(float64) != 2 || opd["inConsultation"].(float64) != 1 ||
		opd["longestWaitMinutes"].(float64) != 90 {
		t.Fatalf("by department: %v", load)
	}
}
