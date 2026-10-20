// Package store is patient-flow's PostgreSQL access. It reads and writes the tables created by the
// core API's Django migrations (see docs/handbook/decisions/ADR-0002); it never changes the schema.
package store

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"mediflow/patient-flow/internal/flow"
)

// NotifyChannel is the PostgreSQL channel visit changes are published on (after commit).
const NotifyChannel = "mediflow_visits"

var ErrNotFound = errors.New("not found")

// ValidationError maps field names to messages, like Django REST Framework's 400 responses.
type ValidationError map[string][]string

func (v ValidationError) Error() string {
	return fmt.Sprintf("invalid input: %v", map[string][]string(v))
}

type User struct {
	ID          int64
	Username    string
	DisplayName string
	Role        string
	Active      bool
}

// Vitals are the triage observations recorded at check-in.
type Vitals struct {
	Complaint    string
	PainScore    *int
	HeartRate    *int
	RespRate     *int
	SpO2         *int
	TemperatureC *float64
	SystolicBP   *int
	AVPU         string // "", A, V, P or U
}

type Visit struct {
	ID                    int64
	Number                string
	PatientID             int64
	PatientName           string
	PatientHospitalNumber string
	DepartmentID          int64
	DepartmentCode        string
	DepartmentName        string
	ESI                   int
	Status                flow.Status
	ArrivalMode           string
	CheckedInAt           time.Time
	CalledAt              *time.Time
	StartedAt             *time.Time
	CompletedAt           *time.Time
	ClinicianID           *int64
	ClinicianName         *string
	Vitals                Vitals
}

type VisitFilter struct {
	Statuses   []string
	Department string // department code
	PatientID  int64
	Since      *time.Time // checked in at or after
	Until      *time.Time // checked in before
}

type CheckIn struct {
	PatientID    int64
	DepartmentID int64
	ESI          int
	ArrivalMode  string
	Vitals       Vitals
}

// VisitPatch holds the editable fields. Nil means "leave unchanged".
type VisitPatch struct {
	ESI          *int
	ESIReason    string // optional, kept with the triage change
	DepartmentID *int64
	ArrivalMode  *string
	ClinicianID  **int64 // non-nil pointer to nil = unassign
	Vitals       *Vitals // non-nil = replace the recorded complaint and vitals
}

// Event is published on NotifyChannel and streamed to live clients.
type Event struct {
	VisitID       int64  `json:"visitId,omitempty"`
	AppointmentID int64  `json:"appointmentId,omitempty"`
	Action        string `json:"action"`
	Status        string `json:"status"`
	Department    string `json:"department"`
}

type Store struct{ pool *pgxpool.Pool }

func New(pool *pgxpool.Pool) *Store { return &Store{pool: pool} }

func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

func (s *Store) UserByID(ctx context.Context, id int64) (User, error) {
	var u User
	err := s.pool.QueryRow(ctx,
		`SELECT id, username, display_name, role, is_active FROM accounts_user WHERE id = $1`, id,
	).Scan(&u.ID, &u.Username, &u.DisplayName, &u.Role, &u.Active)
	if errors.Is(err, pgx.ErrNoRows) {
		return u, ErrNotFound
	}
	return u, err
}

const visitSelect = `
SELECT v.id, v.visit_number, v.patient_id, p.full_name, p.hospital_number,
       v.department_id, d.code, d.name, v.esi, v.status, v.arrival_mode,
       v.checked_in_at, v.called_at, v.started_at, v.completed_at, v.assigned_clinician_id,
       CASE WHEN u.id IS NULL THEN NULL ELSE COALESCE(NULLIF(u.display_name, ''), u.username) END,
       v.chief_complaint, v.pain_score, v.heart_rate, v.resp_rate, v.spo2, v.temperature_c::float8, v.systolic_bp, v.avpu
FROM patients_visit v
JOIN patients_patient p ON p.id = v.patient_id
JOIN patients_department d ON d.id = v.department_id
LEFT JOIN accounts_user u ON u.id = v.assigned_clinician_id`

