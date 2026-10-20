package store

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"

	"mediflow/patient-flow/internal/flow"
)

// QueueStats returns, per department code, how fast it is seeing patients: mean consultation length over
// the last 7 days, consultations in progress, and doctors rostered right now. `now` is local hospital
// time, so the roster's weekday and clock match what the admin console entered.
func (s *Store) QueueStats(ctx context.Context, now time.Time) (map[string]flow.DeptStats, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT d.code,
		       coalesce((SELECT avg(extract(epoch FROM v.completed_at - v.started_at)) / 60
		                 FROM patients_visit v
		                 WHERE v.department_id = d.id AND v.status = 'completed' AND v.started_at IS NOT NULL
		                   AND v.completed_at > now() - interval '7 days'), 0)::float8,
		       (SELECT count(*) FROM patients_visit v WHERE v.department_id = d.id AND v.status = 'in_progress'),
		       (SELECT count(DISTINCT sh.user_id) FROM clinic_staffshift sh JOIN accounts_user u ON u.id = sh.user_id
		        WHERE sh.department_id = d.id AND u.is_active AND u.role = 'doctor'
		          AND sh.weekday = $1 AND sh.starts <= $2::time AND sh.ends > $2::time)
		FROM patients_department d`, int(now.Weekday()), now.Format("15:04:05"))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]flow.DeptStats{}
	for rows.Next() {
		var code string
		var st flow.DeptStats
		if err := rows.Scan(&code, &st.AvgServiceMinutes, &st.ActiveConsults, &st.DoctorsOnShift); err != nil {
			return nil, err
		}
		out[code] = st
	}
	return out, rows.Err()
}

// TriageChange is one row of patients_triagechange.
type TriageChange struct {
	FromESI   int
	ToESI     int
	Reason    string
	ChangedBy *string
	ChangedAt time.Time
}

func recordTriageChange(ctx context.Context, tx pgx.Tx, actor User, visitID int64, from, to int, reason string) error {
	if _, err := tx.Exec(ctx, `INSERT INTO patients_triagechange (visit_id, from_esi, to_esi, reason, changed_by_id, changed_at)
		VALUES ($1, $2, $3, $4, $5, now())`, visitID, from, to, reason, actor.ID); err != nil {
		return err
	}
	// The reason is clinical text: only the levels go into the audit log.
	return audit(ctx, tx, actor, "visit.triage_changed", visitID,
		map[string]any{"from": from, "to": to, "direction": flow.TriageDirection(from, to)})
}

// ChangeTriage escalates or de-escalates a visit that hasn't started yet, with a reason.
func (s *Store) ChangeTriage(ctx context.Context, actor User, id int64, esi int, reason string) (Visit, error) {
	if !flow.ValidESI(esi) {
		return Visit{}, ValidationError{"esi": {"ESI must be from 1 to 5."}}
	}
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		var status, code string
		var current int
		if err := tx.QueryRow(ctx, `SELECT v.status, v.esi, d.code FROM patients_visit v
			JOIN patients_department d ON d.id = v.department_id WHERE v.id = $1 FOR UPDATE OF v`, id).Scan(&status, &current, &code); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return ErrNotFound
			}
			return err
		}
		if flow.Status(status) != flow.Waiting && flow.Status(status) != flow.Called {
			return &flow.Error{Status: 409, Message: "Triage can only change while the patient is waiting or called."}
		}
		if current == esi {
			return ValidationError{"esi": {fmt.Sprintf("The patient is already ESI %d.", esi)}}
		}
		if _, err := tx.Exec(ctx, `UPDATE patients_visit SET esi = $1 WHERE id = $2`, esi, id); err != nil {
			return err
		}
		if err := recordTriageChange(ctx, tx, actor, id, current, esi, reason); err != nil {
			return err
		}
		return notify(ctx, tx, Event{VisitID: id, Action: "triage", Status: status, Department: code})
	})
	if err != nil {
		return Visit{}, err
	}
	return s.GetVisit(ctx, id)
}

// TriageHistory lists a visit's ESI changes, oldest first.
func (s *Store) TriageHistory(ctx context.Context, id int64) ([]TriageChange, error) {
	rows, err := s.pool.Query(ctx, `SELECT t.from_esi, t.to_esi, t.reason, u.display_name, t.changed_at
		FROM patients_triagechange t LEFT JOIN accounts_user u ON u.id = t.changed_by_id
		WHERE t.visit_id = $1 ORDER BY t.changed_at, t.id`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []TriageChange{}
	for rows.Next() {
		var c TriageChange
		if err := rows.Scan(&c.FromESI, &c.ToESI, &c.Reason, &c.ChangedBy, &c.ChangedAt); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
}
