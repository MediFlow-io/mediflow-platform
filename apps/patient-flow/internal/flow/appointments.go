package flow

import (
	"fmt"
	"strings"
)

// Appointment statuses match patients_appointment.status.
//
//	requested ──confirm──▶ confirmed ──check_in──▶ checked_in (creates a visit)
//	    │──decline──▶ declined        │
//	    └────────────cancel───────────┴──▶ cancelled
type AppointmentStatus string

const (
	ApptRequested AppointmentStatus = "requested"
	ApptConfirmed AppointmentStatus = "confirmed"
	ApptDeclined  AppointmentStatus = "declined"
	ApptCancelled AppointmentStatus = "cancelled"
	ApptCheckedIn AppointmentStatus = "checked_in"
)

// OpenAppointment statuses still hold a slot.
var OpenAppointment = []AppointmentStatus{ApptRequested, ApptConfirmed}

// MaxOpenAppointmentsPerPatient stops one person filling the calendar.
const MaxOpenAppointmentsPerPatient = 3

// CanManageAppointments: front-desk and clinical staff confirm, decline, book and check in.
func CanManageAppointments(role string) bool { return frontDesk[role] }

// AppointmentAction describes one appointment transition.
type AppointmentAction struct {
	Name string
	From []AppointmentStatus
	To   AppointmentStatus
}

var AppointmentActions = map[string]AppointmentAction{
	"confirm":  {"confirm", []AppointmentStatus{ApptRequested}, ApptConfirmed},
	"decline":  {"decline", []AppointmentStatus{ApptRequested}, ApptDeclined},
	"cancel":   {"cancel", OpenAppointment, ApptCancelled},
	"check_in": {"check_in", []AppointmentStatus{ApptConfirmed}, ApptCheckedIn},
}

// CheckAppointment decides whether an action is allowed. ownsRecord means the caller is the patient
// (their account is linked to the appointment's patient record); patients may only cancel.
func CheckAppointment(action, role string, ownsRecord bool, current AppointmentStatus) (AppointmentAction, error) {
	a, ok := AppointmentActions[action]
	if !ok {
		return a, &Error{404, "Not found."}
	}
	if !CanManageAppointments(role) && !(action == "cancel" && ownsRecord) {
		return a, &Error{403, fmt.Sprintf("Your role cannot %s an appointment.", strings.ReplaceAll(action, "_", " "))}
	}
	for _, from := range a.From {
		if current == from {
			return a, nil
		}
	}
	return a, &Error{409, fmt.Sprintf("Cannot %s an appointment that is %s.", strings.ReplaceAll(action, "_", " "), strings.ReplaceAll(string(current), "_", " "))}
}
