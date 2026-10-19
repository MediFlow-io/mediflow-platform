package flow

import "math"

// DefaultServiceMinutes is the assumed consultation length when a department has no recent history.
const DefaultServiceMinutes = 15.0

// DeptStats describe how fast a department is seeing patients right now.
type DeptStats struct {
	AvgServiceMinutes float64 // mean consultation length (start → complete) over recent days; 0 = unknown
	ActiveConsults    int     // visits in progress now
	DoctorsOnShift    int     // doctors rostered for this department now (clinic_staffshift)
}

// Servers is how many patients the department can see at once: whoever is consulting now, or the
// rostered doctors if more, and never fewer than one.
func (d DeptStats) Servers() int {
	return max(d.ActiveConsults, d.DoctorsOnShift, 1)
}

// ServiceMinutes is the consultation length used for estimates, kept within sensible bounds so one
// very short or very long visit doesn't swing every estimate.
func (d DeptStats) ServiceMinutes() float64 {
	avg := d.AvgServiceMinutes
	if avg <= 0 {
		avg = DefaultServiceMinutes
	}
	return math.Min(math.Max(avg, 3), 120)
}

// EstimateWaitMinutes estimates how long until a patient with `ahead` people in front of them is called.
// It is a rough guide for patients and staff, never a promise: a more urgent arrival moves ahead.
func EstimateWaitMinutes(ahead int, d DeptStats) int {
	if ahead <= 0 {
		return 0
	}
	return int(math.Ceil(float64(ahead) * d.ServiceMinutes() / float64(d.Servers())))
}

// OverTarget reports whether a patient has waited longer than their ESI level's target.
// targets is indexed by ESI (1..5); index 0 is unused.
func OverTarget(esi, waitedMinutes int, targets [6]int) bool {
	if !ValidESI(esi) {
		return false
	}
	return waitedMinutes > targets[esi]
}

// TriageDirection names an ESI change: a lower number is more urgent.
func TriageDirection(from, to int) string {
	switch {
	case to < from:
		return "escalated"
	case to > from:
		return "de-escalated"
	}
	return "unchanged"
}

// CanTriage: clinical staff may change a waiting patient's triage level.
func CanTriage(role string) bool { return clinical[role] }