func scanVisit(row pgx.Row) (Visit, error) {
	var v Visit
	var status string
	err := row.Scan(&v.ID, &v.Number, &v.PatientID, &v.PatientName, &v.PatientHospitalNumber,
		&v.DepartmentID, &v.DepartmentCode, &v.DepartmentName, &v.ESI, &status, &v.ArrivalMode,
		&v.CheckedInAt, &v.CalledAt, &v.StartedAt, &v.CompletedAt, &v.ClinicianID, &v.ClinicianName,
		&v.Vitals.Complaint, &v.Vitals.PainScore, &v.Vitals.HeartRate, &v.Vitals.RespRate, &v.Vitals.SpO2,
		&v.Vitals.TemperatureC, &v.Vitals.SystolicBP, &v.Vitals.AVPU)
	v.Status = flow.Status(status)
	return v, err
}

// ListVisits returns visits ordered like the queue: most urgent (lowest ESI) first, then by arrival.
func (s *Store) ListVisits(ctx context.Context, f VisitFilter) ([]Visit, error) {
	var where []string
	var args []any
	arg := func(v any) string { args = append(args, v); return "$" + strconv.Itoa(len(args)) }
	if len(f.Statuses) > 0 {
		where = append(where, "v.status = ANY("+arg(f.Statuses)+")")
	}
	if f.Department != "" {
		where = append(where, "d.code = "+arg(f.Department))
	}
	if f.PatientID != 0 {
		where = append(where, "v.patient_id = "+arg(f.PatientID))
	}
	if f.Since != nil {
		where = append(where, "v.checked_in_at >= "+arg(*f.Since))
	}
	if f.Until != nil {
		where = append(where, "v.checked_in_at < "+arg(*f.Until))
	}
	query := visitSelect
	if len(where) > 0 {
		query += " WHERE " + strings.Join(where, " AND ")
	}
	rows, err := s.pool.Query(ctx, query+" ORDER BY v.esi, v.checked_in_at, v.id", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	visits := []Visit{}
	for rows.Next() {
		v, err := scanVisit(rows)
		if err != nil {
			return nil, err
		}
		visits = append(visits, v)
	}
	return visits, rows.Err()
}

func (s *Store) GetVisit(ctx context.Context, id int64) (Visit, error) {
	v, err := scanVisit(s.pool.QueryRow(ctx, visitSelect+" WHERE v.id = $1", id))
	if errors.Is(err, pgx.ErrNoRows) {
		return v, ErrNotFound
	}
	return v, err
}

func newVisitNumber() string {
	b := make([]byte, 5)
	_, _ = rand.Read(b)
	return "V-" + strings.ToUpper(hex.EncodeToString(b))
}

func invalidPK(field string, id int64) ValidationError {
	return ValidationError{field: {fmt.Sprintf("Invalid pk \"%d\" - object does not exist.", id)}}
}

// CheckIn creates a waiting visit. The patient row is locked so two simultaneous check-ins for the
// same patient can't both pass the "one active visit" rule.
func (s *Store) CheckIn(ctx context.Context, actor User, in CheckIn) (Visit, error) {
	var id int64
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) (err error) {
		id, err = checkInTx(ctx, tx, actor, in)
		return err
	})
	if err != nil {
		return Visit{}, err
	}
	return s.GetVisit(ctx, id)
}

