package api

import (
	"encoding/json"
	"testing"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

func TestFlowReportAdminOnlyAndRange(t *testing.T) {
	f, s := newFixture()
	f.users[9] = store.User{ID: 9, Username: "admin", Role: flow.Admin, Active: true}
	h := s.Routes()
	if rec, _ := call(t, h, "GET", "/api/reports/flow", "user-2", ""); rec.Code != 403 {
		t.Fatalf("doctors don't see multi-day reports: %d", rec.Code)
	}
	rec, body := call(t, h, "GET", "/api/reports/flow", "user-9", "")
	if rec.Code != 200 || body["from"] != "2026-10-07" || body["to"] != "2026-10-13" || len(body["days"].([]any)) != 7 {
		t.Fatalf("default should be the last 7 days including today: %d %v", rec.Code, body)
	}
	if !f.reportSince.Equal(time.Date(2026, 10, 7, 0, 0, 0, 0, lagos)) || !f.reportUntil.Equal(time.Date(2026, 10, 14, 0, 0, 0, 0, lagos)) {
		t.Fatalf("query range wrong: %v - %v", f.reportSince, f.reportUntil)
	}
	for _, q := range []string{"from=13-10-2026", "from=2026-10-13&to=2026-10-01", "from=2026-01-01&to=2026-10-13"} {
		if rec, _ := call(t, h, "GET", "/api/reports/flow?"+q, "user-9", ""); rec.Code != 400 {
			t.Errorf("%s: want 400, got %d", q, rec.Code)
		}
	}
}

func TestBuildFlowReport(t *testing.T) {
	at := func(day, h, m int) *time.Time { v := time.Date(2026, 10, day, h, m, 0, 0, lagos); return &v }
	ada := "Dr Ada"
	rows := []store.ReportRow{
		// Oct 11, OPD, ESI 3: waited 20, consulted 15
		{DepartmentName: "OPD", ESI: 3, Status: flow.Completed, CheckedInAt: *at(11, 9, 0), CalledAt: at(11, 9, 20), StartedAt: at(11, 9, 25), CompletedAt: at(11, 9, 40), ClinicianName: &ada},
		// Oct 11, Emergency, ESI 1: started directly after 2 min, still in progress
		{DepartmentName: "Emergency", ESI: 1, Status: flow.InProgress, CheckedInAt: *at(11, 10, 0), StartedAt: at(11, 10, 2)},
		// Oct 12, OPD, ESI 3: cancelled before being seen
		{DepartmentName: "OPD", ESI: 3, Status: flow.Cancelled, CheckedInAt: *at(12, 23, 30)},
	}
	r := buildFlowReport(rows, time.Date(2026, 10, 10, 0, 0, 0, 0, lagos), 3, lagos, [6]int{0, 0, 10, 30, 60, 120})
	if r.From != "2026-10-10" || r.To != "2026-10-12" || len(r.Days) != 3 {
		t.Fatalf("range: %+v", r)
	}
	if r.Days[0].CheckIns != 0 || r.Days[0].AvgWaitMinutes != nil {
		t.Errorf("empty day should be zeros/nulls: %+v", r.Days[0])
	}
	d := r.Days[1]
	if d.CheckIns != 2 || d.Completed != 1 || *d.AvgWaitMinutes != 11 || *d.AvgConsultMinutes != 15 {
		t.Errorf("Oct 11 wrong: %+v (avg wait (20+2)/2 = 11)", d)
	}
	if r.Days[2].Cancelled != 1 || r.Totals.CheckIns != 3 {
		t.Errorf("totals/cancel wrong: %+v %+v", r.Days[2], r.Totals)
	}
	if len(r.ByDepartment) != 2 || r.ByDepartment[0].Department != "Emergency" || r.ByDepartment[1].CheckIns != 2 {
		t.Errorf("byDepartment: %+v", r.ByDepartment)
	}
	if len(r.ByESI) != 2 || r.ByESI[0].ESI != 1 || *r.ByESI[0].AvgWaitMinutes != 2 {
		t.Errorf("byEsi: %+v", r.ByESI)
	}
	// ESI 3 seen after 20 min (target 30): in target. ESI 1 seen after 2 min (target 0): not.
	if *d.SeenWithinTargetPercent != 50 || *d.AvgCallToStartMinutes != 5 {
		t.Errorf("targets / call-to-start: %+v", d)
	}
	if len(r.ByHour) != 24 || r.ByHour[9].CheckIns != 1 || r.ByHour[23].Cancelled != 1 || r.ByHour[3].AvgWaitMinutes != nil {
		t.Errorf("byHour: %+v", r.ByHour[9])
	}
	if len(r.ByWeekday) != 7 || r.ByWeekday[0].Day != "Sun" || r.ByWeekday[0].CheckIns != 2 || r.ByWeekday[1].CheckIns != 1 {
		t.Errorf("byWeekday (Oct 11 2026 is a Sunday): %+v", r.ByWeekday[:2])
	}
	if len(r.ByClinician) != 1 || r.ByClinician[0].Clinician != "Dr Ada" || r.ByClinician[0].Completed != 1 {
		t.Errorf("byClinician: %+v", r.ByClinician)
	}
	if r.Targets["2"] != 10 {
		t.Errorf("targets used: %v", r.Targets)
	}
	raw, _ := json.Marshal(r.Days[1])
	var flat map[string]any
	_ = json.Unmarshal(raw, &flat)
	for _, key := range []string{"date", "checkIns", "completed", "cancelled", "averageWaitMinutes", "averageConsultationMinutes"} {
		if _, ok := flat[key]; !ok {
			t.Errorf("day JSON missing %q: %s", key, raw)
		}
	}
}
