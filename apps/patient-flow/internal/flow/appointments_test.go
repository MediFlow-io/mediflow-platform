package flow

import (
	"testing"
	"time"
)

var lagos, _ = time.LoadLocation("Africa/Lagos")

// Tuesday 13 Oct 2026, 10:00 in Lagos.
var tue = time.Date(2026, 10, 13, 10, 0, 0, 0, lagos)

func TestAppointmentTransitions(t *testing.T) {
	cases := []struct {
		action, role string
		owns         bool
		from         AppointmentStatus
		want         int
	}{
		{"confirm", Reception, false, ApptRequested, 0},
		{"confirm", Reception, false, ApptConfirmed, 409},
		{"decline", Nurse, false, ApptRequested, 0},
		{"check_in", Reception, false, ApptConfirmed, 0},
		{"check_in", Reception, false, ApptRequested, 409},
		{"cancel", Student, true, ApptConfirmed, 0},    // patients may cancel their own
		{"cancel", Student, false, ApptConfirmed, 403}, // ...but not someone else's
		{"confirm", Student, true, ApptRequested, 403}, // ...and can't confirm
		{"cancel", Lab, false, ApptRequested, 403},
		{"cancel", Admin, false, ApptCheckedIn, 409},
		{"reschedule", Admin, false, ApptRequested, 404},
	}
	for _, c := range cases {
		_, err := CheckAppointment(c.action, c.role, c.owns, c.from)
		if got := status(err); got != c.want {
			t.Errorf("%s by %s (owns=%v) from %s: got %d, want %d (%v)", c.action, c.role, c.owns, c.from, got, c.want, err)
		}
	}
	_, err := CheckAppointment("check_in", Admin, false, ApptCheckedIn)
	if err.Error() != "Cannot check in an appointment that is checked in." {
		t.Fatalf("message: %q", err)
	}
}

func TestScheduleValidate(t *testing.T) {
	s := DefaultSchedule(lagos)
	at := func(day, h, m int) time.Time { return time.Date(2026, 10, day, h, m, 0, 0, lagos) }
	cases := map[string]struct {
		when time.Time
		ok   bool
	}{
		"tomorrow 09:00":        {at(14, 9, 0), true},
		"today 10:15":           {at(13, 10, 15), true},
		"too soon (10:05)":      {at(13, 10, 5), false},
		"in the past":           {at(12, 9, 0), false},
		"before opening":        {at(14, 7, 45), false},
		"at closing time":       {at(14, 16, 0), false},
		"Saturday":              {at(17, 10, 0), false},
		"off-slot 09:10":        {at(14, 9, 10), false},
		"61 days ahead":         {tue.AddDate(0, 0, 61), false},
		"other zone, same slot": {time.Date(2026, 10, 14, 8, 0, 0, 0, time.UTC), true}, // 09:00 Lagos
	}
	for name, c := range cases {
		if msg := s.Validate(c.when, tue); (msg == "") != c.ok {
			t.Errorf("%s: ok=%v, message %q", name, c.ok, msg)
		}
	}
	if msg := s.Validate(at(17, 10, 0), tue); msg != "The clinic takes appointments Mon Tue Wed Thu Fri, 08:00–16:00." {
		t.Errorf("unexpected message %q", msg)
	}
}

func TestParseSchedule(t *testing.T) {
	s, err := ParseSchedule(lagos, "09:30-13:00", "Mon,Wed,Sat")
	if err != nil {
		t.Fatal(err)
	}
	if s.Describe() != "Mon Wed Sat, 09:30–13:00" {
		t.Fatalf("got %q", s.Describe())
	}
	if s, _ := ParseSchedule(lagos, "", "Fri-Mon"); s.Describe() != "Sun Mon Fri Sat, 08:00–16:00" {
		t.Fatalf("wrap-around range: %q", s.Describe())
	}
	for _, bad := range [][2]string{{"9-5", ""}, {"16:00-08:00", ""}, {"", "Mon-Funday"}} {
		if _, err := ParseSchedule(lagos, bad[0], bad[1]); err == nil {
			t.Errorf("%v should be rejected", bad)
		}
	}
	if !DefaultSchedule(lagos).SameDay(time.Date(2026, 10, 13, 23, 30, 0, 0, time.UTC), time.Date(2026, 10, 14, 1, 0, 0, 0, lagos)) {
		t.Error("23:30 UTC is 00:30 the next day in Lagos")
	}
}

func TestScheduleWithPerDayHoursAndHolidays(t *testing.T) {
	s := DefaultSchedule(lagos)
	s.Hours[time.Friday] = Window{8 * time.Hour, 12 * time.Hour}
	s.Holidays = map[string]string{"2026-10-15": "Founders Day"}
	if s.Describe() != "Mon Tue Wed Thu, 08:00–16:00; Fri, 08:00–12:00" {
		t.Fatalf("got %q", s.Describe())
	}
	at := func(day, h, m int) time.Time { return time.Date(2026, 10, day, h, m, 0, 0, lagos) }
	if msg := s.Validate(at(16, 13, 0), tue); msg == "" {
		t.Error("Friday afternoon is closed")
	}
	if msg := s.Validate(at(16, 11, 45), tue); msg != "" {
		t.Errorf("Friday morning is open: %q", msg)
	}
	if msg := s.Validate(at(15, 9, 0), tue); msg != "The clinic is closed on Thu 15 Oct (Founders Day)." {
		t.Errorf("holiday: %q", msg)
	}
	if (Schedule{Loc: lagos}).Describe() != "no hours set" {
		t.Error("empty schedule")
	}
	if d, err := ParseClock("08:30:00"); err != nil || d != 8*time.Hour+30*time.Minute {
		t.Errorf("ParseClock: %v %v", d, err)
	}
}
