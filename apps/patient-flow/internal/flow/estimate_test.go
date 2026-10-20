package flow

import "testing"

func TestEstimateWaitMinutes(t *testing.T) {
	cases := []struct {
		name  string
		ahead int
		stats DeptStats
		want  int
	}{
		{"next in line", 0, DeptStats{AvgServiceMinutes: 20}, 0},
		{"no history uses the default", 2, DeptStats{}, 30},
		{"one clinician", 3, DeptStats{AvgServiceMinutes: 12, ActiveConsults: 1}, 36},
		{"two clinicians halve it", 3, DeptStats{AvgServiceMinutes: 12, ActiveConsults: 2}, 18},
		{"rostered doctors count when idle", 4, DeptStats{AvgServiceMinutes: 10, DoctorsOnShift: 4}, 10},
		{"tiny averages are floored", 2, DeptStats{AvgServiceMinutes: 0.5}, 6},
		{"huge averages are capped", 1, DeptStats{AvgServiceMinutes: 600}, 120},
		{"rounds up", 1, DeptStats{AvgServiceMinutes: 10, ActiveConsults: 3}, 4},
	}
	for _, c := range cases {
		if got := EstimateWaitMinutes(c.ahead, c.stats); got != c.want {
			t.Errorf("%s: got %d, want %d", c.name, got, c.want)
		}
	}
}

func TestOverTargetAndDirection(t *testing.T) {
	targets := [6]int{0, 0, 10, 30, 60, 120}
	if OverTarget(1, 0, targets) || !OverTarget(1, 1, targets) {
		t.Error("ESI 1 is due immediately")
	}
	if OverTarget(3, 30, targets) || !OverTarget(3, 31, targets) || OverTarget(9, 500, targets) {
		t.Error("ESI 3 target is 30 minutes; invalid ESI is never over")
	}
	if TriageDirection(3, 2) != "escalated" || TriageDirection(2, 4) != "de-escalated" || TriageDirection(3, 3) != "unchanged" {
		t.Error("direction")
	}
	if !CanTriage(Nurse) || CanTriage(Reception) || CanTriage(Student) {
		t.Error("only clinical staff change triage")
	}
}