// checkInTx creates a waiting visit inside the caller's transaction (also used by appointment check-in).
func checkInTx(ctx context.Context, tx pgx.Tx, actor User, in CheckIn) (int64, error) {
	if !flow.ValidESI(in.ESI) {
		return 0, ValidationError{"esi": {"ESI must be from 1 to 5."}}
	}
	if in.ArrivalMode == "" {
		in.ArrivalMode = "walk_in"
	}
	var id int64
	err := func() error {
		if err := tx.QueryRow(ctx, `SELECT id FROM patients_patient WHERE id = $1 FOR UPDATE`, in.PatientID).Scan(new(int64)); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return invalidPK("patient", in.PatientID)
			}
			return err
		}
		var code string
		var active bool
		if err := tx.QueryRow(ctx, `SELECT code, active FROM patients_department WHERE id = $1`, in.DepartmentID).Scan(&code, &active); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return invalidPK("department", in.DepartmentID)
			}
			return err
		}
		if !active {
			return ValidationError{"department": {"This department is not active."}}
		}
		var busy bool
		if err := tx.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM patients_visit WHERE patient_id = $1 AND status = ANY($2))`,
			in.PatientID, statuses(flow.Active)).Scan(&busy); err != nil {
			return err
		}
		if busy {
			return ValidationError{"patient": {"This patient already has an active visit."}}
		}
		if err := tx.QueryRow(ctx, `
			INSERT INTO patients_visit (visit_number, patient_id, department_id, esi, status, arrival_mode, checked_in_at,
				chief_complaint, pain_score, heart_rate, resp_rate, spo2, temperature_c, systolic_bp, avpu)
			VALUES ($1, $2, $3, $4, $5, $6, now(), $7, $8, $9, $10, $11, $12, $13, $14) RETURNING id`,
			newVisitNumber(), in.PatientID, in.DepartmentID, in.ESI, string(flow.Waiting), in.ArrivalMode,
			in.Vitals.Complaint, in.Vitals.PainScore, in.Vitals.HeartRate, in.Vitals.RespRate, in.Vitals.SpO2,
			in.Vitals.TemperatureC, in.Vitals.SystolicBP, in.Vitals.AVPU).Scan(&id); err != nil {
			return err
		}
		// Clinical text stays out of the audit log; record only that vitals were taken.
		if err := audit(ctx, tx, actor, "visit.checked_in", id, map[string]any{"esi": in.ESI, "department": code, "vitals_recorded": in.Vitals.recorded()}); err != nil {
			return err
		}
		return notify(ctx, tx, Event{VisitID: id, Action: "checked_in", Status: string(flow.Waiting), Department: code})
	}()
	return id, err
}

// UpdateVisit changes editable fields (not status: that goes through Transition).
func (s *Store) UpdateVisit(ctx context.Context, actor User, id int64, p VisitPatch) (Visit, error) {
	if p.ESI != nil && !flow.ValidESI(*p.ESI) {
		return Visit{}, ValidationError{"esi": {"ESI must be from 1 to 5."}}
	}
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		var status, code string
		var currentESI int
		if err := tx.QueryRow(ctx, `SELECT v.status, v.esi, d.code FROM patients_visit v JOIN patients_department d ON d.id = v.department_id
			WHERE v.id = $1 FOR UPDATE OF v`, id).Scan(&status, &currentESI, &code); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return ErrNotFound
			}
			return err
		}
		var sets []string
		var fields []string
		var args []any
		set := func(column, field string, v any) {
			args = append(args, v)
			sets = append(sets, fmt.Sprintf("%s = $%d", column, len(args)))
			if len(fields) == 0 || fields[len(fields)-1] != field {
				fields = append(fields, field)
			}
		}
		if p.ESI != nil {
			set("esi", "esi", *p.ESI)
		}
		if p.ArrivalMode != nil {
			set("arrival_mode", "arrival_mode", *p.ArrivalMode)
		}
		if p.DepartmentID != nil {
			var active bool
			if err := tx.QueryRow(ctx, `SELECT code, active FROM patients_department WHERE id = $1`, *p.DepartmentID).Scan(&code, &active); err != nil {
				if errors.Is(err, pgx.ErrNoRows) {
					return invalidPK("department", *p.DepartmentID)
				}
				return err
			}
			if !active {
				return ValidationError{"department": {"This department is not active."}}
			}
			set("department_id", "department", *p.DepartmentID)
		}
		if p.ClinicianID != nil {
			if *p.ClinicianID != nil {
				var exists bool
				if err := tx.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM accounts_user WHERE id = $1)`, **p.ClinicianID).Scan(&exists); err != nil {
					return err
				}
				if !exists {
					return invalidPK("assigned_clinician", **p.ClinicianID)
				}
			}
			set("assigned_clinician_id", "assigned_clinician", *p.ClinicianID)
		}
		if p.Vitals != nil {
			v := p.Vitals
			set("chief_complaint", "chief_complaint", v.Complaint)
			for _, f := range []struct {
				column string
				value  any
			}{{"pain_score", v.PainScore}, {"heart_rate", v.HeartRate}, {"resp_rate", v.RespRate}, {"spo2", v.SpO2},
				{"temperature_c", v.TemperatureC}, {"systolic_bp", v.SystolicBP}, {"avpu", v.AVPU}} {
				set(f.column, "vitals", f.value)
			}
		}
		if len(sets) == 0 {
			return nil
		}
		args = append(args, id)
		if _, err := tx.Exec(ctx, fmt.Sprintf("UPDATE patients_visit SET %s WHERE id = $%d", strings.Join(sets, ", "), len(args)), args...); err != nil {
			return err
		}
		if err := audit(ctx, tx, actor, "visit.updated", id, map[string]any{"fields": fields}); err != nil {
			return err
		}
		if p.ESI != nil && *p.ESI != currentESI {
			if err := recordTriageChange(ctx, tx, actor, id, currentESI, *p.ESI, p.ESIReason); err != nil {
				return err
			}
		}
		return notify(ctx, tx, Event{VisitID: id, Action: "updated", Status: status, Department: code})
	})
	if err != nil {
		return Visit{}, err
	}
	return s.GetVisit(ctx, id)
}

