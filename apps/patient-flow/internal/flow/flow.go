// Package flow holds MediFlow's patient-flow rules: who may do what, and how a visit moves
// through its lifecycle. It has no database or HTTP code, so the rules are easy to test and review.
//
//	waiting ──call──▶ called ──start──▶ in_progress ──complete──▶ completed
//	   │                 │                   │
//	   └──────start──────┘                   │
//	   └─────────────cancel──────────────────┴──▶ cancelled
package flow

import "fmt"

// Status values match the core API's patients_visit.status column.
type Status string

const (
	Waiting    Status = "waiting"
	Called     Status = "called"
	InProgress Status = "in_progress"
	Completed  Status = "completed"
	Cancelled  Status = "cancelled"
)

// Active statuses: a patient may have at most one visit in any of these.
var Active = []Status{Waiting, Called, InProgress}

func (s Status) IsActive() bool {
	for _, a := range Active {
		if s == a {
			return true
		}
	}
	return false
}

func (s Status) Label() string {
	switch s {
	case Waiting:
		return "waiting"
	case Called:
		return "called"
	case InProgress:
		return "in progress"
	case Completed:
		return "completed"
	case Cancelled:
		return "cancelled"
	}
	return string(s)
}

// Roles match accounts_user.role.
const (
	Admin     = "admin"
	Doctor    = "doctor"
	Nurse     = "nurse"
	Reception = "reception"
	Lab       = "lab"
	Pharmacy  = "pharmacy"
	IT        = "it"
	Student   = "student"
)

type roleSet map[string]bool

func roles(names ...string) roleSet {
	set := roleSet{}
	for _, n := range names {
		set[n] = true
	}
	return set
}

// Permission sets (mirroring apps/core-api/apps/accounts/permissions.py).
var (
	readVisits = roles(Admin, Doctor, Nurse, Reception, Lab, Pharmacy) // identifiable patient data
	checkIn    = roles(Admin, Doctor, Nurse, Reception)
	editVisits = roles(Admin, Doctor, Reception)
	staff      = roles(Admin, Doctor, Nurse, Reception, Lab, Pharmacy, IT)
	frontDesk  = roles(Admin, Doctor, Nurse, Reception)
	clinical   = roles(Admin, Doctor, Nurse)
)

func CanReadVisits(role string) bool   { return readVisits[role] }
func CanCheckIn(role string) bool      { return checkIn[role] }
func CanEditVisit(role string) bool    { return editVisits[role] }
func CanSeeDashboard(role string) bool { return staff[role] }

// CanSeeReports: multi-day flow reports are for administrators (the admin console).
func CanSeeReports(role string) bool { return role == Admin }

// Transition describes one lifecycle action.
type Transition struct {
	Action    string
	From      []Status
	To        Status
	roles     roleSet
	Timestamp string // patients_visit column stamped with now(), "" for none
}

var Transitions = map[string]Transition{
	"call":     {Action: "call", From: []Status{Waiting}, To: Called, roles: frontDesk, Timestamp: "called_at"},
	"start":    {Action: "start", From: []Status{Waiting, Called}, To: InProgress, roles: clinical, Timestamp: "started_at"},
	"complete": {Action: "complete", From: []Status{InProgress}, To: Completed, roles: clinical, Timestamp: "completed_at"},
	"cancel":   {Action: "cancel", From: Active, To: Cancelled, roles: frontDesk, Timestamp: "completed_at"},
}

// Error carries the HTTP status the API should answer with.
type Error struct {
	Status  int
	Message string
}

func (e *Error) Error() string { return e.Message }

// Check decides whether `role` may apply `action` to a visit currently in `current`.
func Check(action, role string, current Status) (Transition, error) {
	t, ok := Transitions[action]
	if !ok {
		return Transition{}, &Error{404, "Not found."}
	}
	if !t.roles[role] {
		return t, &Error{403, fmt.Sprintf("Your role cannot %s a visit.", action)}
	}
	for _, from := range t.From {
		if current == from {
			return t, nil
		}
	}
	return t, &Error{409, fmt.Sprintf("Cannot %s a visit that is %s.", action, current.Label())}
}

// ValidESI reports whether an Emergency Severity Index level is in range.
func ValidESI(esi int) bool { return esi >= 1 && esi <= 5 }
