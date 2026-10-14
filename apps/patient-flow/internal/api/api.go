// Package api serves patient-flow's HTTP API: visits, the queue, live queue events and the flow
// dashboard. It keeps the contract in docs/api/core.yaml (the same JSON the core API served before
// ownership moved to Go), so the React apps don't change.
package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"mediflow/patient-flow/internal/auth"
	"mediflow/patient-flow/internal/events"
	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

type Store interface {
	Ping(ctx context.Context) error
	UserByID(ctx context.Context, id int64) (store.User, error)
	ListVisits(ctx context.Context, f store.VisitFilter) ([]store.Visit, error)
	GetVisit(ctx context.Context, id int64) (store.Visit, error)
	CheckIn(ctx context.Context, actor store.User, in store.CheckIn) (store.Visit, error)
	UpdateVisit(ctx context.Context, actor store.User, id int64, p store.VisitPatch) (store.Visit, error)
	Transition(ctx context.Context, actor store.User, id int64, action string) (store.Visit, error)
	DashboardData(ctx context.Context, since, until time.Time) (today, active []store.DashboardRow, err error)
	ReportRows(ctx context.Context, since, until time.Time) ([]store.ReportRow, error)
}

type TokenVerifier interface {
	Verify(ctx context.Context, token string) (*auth.Claims, error)
}

type Server struct {
	Store     Store
	Tokens    TokenVerifier
	Hub       *events.Hub
	Loc       *time.Location // hospital time zone: "today" and HH:MM are local
	Log       *slog.Logger
	Now       func() time.Time
	Heartbeat time.Duration // keep-alive interval for the event stream
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.health)
	mux.Handle("GET /api/visits", s.authed(flow.CanReadVisits, s.listVisits))
	mux.Handle("POST /api/visits", s.authed(flow.CanCheckIn, s.checkIn))
	mux.Handle("GET /api/visits/{id}", s.authed(flow.CanReadVisits, s.getVisit))
	mux.Handle("PATCH /api/visits/{id}", s.authed(flow.CanEditVisit, s.updateVisit))
	// Per-action role rules live in flow.Check; any check-in role may reach the route.
	mux.Handle("POST /api/visits/{id}/{action}", s.authed(flow.CanCheckIn, s.transition))
	mux.Handle("GET /api/queue", s.authed(flow.CanReadVisits, s.queue))
	mux.Handle("GET /api/queue/events", s.authed(flow.CanReadVisits, s.queueEvents))
	mux.Handle("GET /api/dashboard", s.authed(flow.CanSeeDashboard, s.dashboard))
	mux.Handle("GET /api/reports/flow", s.authed(flow.CanSeeReports, s.flowReport))
	return s.recoverer(s.logRequests(mux))
}

// ---------------------------------------------------------------- responses