// Transition applies a lifecycle action atomically, under a row lock, so two people can't apply
// conflicting actions to the same visit.
func (s *Store) Transition(ctx context.Context, actor User, id int64, action string) (Visit, error) {
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		var status, code string
		if err := tx.QueryRow(ctx, `SELECT v.status, d.code FROM patients_visit v JOIN patients_department d ON d.id = v.department_id
			WHERE v.id = $1 FOR UPDATE OF v`, id).Scan(&status, &code); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return ErrNotFound
			}
			return err
		}
		t, err := flow.Check(action, actor.Role, flow.Status(status))
		if err != nil {
			return err
		}
		// Column names come from the fixed transition table, never from input.
		query := fmt.Sprintf("UPDATE patients_visit SET status = $1, %s = now()", t.Timestamp)
		if action == "start" {
			query += ", assigned_clinician_id = COALESCE(assigned_clinician_id, $3)"
		}
		args := []any{string(t.To), id}
		if action == "start" {
			args = append(args, actor.ID)
		}
		if _, err := tx.Exec(ctx, query+" WHERE id = $2", args...); err != nil {
			return err
		}
		if err := audit(ctx, tx, actor, "visit."+action, id, map[string]any{"status": string(t.To)}); err != nil {
			return err
		}
		return notify(ctx, tx, Event{VisitID: id, Action: action, Status: string(t.To), Department: code})
	})
	if err != nil {
		return Visit{}, err
	}
	return s.GetVisit(ctx, id)
}

// DashboardRow is one visit's timing data, for computing the dashboard.
type DashboardRow struct {
	PatientID      int64
	DepartmentName string
	Status         flow.Status
	ESI            int
	CheckedInAt    time.Time
	CalledAt       *time.Time
	StartedAt      *time.Time
}

