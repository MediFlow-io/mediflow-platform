package flow

import (
	"fmt"
	"strings"
	"time"
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

// Schedule holds the bookable clinic hours, in the hospital's time zone.
type Schedule struct {
	Loc        *time.Location
	Open       time.Duration // offset from midnight, e.g. 8h
	Close      time.Duration // last slot must start before this
	Days       map[time.Weekday]bool
	MaxAhead   time.Duration
	MinNotice  time.Duration
	SlotLength time.Duration // appointments start on these boundaries
}

// DefaultSchedule: weekdays 08:00–16:00, 15-minute slots, up to 60 days ahead, 15 minutes' notice.
func DefaultSchedule(loc *time.Location) Schedule {
	return Schedule{Loc: loc, Open: 8 * time.Hour, Close: 16 * time.Hour,
		Days:     map[time.Weekday]bool{time.Monday: true, time.Tuesday: true, time.Wednesday: true, time.Thursday: true, time.Friday: true},
		MaxAhead: 60 * 24 * time.Hour, MinNotice: 15 * time.Minute, SlotLength: 15 * time.Minute}
}

// ParseSchedule reads hours like "08:00-16:00" and days like "Mon-Fri" or "Mon,Wed,Sat".
func ParseSchedule(loc *time.Location, hours, days string) (Schedule, error) {
	s := DefaultSchedule(loc)
	if hours != "" {
		open, close, ok := strings.Cut(hours, "-")
		o, err1 := time.Parse("15:04", strings.TrimSpace(open))
		c, err2 := time.Parse("15:04", strings.TrimSpace(close))
		if !ok || err1 != nil || err2 != nil || !c.After(o) {
			return s, fmt.Errorf("clinic hours %q: use HH:MM-HH:MM", hours)
		}
		s.Open = time.Duration(o.Hour())*time.Hour + time.Duration(o.Minute())*time.Minute
		s.Close = time.Duration(c.Hour())*time.Hour + time.Duration(c.Minute())*time.Minute
	}
	if days != "" {
		names := []string{"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}
		index := func(n string) int {
			for i, name := range names {
				if strings.EqualFold(name, strings.TrimSpace(n)) {
					return i
				}
			}
			return -1
		}
		s.Days = map[time.Weekday]bool{}
		for _, part := range strings.Split(days, ",") {
			from, to, isRange := strings.Cut(part, "-")
			a, b := index(from), index(to)
			if !isRange {
				b = a
			}
			if a < 0 || b < 0 {
				return s, fmt.Errorf("clinic days %q: use e.g. Mon-Fri or Mon,Wed,Sat", days)
			}
			for d := a; ; d = (d + 1) % 7 {
				s.Days[time.Weekday(d)] = true
				if d == b {
					break
				}
			}
		}
	}
	return s, nil
}

// Describe is a human summary for error messages and the UI.
func (s Schedule) Describe() string {
	clock := func(d time.Duration) string { return fmt.Sprintf("%02d:%02d", int(d.Hours()), int(d.Minutes())%60) }
	var days []string
	for d := time.Sunday; d <= time.Saturday; d++ {
		if s.Days[d] {
			days = append(days, d.String()[:3])
		}
	}
	return fmt.Sprintf("%s, %s–%s", strings.Join(days, " "), clock(s.Open), clock(s.Close))
}

// Validate checks that t is a bookable slot. It returns a message suitable for the user, or "".
func (s Schedule) Validate(t, now time.Time) string {
	local := t.In(s.Loc)
	midnight := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, s.Loc)
	offset := local.Sub(midnight)
	switch {
	case t.Before(now.Add(s.MinNotice)):
		return fmt.Sprintf("Choose a time at least %d minutes from now.", int(s.MinNotice.Minutes()))
	case t.After(now.Add(s.MaxAhead)):
		return fmt.Sprintf("Appointments can be booked up to %d days ahead.", int(s.MaxAhead.Hours()/24))
	case !s.Days[local.Weekday()] || offset < s.Open || offset >= s.Close:
		return "The clinic takes appointments " + s.Describe() + "."
	case s.SlotLength > 0 && offset%s.SlotLength != 0:
		return fmt.Sprintf("Appointments start every %d minutes (e.g. 09:00, 09:15).", int(s.SlotLength.Minutes()))
	}
	return ""
}

// SameDay reports whether two instants fall on the same calendar day in the schedule's time zone.
func (s Schedule) SameDay(a, b time.Time) bool {
	a, b = a.In(s.Loc), b.In(s.Loc)
	return a.Year() == b.Year() && a.YearDay() == b.YearDay()
}
