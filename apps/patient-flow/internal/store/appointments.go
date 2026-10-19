package store

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"mediflow/patient-flow/internal/flow"
)

type Appointment struct {
	ID                    int64
	Reference             string
	PatientID             int64
	PatientName           string
	PatientHospitalNumber string
	PatientUserID         *int64 // login account linked to the patient record, if any
	DepartmentID          int64
	DepartmentCode        string
	DepartmentName        string
	ScheduledFor          time.Time
	Reason                string
	Status                flow.AppointmentStatus
	StaffNote             string
	RequestedBy           *string // usernames
	HandledBy             *string
	VisitID               *int64
	CreatedAt             time.Time
	UpdatedAt             time.Time
}

type AppointmentFilter struct {
	Statuses    []string
	Department  string
	PatientID   int64
	Since       *time.Time
	Until       *time.Time
	NewestFirst bool
}

type NewAppointment struct {
	PatientID    int64
	DepartmentID int64
	ScheduledFor time.Time
	Reason       string
	Status       flow.AppointmentStatus // requested (by a patient) or confirmed (booked by staff)
}

// AppointmentUpdate carries the extra input an action may need.
type AppointmentUpdate struct {
	Note         *string    // staff note shown to the patient
	ScheduledFor *time.Time // confirm may move the slot
	CheckIn      *CheckIn   // check_in: ESI and observations for the new visit
	// CheckInAllowed is asked before checking in, with the slot time; "" means allowed.
	CheckInAllowed func(scheduledFor time.Time) string
	// SlotAllowed is asked before moving the slot, with the appointment's department; "" means allowed.
	SlotAllowed func(departmentID int64, t time.Time) (string, error)
}

const appointmentSelect = `
SELECT a.id, a.reference, a.patient_id, p.full_name, p.hospital_number, p.user_id,
       a.department_id, d.code, d.name, a.scheduled_for, a.reason, a.status, a.staff_note,
       rb.username, hb.username, a.visit_id, a.created_at, a.updated_at
FROM patients_appointment a
JOIN patients_patient p ON p.id = a.patient_id
JOIN patients_department d ON d.id = a.department_id
LEFT JOIN accounts_user rb ON rb.id = a.requested_by_id
LEFT JOIN accounts_user hb ON hb.id = a.handled_by_id`

func scanAppointment(row pgx.Row) (Appointment, error) {
	var a Appointment
	var status string
	err := row.Scan(&a.ID, &a.Reference, &a.PatientID, &a.PatientName, &a.PatientHospitalNumber, &a.PatientUserID,
		&a.DepartmentID, &a.DepartmentCode, &a.DepartmentName, &a.ScheduledFor, &a.Reason, &status, &a.StaffNote,
		&a.RequestedBy, &a.HandledBy, &a.VisitID, &a.CreatedAt, &a.UpdatedAt)
	a.Status = flow.AppointmentStatus(status)
	return a, err
}

// PatientIDForUser returns the patient record linked to a login account, or ErrNotFound.
func (s *Store) PatientIDForUser(ctx context.Context, userID int64) (int64, error) {
	var id int64
	err := s.pool.QueryRow(ctx, `SELECT id FROM patients_patient WHERE user_id = $1`, userID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, ErrNotFound
	}
	return id, err
}

func (s *Store) ListAppointments(ctx context.Context, f AppointmentFilter) ([]Appointment, error) {
	var where []string
	var args []any
	arg := func(v any) string { args = append(args, v); return "$" + strconv.Itoa(len(args)) }
	if len(f.Statuses) > 0 {
		where = append(where, "a.status = ANY("+arg(f.Statuses)+")")
	}
	if f.Department != "" {
		where = append(where, "d.code = "+arg(f.Department))
	}
	if f.PatientID != 0 {
		where = append(where, "a.patient_id = "+arg(f.PatientID))
	}
	if f.Since != nil {
		where = append(where, "a.scheduled_for >= "+arg(*f.Since))
	}
	if f.Until != nil {
		where = append(where, "a.scheduled_for < "+arg(*f.Until))
	}
	query := appointmentSelect
	if len(where) > 0 {
		query += " WHERE " + strings.Join(where, " AND ")
	}
	order := " ORDER BY a.scheduled_for, a.id"
	if f.NewestFirst {
		order = " ORDER BY a.scheduled_for DESC, a.id DESC"
	}
	rows, err := s.pool.Query(ctx, query+order+" LIMIT 500", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Appointment{}
	for rows.Next() {
		a, err := scanAppointment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func (s *Store) GetAppointment(ctx context.Context, id int64) (Appointment, error) {
	a, err := scanAppointment(s.pool.QueryRow(ctx, appointmentSelect+" WHERE a.id = $1", id))
	if errors.Is(err, pgx.ErrNoRows) {
		return a, ErrNotFound
	}
	return a, err
}

func newAppointmentReference() string {
	b := make([]byte, 4)
	_, _ = rand.Read(b)
	return "A-" + strings.ToUpper(hex.EncodeToString(b))
}

// CreateAppointment books (staff) or requests (patient) a slot. The patient row is locked so the
// open-appointment limit can't be exceeded by simultaneous requests.
func (s *Store) CreateAppointment(ctx context.Context, actor User, in NewAppointment) (Appointment, error) {
	var id int64
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
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
			return ValidationError{"department": {"This department is not taking appointments."}}
		}
		var open int
		if err := tx.QueryRow(ctx, `SELECT count(*) FROM patients_appointment WHERE patient_id = $1 AND status = ANY($2)`,
			in.PatientID, apptStatuses(flow.OpenAppointment)).Scan(&open); err != nil {
			return err
		}
		qs, _, err := loadQueueSettings(ctx, tx)
		if err != nil {
			return err
		}
		if open >= qs.MaxOpenAppointments {
			return ValidationError{"non_field_errors": {fmt.Sprintf(
				"There are already %d upcoming appointments for this patient. Cancel one before booking another.", open)}}
		}
		var handledBy *int64
		if in.Status == flow.ApptConfirmed {
			handledBy = &actor.ID
		}
		if err := tx.QueryRow(ctx, `INSERT INTO patients_appointment (reference, patient_id, department_id, scheduled_for, reason,
				status, staff_note, requested_by_id, handled_by_id, created_at, updated_at)
			VALUES ($1, $2, $3, $4, $5, $6, '', $7, $8, now(), now()) RETURNING id`,
			newAppointmentReference(), in.PatientID, in.DepartmentID, in.ScheduledFor, in.Reason, string(in.Status),
			actor.ID, handledBy).Scan(&id); err != nil {
			return err
		}
		action := "appointment.requested"
		if in.Status == flow.ApptConfirmed {
			action = "appointment.booked"
		}
		// The reason is the patient's own words: keep it out of the audit log.
		if err := auditAs(ctx, tx, actor, action, "appointment", id, map[string]any{"department": code, "status": string(in.Status)}); err != nil {
			return err
		}
		return notify(ctx, tx, Event{AppointmentID: id, Action: action, Status: string(in.Status), Department: code})
	})
	if err != nil {
		return Appointment{}, err
	}
	return s.GetAppointment(ctx, id)
}

