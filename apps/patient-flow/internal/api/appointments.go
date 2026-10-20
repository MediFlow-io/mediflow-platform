package api

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

type appointmentJSON struct {
	ID                    int64   `json:"id"`
	Reference             string  `json:"reference"`
	Patient               int64   `json:"patient"`
	PatientName           string  `json:"patient_name"`
	PatientHospitalNumber string  `json:"patient_hospital_number"`
	Department            int64   `json:"department"`
	DepartmentCode        string  `json:"department_code"`
	DepartmentName        string  `json:"department_name"`
	ScheduledFor          string  `json:"scheduled_for"`
	Date                  string  `json:"date"` // hospital-local, for display and forms
	Time                  string  `json:"time"`
	Reason                string  `json:"reason"`
	Status                string  `json:"status"`
	StaffNote             string  `json:"staff_note"`
	RequestedBy           *string `json:"requested_by"`
	HandledBy             *string `json:"handled_by"`
	Visit                 *int64  `json:"visit"`
	CreatedAt             string  `json:"created_at"`
}

func (s *Server) appointmentOut(a store.Appointment, forPatient bool) appointmentJSON {
	local := a.ScheduledFor.In(s.Loc)
	out := appointmentJSON{
		ID: a.ID, Reference: a.Reference, Patient: a.PatientID, PatientName: a.PatientName,
		PatientHospitalNumber: a.PatientHospitalNumber, Department: a.DepartmentID, DepartmentCode: a.DepartmentCode,
		DepartmentName: a.DepartmentName, ScheduledFor: s.stamp(a.ScheduledFor), Date: local.Format("2006-01-02"),
		Time: local.Format("15:04"), Reason: a.Reason, Status: string(a.Status), StaffNote: a.StaffNote,
		RequestedBy: a.RequestedBy, HandledBy: a.HandledBy, Visit: a.VisitID, CreatedAt: s.stamp(a.CreatedAt),
	}
	if forPatient { // patients don't need staff usernames
		out.RequestedBy, out.HandledBy = nil, nil
	}
	return out
}

func anyone(string) bool { return true }

// parseSlot reads {"date": "YYYY-MM-DD", "time": "HH:MM"} in the hospital's time zone and checks clinic hours.
func (s *Server) parseSlot(fields map[string]json.RawMessage, problems store.ValidationError, required bool) *time.Time {
	var date, clock string
	_, hasDate := fields["date"]
	_, hasTime := fields["time"]
	if !hasDate && !hasTime && !required {
		return nil
	}
	_ = json.Unmarshal(fields["date"], &date)
	_ = json.Unmarshal(fields["time"], &clock)
	t, err := time.ParseInLocation("2006-01-02 15:04", strings.TrimSpace(date)+" "+strings.TrimSpace(clock), s.Loc)
	if err != nil {
		problems["date"] = []string{"Give a date (YYYY-MM-DD) and a time (HH:MM)."}
		return nil
	}
	return &t
}

// checkSlot validates t against the department's schedule (0 = clinic-wide). "" means bookable.
func (s *Server) checkSlot(ctx context.Context, departmentID int64, t time.Time) (string, error) {
	sched, err := s.Store.Schedule(ctx, departmentID, s.Schedule)
	if err != nil {
		return "", err
	}
	return sched.Validate(t, s.Now()), nil
}

func stringField(fields map[string]json.RawMessage, name string, max int, problems store.ValidationError) string {
	var v string
	if raw, ok := fields[name]; ok && string(raw) != "null" {
		if json.Unmarshal(raw, &v) != nil {
			problems[name] = []string{"Not a valid string."}
		}
	}
	v = strings.TrimSpace(v)
	if len([]rune(v)) > max {
		problems[name] = []string{"Ensure this field has no more than " + strconv.Itoa(max) + " characters."}
	}
	return v
}

// GET /api/appointments (staff): ?status=a,b ?department=opd ?patient=12 ?date=YYYY-MM-DD
func (s *Server) listAppointments(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	f := store.AppointmentFilter{Department: q.Get("department")}
	for _, st := range strings.Split(q.Get("status"), ",") {
		if st = strings.TrimSpace(st); st != "" {
			f.Statuses = append(f.Statuses, st)
		}
	}
	if p := q.Get("patient"); p != "" {
		id, err := strconv.ParseInt(p, 10, 64)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, store.ValidationError{"patient": {"A valid integer is required."}})
			return
		}
		f.PatientID = id
	}
	if d := q.Get("date"); d != "" {
		day, err := time.ParseInLocation("2006-01-02", d, s.Loc)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, store.ValidationError{"date": {"Use the format YYYY-MM-DD."}})
			return
		}
		next := day.AddDate(0, 0, 1)
		f.Since, f.Until = &day, &next
	}
	list, err := s.Store.ListAppointments(r.Context(), f)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	out := make([]appointmentJSON, len(list))
	for i, a := range list {
		out[i] = s.appointmentOut(a, false)
	}
	writeJSON(w, http.StatusOK, out)
}