type errorBody struct {
	Detail string `json:"detail"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func detail(w http.ResponseWriter, status int, msg string) { writeJSON(w, status, errorBody{msg}) }

func (s *Server) fail(w http.ResponseWriter, r *http.Request, err error) {
	var fe *flow.Error
	var ve store.ValidationError
	switch {
	case errors.Is(err, store.ErrNotFound):
		detail(w, http.StatusNotFound, "Not found.")
	case errors.As(err, &fe):
		detail(w, fe.Status, fe.Message)
	case errors.As(err, &ve):
		writeJSON(w, http.StatusBadRequest, ve)
	default:
		s.Log.Error("request failed", "path", r.URL.Path, "error", err)
		detail(w, http.StatusInternalServerError, "Something went wrong. Please try again.")
	}
}

// ---------------------------------------------------------------- middleware

type ctxKey struct{}

func userFrom(r *http.Request) store.User { return r.Context().Value(ctxKey{}).(store.User) }

// authed verifies the bearer token, then re-reads the user from the database so a deactivated
// account or a changed role takes effect immediately (the token's role claim may be minutes old).
func (s *Server) authed(allowed func(role string) bool, next http.HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok || raw == "" {
			detail(w, http.StatusUnauthorized, "Authentication credentials were not provided.")
			return
		}
		claims, err := s.Tokens.Verify(r.Context(), raw)
		if err != nil {
			detail(w, http.StatusUnauthorized, "Token is invalid or expired.")
			return
		}
		id, err := strconv.ParseInt(claims.UserID, 10, 64)
		if err != nil {
			detail(w, http.StatusUnauthorized, "Token is invalid or expired.")
			return
		}
		user, err := s.Store.UserByID(r.Context(), id)
		if errors.Is(err, store.ErrNotFound) || (err == nil && !user.Active) {
			detail(w, http.StatusUnauthorized, "User not found or inactive.")
			return
		}
		if err != nil {
			s.fail(w, r, err)
			return
		}
		if !allowed(user.Role) {
			detail(w, http.StatusForbidden, "You do not have permission to perform this action.")
			return
		}
		next(w, r.WithContext(context.WithValue(r.Context(), ctxKey{}, user)))
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) { r.status = code; r.ResponseWriter.WriteHeader(code) }
func (r *statusRecorder) Flush() {
	if f, ok := r.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// logRequests writes one structured line per request. Bodies are never logged: they hold patient data.
func (s *Server) logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		s.Log.Info("request", "method", r.Method, "path", r.URL.Path, "status", rec.status,
			"ms", float64(time.Since(start).Microseconds())/1000)
	})
}

func (s *Server) recoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if v := recover(); v != nil {
				s.Log.Error("panic", "path", r.URL.Path, "panic", fmt.Sprint(v))
				detail(w, http.StatusInternalServerError, "Something went wrong. Please try again.")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// ---------------------------------------------------------------- JSON shapes

type visitJSON struct {
	ID                    int64   `json:"id"`
	VisitNumber           string  `json:"visit_number"`
	Patient               int64   `json:"patient"`
	PatientName           string  `json:"patient_name"`
	PatientHospitalNumber string  `json:"patient_hospital_number"`
	Department            int64   `json:"department"`
	DepartmentCode        string  `json:"department_code"`
	DepartmentName        string  `json:"department_name"`
	ESI                   int     `json:"esi"`
	Status                string  `json:"status"`
	ArrivalMode           string  `json:"arrival_mode"`
	CheckedInAt           string  `json:"checked_in_at"`
	CalledAt              *string `json:"called_at"`
	StartedAt             *string `json:"started_at"`
	CompletedAt           *string `json:"completed_at"`
	AssignedClinician     *int64  `json:"assigned_clinician"`
	AssignedClinicianName *string `json:"assigned_clinician_name"`
}

// stamp formats like Django REST Framework: local time with offset and microseconds.
func (s *Server) stamp(t time.Time) string {
	return t.In(s.Loc).Format("2006-01-02T15:04:05.999999-07:00")
}

func (s *Server) stampPtr(t *time.Time) *string {
	if t == nil {
		return nil
	}
	v := s.stamp(*t)
	return &v
}

func (s *Server) visitOut(v store.Visit) visitJSON {
	return visitJSON{
		ID: v.ID, VisitNumber: v.Number, Patient: v.PatientID, PatientName: v.PatientName,
		PatientHospitalNumber: v.PatientHospitalNumber, Department: v.DepartmentID,
		DepartmentCode: v.DepartmentCode, DepartmentName: v.DepartmentName, ESI: v.ESI,
		Status: string(v.Status), ArrivalMode: v.ArrivalMode, CheckedInAt: s.stamp(v.CheckedInAt),
		CalledAt: s.stampPtr(v.CalledAt), StartedAt: s.stampPtr(v.StartedAt), CompletedAt: s.stampPtr(v.CompletedAt),
		AssignedClinician: v.ClinicianID, AssignedClinicianName: v.ClinicianName,
	}
}

func (s *Server) today() (time.Time, time.Time) {
	now := s.Now().In(s.Loc)
	start := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, s.Loc)
	return start, start.AddDate(0, 0, 1)
}

func minutesBetween(from, to time.Time) int {
	if m := int(to.Sub(from) / time.Minute); m > 0 {
		return m
	}
	return 0
}

// ---------------------------------------------------------------- handlers

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err := s.Store.Ping(ctx); err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "unavailable"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func pathID(r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	return id, err == nil && id > 0
}

func (s *Server) listVisits(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	f := store.VisitFilter{Department: q.Get("department")}
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
	if q.Get("today") == "true" {
		since, until := s.today()
		f.Since, f.Until = &since, &until
	}
	visits, err := s.Store.ListVisits(r.Context(), f)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	out := make([]visitJSON, len(visits))
	for i, v := range visits {
		out[i] = s.visitOut(v)
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) getVisit(w http.ResponseWriter, r *http.Request) {
	id, ok := pathID(r)
	if !ok {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	v, err := s.Store.GetVisit(r.Context(), id)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.visitOut(v))
}

// decodeFields reads a JSON object, keeping raw values so missing vs null vs wrong type can be told apart.
func decodeFields(r *http.Request) (map[string]json.RawMessage, error) {
	var fields map[string]json.RawMessage
	r.Body = http.MaxBytesReader(nil, r.Body, 64<<10)
	if err := json.NewDecoder(r.Body).Decode(&fields); err != nil || fields == nil {
		return nil, store.ValidationError{"non_field_errors": {"Request body must be a JSON object."}}
	}
	return fields, nil
}

// intField parses an integer that may arrive as a number or a numeric string (as DRF accepts).
func intField(raw json.RawMessage) (int64, bool) {
	var n json.Number
	if json.Unmarshal(raw, &n) == nil {
		v, err := n.Int64()
		return v, err == nil
	}
	var s string
	if json.Unmarshal(raw, &s) == nil {
		v, err := strconv.ParseInt(strings.TrimSpace(s), 10, 64)
		return v, err == nil
	}
	return 0, false
}

func (s *Server) checkIn(w http.ResponseWriter, r *http.Request) {
	fields, err := decodeFields(r)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	in := store.CheckIn{}
	problems := store.ValidationError{}
	for name, dest := range map[string]*int64{"patient": &in.PatientID, "department": &in.DepartmentID} {
		raw, present := fields[name]
		if !present || string(raw) == "null" {
			problems[name] = []string{"This field is required."}
		} else if v, ok := intField(raw); !ok {
			problems[name] = []string{"Incorrect type. Expected pk value."}
		} else {
			*dest = v
		}
	}
	if raw, present := fields["esi"]; !present || string(raw) == "null" {
		problems["esi"] = []string{"This field is required."}
	} else if v, ok := intField(raw); !ok {
		problems["esi"] = []string{"A valid integer is required."}
	} else {
		in.ESI = int(v)
	}
	if raw, present := fields["arrival_mode"]; present {
		_ = json.Unmarshal(raw, &in.ArrivalMode)
	}
	if len(problems) > 0 {
		writeJSON(w, http.StatusBadRequest, problems)
		return
	}
	v, err := s.Store.CheckIn(r.Context(), userFrom(r), in)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusCreated, s.visitOut(v))
}

func (s *Server) updateVisit(w http.ResponseWriter, r *http.Request) {
	id, ok := pathID(r)
	if !ok {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	fields, err := decodeFields(r)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	var p store.VisitPatch
	problems := store.ValidationError{}
	if raw, ok := fields["patient"]; ok {
		if current, err := s.Store.GetVisit(r.Context(), id); err == nil {
			if v, ok := intField(raw); !ok || v != current.PatientID {
				problems["patient"] = []string{"A visit can't be moved to another patient. Cancel it and check the right patient in."}
			}
		}
	}
	if raw, ok := fields["esi"]; ok {
		if v, ok := intField(raw); ok {
			esi := int(v)
			p.ESI = &esi
		} else {
			problems["esi"] = []string{"A valid integer is required."}
		}
	}
	if raw, ok := fields["department"]; ok {
		if v, ok := intField(raw); ok {
			p.DepartmentID = &v
		} else {
			problems["department"] = []string{"Incorrect type. Expected pk value."}
		}
	}
	if raw, ok := fields["arrival_mode"]; ok {
		var mode string
		if json.Unmarshal(raw, &mode) == nil && mode != "" && len(mode) <= 32 {
			p.ArrivalMode = &mode
		} else {
			problems["arrival_mode"] = []string{"Enter a short arrival mode such as walk_in."}
		}
	}
	if raw, ok := fields["assigned_clinician"]; ok {
		var clinician *int64
		if string(raw) != "null" {
			v, ok := intField(raw)
			if !ok {
				problems["assigned_clinician"] = []string{"Incorrect type. Expected pk value."}
			}
			clinician = &v
		}
		p.ClinicianID = &clinician
	}
	// status, timestamps and visit_number are read-only and ignored, as before.
	if len(problems) > 0 {
		writeJSON(w, http.StatusBadRequest, problems)
		return
	}
	v, err := s.Store.UpdateVisit(r.Context(), userFrom(r), id, p)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.visitOut(v))
}

func (s *Server) transition(w http.ResponseWriter, r *http.Request) {
	id, ok := pathID(r)
	action := r.PathValue("action")
	if _, known := flow.Transitions[action]; !ok || !known {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	v, err := s.Store.Transition(r.Context(), userFrom(r), id, action)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.visitOut(v))
}

type queueEntry struct {
	ID             int64  `json:"id"`
	VisitID        string `json:"visitId"`
	PatientID      int64  `json:"patientId"`
	FullName       string `json:"fullName"`
	HospitalNumber string `json:"hospitalNumber"`
	Department     string `json:"department"`
	Priority       int    `json:"priority"`
	Status         string `json:"status"`
	Position       int    `json:"position"`
	Arrival        string `json:"arrival"`
	WaitingMinutes int    `json:"waitingMinutes"`
	Wait           string `json:"wait"`
}

func (s *Server) queue(w http.ResponseWriter, r *http.Request) {
	visits, err := s.Store.ListVisits(r.Context(), store.VisitFilter{
		Statuses: []string{string(flow.Waiting)}, Department: r.URL.Query().Get("department")})
	if err != nil {
		s.fail(w, r, err)
		return
	}
	now := s.Now()
	out := make([]queueEntry, len(visits))
	for i, v := range visits {
		waited := minutesBetween(v.CheckedInAt, now)
		label := "Waiting"
		if v.ESI <= 2 {
			label = "Urgent"
		}
		out[i] = queueEntry{
			ID: v.ID, VisitID: v.Number, PatientID: v.PatientID, FullName: v.PatientName,
			HospitalNumber: v.PatientHospitalNumber, Department: v.DepartmentCode, Priority: v.ESI,
			Status: label, Position: i + 1, Arrival: v.CheckedInAt.In(s.Loc).Format("15:04"),
			WaitingMinutes: waited, Wait: fmt.Sprintf("%d min", waited),
		}
	}
	writeJSON(w, http.StatusOK, out)
}

// queueEvents streams visit changes as Server-Sent Events. Clients refetch the queue on each event.
// It needs an Authorization header (use fetch with a stream reader rather than EventSource): tokens
// must never go in URLs, where proxies log them.
func (s *Server) queueEvents(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		detail(w, http.StatusInternalServerError, "Streaming is not supported.")
		return
	}
	h := w.Header()
	h.Set("Content-Type", "text/event-stream")
	h.Set("Cache-Control", "no-cache")
	h.Set("X-Accel-Buffering", "no") // tell Nginx not to buffer the stream
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, ": connected\n\n")
	flusher.Flush()

	events, stop := s.Hub.Subscribe()
	defer stop()
	beat := s.Heartbeat
	if beat <= 0 {
		beat = 25 * time.Second
	}
	ticker := time.NewTicker(beat)
	defer ticker.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case payload, open := <-events:
			if !open {
				return
			}
			fmt.Fprintf(w, "event: visit\ndata: %s\n\n", payload)
			flusher.Flush()
		case <-ticker.C:
			fmt.Fprint(w, ": ping\n\n")
			flusher.Flush()
		}
	}
}

type departmentCount struct {
	Name  string `json:"department__name"`
	Total int    `json:"total"`
}

func (s *Server) dashboard(w http.ResponseWriter, r *http.Request) {
	since, until := s.today()
	today, active, err := s.Store.DashboardData(r.Context(), since, until)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, buildDashboard(today, active, s.Now()))
}

// buildDashboard computes the same numbers the core API used to: today's visits plus whatever is
// active right now (a patient can still be waiting from yesterday).
func buildDashboard(today, active []store.DashboardRow, now time.Time) map[string]any {
	patients := map[int64]bool{}
	byDept := map[string]int{}
	byStatus := map[string]int{}
	completed, waitSum, waitCount := 0, 0, 0
	for _, v := range today {
		patients[v.PatientID] = true
		byDept[v.DepartmentName]++
		byStatus[string(v.Status)]++
		if v.Status == flow.Completed {
			completed++
		}
		seen := v.CalledAt
		if seen == nil {
			seen = v.StartedAt
		}
		if seen != nil {
			waitSum += minutesBetween(v.CheckedInAt, *seen)
			waitCount++
		}
	}
	waiting, inConsultation, emergencies := 0, 0, 0
	var oldest *time.Time
	for i, v := range active {
		switch v.Status {
		case flow.Waiting:
			waiting++
			if v.ESI <= 2 {
				emergencies++
			}
			if oldest == nil || v.CheckedInAt.Before(*oldest) {
				oldest = &active[i].CheckedInAt
			}
		case flow.InProgress:
			inConsultation++
		}
	}
	depts := make([]departmentCount, 0, len(byDept))
	for name, total := range byDept {
		depts = append(depts, departmentCount{name, total})
	}
	sort.Slice(depts, func(i, j int) bool { return depts[i].Name < depts[j].Name })

	var avg, longest any
	if waitCount > 0 {
		// Round half to even, matching Python's round() in the previous implementation.
		avg = int(math.RoundToEven(float64(waitSum) / float64(waitCount)))
	}
	if oldest != nil {
		longest = minutesBetween(*oldest, now)
	}
	return map[string]any{
		"patientsToday":             len(patients),
		"currentlyWaiting":          waiting,
		"inConsultation":            inConsultation,
		"completedToday":            completed,
		"emergencyCases":            emergencies,
		"averageWaitMinutes":        avg,
		"longestCurrentWaitMinutes": longest,
		"byDepartment":              depts,
		"byStatus":                  byStatus,
	}
}