// DashboardData returns today's visits plus all currently-active visits (which may be older than today).
func (s *Store) DashboardData(ctx context.Context, since, until time.Time) (today, active []DashboardRow, err error) {
	load := func(where string, args ...any) ([]DashboardRow, error) {
		rows, err := s.pool.Query(ctx, `SELECT v.patient_id, d.name, v.status, v.esi, v.checked_in_at, v.called_at, v.started_at
			FROM patients_visit v JOIN patients_department d ON d.id = v.department_id WHERE `+where, args...)
		if err != nil {
			return nil, err
		}
		defer rows.Close()
		out := []DashboardRow{}
		for rows.Next() {
			var r DashboardRow
			var st string
			if err := rows.Scan(&r.PatientID, &r.DepartmentName, &st, &r.ESI, &r.CheckedInAt, &r.CalledAt, &r.StartedAt); err != nil {
				return nil, err
			}
			r.Status = flow.Status(st)
			out = append(out, r)
		}
		return out, rows.Err()
	}
	if today, err = load("v.checked_in_at >= $1 AND v.checked_in_at < $2", since, until); err != nil {
		return nil, nil, err
	}
	active, err = load("v.status = ANY($1)", statuses(flow.Active))
	return today, active, err
}

// ReportRow is one visit's data for multi-day flow reports.
type ReportRow struct {
	DepartmentName string
	ESI            int
	Status         flow.Status
	CheckedInAt    time.Time
	CalledAt       *time.Time
	StartedAt      *time.Time
	CompletedAt    *time.Time
}

// ReportRows returns visits checked in within [since, until), oldest first.
func (s *Store) ReportRows(ctx context.Context, since, until time.Time) ([]ReportRow, error) {
	rows, err := s.pool.Query(ctx, `SELECT d.name, v.esi, v.status, v.checked_in_at, v.called_at, v.started_at, v.completed_at
		FROM patients_visit v JOIN patients_department d ON d.id = v.department_id
		WHERE v.checked_in_at >= $1 AND v.checked_in_at < $2 ORDER BY v.checked_in_at`, since, until)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []ReportRow{}
	for rows.Next() {
		var r ReportRow
		var st string
		if err := rows.Scan(&r.DepartmentName, &r.ESI, &st, &r.CheckedInAt, &r.CalledAt, &r.StartedAt, &r.CompletedAt); err != nil {
			return nil, err
		}
		r.Status = flow.Status(st)
		out = append(out, r)
	}
	return out, rows.Err()
}

// recorded reports whether any observation was taken.
func (v Vitals) recorded() bool {
	return v.Complaint != "" || v.PainScore != nil || v.HeartRate != nil || v.RespRate != nil || v.SpO2 != nil ||
		v.TemperatureC != nil || v.SystolicBP != nil || v.AVPU != ""
}

func statuses(list []flow.Status) []string {
	out := make([]string, len(list))
	for i, s := range list {
		out[i] = string(s)
	}
	return out
}

// audit appends to the shared, append-only audit log in the caller's transaction.
func audit(ctx context.Context, tx pgx.Tx, actor User, action string, entityID int64, details map[string]any) error {
	return auditAs(ctx, tx, actor, action, "visit", entityID, details)
}

func auditAs(ctx context.Context, tx pgx.Tx, actor User, action, entityType string, entityID int64, details map[string]any) error {
	payload, err := json.Marshal(details)
	if err != nil {
		return err
	}
	_, err = tx.Exec(ctx, `INSERT INTO operations_auditlog (actor_id, action, entity_type, entity_id, details, created_at)
		VALUES ($1, $2, $3, $4, $5, now())`, actor.ID, action, entityType, strconv.FormatInt(entityID, 10), string(payload))
	return err
}

// notify publishes an event that PostgreSQL delivers only if the transaction commits.
func notify(ctx context.Context, tx pgx.Tx, e Event) error {
	payload, err := json.Marshal(e)
	if err != nil {
		return err
	}
	_, err = tx.Exec(ctx, `SELECT pg_notify($1, $2)`, NotifyChannel, string(payload))
	return err
}