// GET /api/appointments/mine: the caller's own appointments (e.g. the student dashboard).
func (s *Server) myAppointments(w http.ResponseWriter, r *http.Request) {
	user := userFrom(r)
	sched, err := s.Store.Schedule(r.Context(), 0, s.Schedule)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	resp := map[string]any{"linked": false, "schedule": sched.Describe(), "holidays": upcomingHolidays(sched),
		"appointments": []appointmentJSON{}}
	patientID, err := s.Store.PatientIDForUser(r.Context(), user.ID)
	if errors.Is(err, store.ErrNotFound) {
		writeJSON(w, http.StatusOK, resp)
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	list, err := s.Store.ListAppointments(r.Context(), store.AppointmentFilter{PatientID: patientID, NewestFirst: true})
	if err != nil {
		s.fail(w, r, err)
		return
	}
	out := make([]appointmentJSON, len(list))
	for i, a := range list {
		out[i] = s.appointmentOut(a, true)
	}
	resp["linked"], resp["appointments"] = true, out
	writeJSON(w, http.StatusOK, resp)
}

// POST /api/appointments: a patient requests a slot for themselves; staff book one for a patient.
func (s *Server) createAppointment(w http.ResponseWriter, r *http.Request) {
	user := userFrom(r)
	fields, err := decodeFields(r)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	problems := store.ValidationError{}
	in := store.NewAppointment{Status: flow.ApptRequested}
	if flow.CanManageAppointments(user.Role) {
		raw, ok := fields["patient"]
		id, valid := intField(raw)
		if !ok || !valid {
			problems["patient"] = []string{"Choose the patient to book for."}
		}
		in.PatientID, in.Status = id, flow.ApptConfirmed // staff bookings are confirmed straight away
	} else {
		id, err := s.Store.PatientIDForUser(r.Context(), user.ID)
		if errors.Is(err, store.ErrNotFound) {
			detail(w, http.StatusBadRequest, "Your account isn't linked to a health record yet. Ask reception to link it, then try again.")
			return
		}
		if err != nil {
			s.fail(w, r, err)
			return
		}
		in.PatientID = id
	}
	if raw, ok := fields["department"]; !ok {
		problems["department"] = []string{"This field is required."}
	} else if id, valid := intField(raw); !valid {
		problems["department"] = []string{"Incorrect type. Expected pk value."}
	} else {
		in.DepartmentID = id
	}
	in.Reason = stringField(fields, "reason", 300, problems)
	if slot := s.parseSlot(fields, problems, true); slot != nil {
		in.ScheduledFor = *slot
		if in.DepartmentID != 0 {
			msg, err := s.checkSlot(r.Context(), in.DepartmentID, *slot)
			if err != nil {
				s.fail(w, r, err)
				return
			}
			if msg != "" {
				problems["time"] = []string{msg}
			}
		}
	}
	if len(problems) > 0 {
		writeJSON(w, http.StatusBadRequest, problems)
		return
	}
	a, err := s.Store.CreateAppointment(r.Context(), user, in)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusCreated, s.appointmentOut(a, !flow.CanManageAppointments(user.Role)))
}

// POST /api/appointments/{id}/{confirm,decline,cancel,check_in}
func (s *Server) appointmentAction(w http.ResponseWriter, r *http.Request) {
	user := userFrom(r)
	id, ok := pathID(r)
	action := r.PathValue("action")
	if _, known := flow.AppointmentActions[action]; !ok || !known {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	fields := map[string]json.RawMessage{}
	if r.ContentLength != 0 {
		var err error
		if fields, err = decodeFields(r); err != nil {
			s.fail(w, r, err)
			return
		}
	}
	problems := store.ValidationError{}
	up := store.AppointmentUpdate{}
	if _, present := fields["note"]; present {
		note := stringField(fields, "note", 500, problems)
		up.Note = &note
	}
	switch action {
	case "decline":
		if up.Note == nil || *up.Note == "" {
			problems["note"] = []string{"Tell the patient why (e.g. suggest another day)."}
		}
	case "confirm":
		up.ScheduledFor = s.parseSlot(fields, problems, false)
		ctx := r.Context()
		up.SlotAllowed = func(departmentID int64, t time.Time) (string, error) { return s.checkSlot(ctx, departmentID, t) }
	case "check_in":
		in := store.CheckIn{}
		if raw, present := fields["esi"]; !present || string(raw) == "null" {
			problems["esi"] = []string{"This field is required."}
		} else if esi, ok := esiField(raw, problems); ok {
			in.ESI = esi
		}
		in.Vitals, _ = parseVitals(fields, problems)
		up.CheckIn = &in
		up.CheckInAllowed = func(scheduledFor time.Time) string {
			if !s.Schedule.SameDay(scheduledFor, s.Now()) {
				return "This appointment is for " + scheduledFor.In(s.Loc).Format("Mon 2 Jan") + ". Check the patient in as a walk-in instead."
			}
			return ""
		}
	}
	if len(problems) > 0 {
		writeJSON(w, http.StatusBadRequest, problems)
		return
	}
	a, err := s.Store.AppointmentAction(r.Context(), user, id, action, up)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.appointmentOut(a, !flow.CanManageAppointments(user.Role)))
}

type holidayJSON struct {
	Date string `json:"date"`
	Name string `json:"name"`
}

func upcomingHolidays(sched flow.Schedule) []holidayJSON {
	out := []holidayJSON{}
	for day, name := range sched.Holidays {
		out = append(out, holidayJSON{day, name})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Date < out[j].Date })
	return out
}
