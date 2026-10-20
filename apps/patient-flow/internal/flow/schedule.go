package flow

import (
	"fmt"
	"strings"
	"time"
)

// Window is one day's bookable hours, as offsets from midnight. The last slot starts before Close.
type Window struct {
	Open, Close time.Duration
}

// Schedule holds the bookable clinic hours, in the hospital's time zone. A weekday missing from Hours
// is closed. The admin console sets hours and holidays (clinic_* tables); CLINIC_HOURS/CLINIC_DAYS are
// the fallback until it does.
type Schedule struct {
	Loc        *time.Location
	Hours      map[time.Weekday]Window
	Holidays   map[string]string // "2006-01-02" → name
	MaxAhead   time.Duration
	MinNotice  time.Duration
	SlotLength time.Duration // appointments start on these boundaries
}

// DefaultSchedule: weekdays 08:00–16:00, 15-minute slots, up to 60 days ahead, 15 minutes' notice.
func DefaultSchedule(loc *time.Location) Schedule {
	s := Schedule{Loc: loc, Hours: map[time.Weekday]Window{}, MaxAhead: 60 * 24 * time.Hour,
		MinNotice: 15 * time.Minute, SlotLength: 15 * time.Minute}
	for d := time.Monday; d <= time.Friday; d++ {
		s.Hours[d] = Window{8 * time.Hour, 16 * time.Hour}
	}
	return s
}

// ParseSchedule reads hours like "08:00-16:00" and days like "Mon-Fri" or "Mon,Wed,Sat".
func ParseSchedule(loc *time.Location, hours, days string) (Schedule, error) {
	s := DefaultSchedule(loc)
	window := Window{8 * time.Hour, 16 * time.Hour}
	if hours != "" {
		open, close, ok := strings.Cut(hours, "-")
		o, err1 := ParseClock(open)
		c, err2 := ParseClock(close)
		if !ok || err1 != nil || err2 != nil || c <= o {
			return s, fmt.Errorf("clinic hours %q: use HH:MM-HH:MM", hours)
		}
		window = Window{o, c}
	}
	selected := map[time.Weekday]bool{}
	for d := range s.Hours {
		selected[d] = true
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
		selected = map[time.Weekday]bool{}
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
				selected[time.Weekday(d)] = true
				if d == b {
					break
				}
			}
		}
	}
	s.Hours = map[time.Weekday]Window{}
	for d := range selected {
		s.Hours[d] = window
	}
	return s, nil
}

// ParseClock reads "HH:MM" or "HH:MM:SS" as an offset from midnight.
func ParseClock(v string) (time.Duration, error) {
	v = strings.TrimSpace(v)
	layout := "15:04"
	if strings.Count(v, ":") == 2 {
		layout = "15:04:05"
	}
	t, err := time.Parse(layout, v)
	if err != nil {
		return 0, err
	}
	return time.Duration(t.Hour())*time.Hour + time.Duration(t.Minute())*time.Minute + time.Duration(t.Second())*time.Second, nil
}

func clock(d time.Duration) string {
	return fmt.Sprintf("%02d:%02d", int(d.Hours()), int(d.Minutes())%60)
}

// Describe is a human summary for error messages and the UI, e.g. "Mon Tue Wed Thu, 08:00–16:00; Fri, 08:00–12:00".
func (s Schedule) Describe() string {
	var groups []string
	var order []Window
	days := map[Window][]string{}
	for d := time.Sunday; d <= time.Saturday; d++ {
		w, open := s.Hours[d]
		if !open {
			continue
		}
		if _, seen := days[w]; !seen {
			order = append(order, w)
		}
		days[w] = append(days[w], d.String()[:3])
	}
	for _, w := range order {
		groups = append(groups, fmt.Sprintf("%s, %s–%s", strings.Join(days[w], " "), clock(w.Open), clock(w.Close)))
	}
	if len(groups) == 0 {
		return "no hours set"
	}
	return strings.Join(groups, "; ")
}

// Validate checks that t is a bookable slot. It returns a message suitable for the user, or "".
func (s Schedule) Validate(t, now time.Time) string {
	local := t.In(s.Loc)
	midnight := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, s.Loc)
	offset := local.Sub(midnight)
	window, open := s.Hours[local.Weekday()]
	switch {
	case t.Before(now.Add(s.MinNotice)):
		return fmt.Sprintf("Choose a time at least %d minutes from now.", int(s.MinNotice.Minutes()))
	case t.After(now.Add(s.MaxAhead)):
		return fmt.Sprintf("Appointments can be booked up to %d days ahead.", int(s.MaxAhead.Hours()/24))
	case s.Holidays[local.Format("2006-01-02")] != "":
		return fmt.Sprintf("The clinic is closed on %s (%s).", local.Format("Mon 2 Jan"), s.Holidays[local.Format("2006-01-02")])
	case !open || offset < window.Open || offset >= window.Close:
		return "The clinic takes appointments " + s.Describe() + "."
	case s.SlotLength > 0 && offset%s.SlotLength != 0:
		return fmt.Sprintf("Appointments start every %d minutes (e.g. 09:00, 09:%02d).", int(s.SlotLength.Minutes()), int(s.SlotLength.Minutes())%60)
	}
	return ""
}

// SameDay reports whether two instants fall on the same calendar day in the schedule's time zone.
func (s Schedule) SameDay(a, b time.Time) bool {
	a, b = a.In(s.Loc), b.In(s.Loc)
	return a.Year() == b.Year() && a.YearDay() == b.YearDay()
}