// AppointmentAction applies confirm, decline, cancel or check_in under a row lock. Check-in creates
// the visit in the same transaction, so either both happen or neither does.
func (s *Store) AppointmentAction(ctx context.Context, actor User, id int64, action string, up AppointmentUpdate) (Appointment, error) {
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		var status, code string
		var patientID, departmentID int64
		var patientUser *int64
		var scheduledFor time.Time
		if err := tx.QueryRow(ctx, `SELECT a.status, a.patient_id, a.department_id, p.user_id, a.scheduled_for, d.code
			FROM patients_appointment a JOIN patients_patient p ON p.id = a.patient_id
			JOIN patients_department d ON d.id = a.department_id WHERE a.id = $1 FOR UPDATE OF a`, id).
			Scan(&status, &patientID, &departmentID, &patientUser, &scheduledFor, &code); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return ErrNotFound
			}
			return err
		}
		ownsRecord := patientUser != nil && *patientUser == actor.ID
		if !ownsRecord && !flow.CanManageAppointments(actor.Role) {
			return ErrNotFound // don't reveal other people's appointments
		}
		a, err := flow.CheckAppointment(action, actor.Role, ownsRecord, flow.AppointmentStatus(status))
		if err != nil {
			return err
		}
		sets := []string{"status = $1", "updated_at = now()"}
		args := []any{string(a.To)}
		add := func(column string, v any) {
			args = append(args, v)
			sets = append(sets, fmt.Sprintf("%s = $%d", column, len(args)))
		}
		staff := flow.CanManageAppointments(actor.Role)
		if staff {
			add("handled_by_id", actor.ID)
		}
		if up.Note != nil {
			add("staff_note", *up.Note)
		}
		details := map[string]any{"status": string(a.To)}
		if action == "confirm" && up.ScheduledFor != nil && !up.ScheduledFor.Equal(scheduledFor) {
			if up.SlotAllowed != nil {
				msg, err := up.SlotAllowed(departmentID, *up.ScheduledFor)
				if err != nil {
					return err
				}
				if msg != "" {
					return ValidationError{"time": {msg}}
				}
			}
			add("scheduled_for", *up.ScheduledFor)
			details["rescheduled"] = true
		}
		if action == "check_in" {
			if up.CheckIn == nil {
				return ValidationError{"esi": {"This field is required."}}
			}
			if up.CheckInAllowed != nil {
				if msg := up.CheckInAllowed(scheduledFor); msg != "" {
					return ValidationError{"non_field_errors": {msg}}
				}
			}
			in := *up.CheckIn
			in.PatientID, in.DepartmentID, in.ArrivalMode = patientID, departmentID, "appointment"
			visitID, err := checkInTx(ctx, tx, actor, in)
			if err != nil {
				return err
			}
			add("visit_id", visitID)
			details["visit"] = visitID
		}
		args = append(args, id)
		if _, err := tx.Exec(ctx, fmt.Sprintf("UPDATE patients_appointment SET %s WHERE id = $%d", strings.Join(sets, ", "), len(args)), args...); err != nil {
			return err
		}
		if err := auditAs(ctx, tx, actor, "appointment."+action, "appointment", id, details); err != nil {
			return err
		}
		return notify(ctx, tx, Event{AppointmentID: id, Action: "appointment." + action, Status: string(a.To), Department: code})
	})
	if err != nil {
		return Appointment{}, err
	}
	return s.GetAppointment(ctx, id)
}

func apptStatuses(list []flow.AppointmentStatus) []string {
	out := make([]string, len(list))
	for i, s := range list {
		out[i] = string(s)
	}
	return out
}
