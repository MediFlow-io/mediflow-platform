package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"

	"mediflow/patient-flow/internal/flow"
)

// QueueSettings mirror clinic_queuesettings (one row, edited from the admin console). Missing row →
// DefaultQueueSettings.
type QueueSettings struct {
	ESITargetMinutes    [6]int // index 1..5; index 0 unused
	LongWaitMinutes     int
	TurnNearAhead       int
	SlotMinutes         int
	MaxDaysAhead        int
	MinNoticeMinutes    int
	MaxOpenAppointments int
}

func DefaultQueueSettings() QueueSettings {
	return QueueSettings{ESITargetMinutes: [6]int{0, 0, 10, 30, 60, 120}, LongWaitMinutes: 60, TurnNearAhead: 2,
		SlotMinutes: 15, MaxDaysAhead: 60, MinNoticeMinutes: 15, MaxOpenAppointments: flow.MaxOpenAppointmentsPerPatient}
}

type querier interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

func loadQueueSettings(ctx context.Context, q querier) (QueueSettings, bool, error) {
	qs := DefaultQueueSettings()
	t := &qs.ESITargetMinutes
	err := q.QueryRow(ctx, `SELECT esi1_target_minutes, esi2_target_minutes, esi3_target_minutes, esi4_target_minutes,
			esi5_target_minutes, long_wait_minutes, turn_near_ahead, slot_minutes, max_days_ahead, min_notice_minutes,
			max_open_appointments FROM clinic_queuesettings WHERE id = 1`).
		Scan(&t[1], &t[2], &t[3], &t[4], &t[5], &qs.LongWaitMinutes, &qs.TurnNearAhead, &qs.SlotMinutes,
			&qs.MaxDaysAhead, &qs.MinNoticeMinutes, &qs.MaxOpenAppointments)
	if errors.Is(err, pgx.ErrNoRows) {
		return DefaultQueueSettings(), false, nil
	}
	return qs, err == nil, err
}

// QueueSettings returns the clinic's queue settings, or the defaults if none were saved.
func (s *Store) QueueSettings(ctx context.Context) (QueueSettings, error) {
	qs, _, err := loadQueueSettings(ctx, s.pool)
	return qs, err
}

// Schedule is the bookable schedule for a department (0 = clinic-wide): the department's own hours if
// it has any, else the clinic default hours, else base (CLINIC_HOURS/CLINIC_DAYS). Holidays and booking
// rules come from the settings tables when saved.
func (s *Store) Schedule(ctx context.Context, departmentID int64, base flow.Schedule) (flow.Schedule, error) {
	sched := base
	qs, saved, err := loadQueueSettings(ctx, s.pool)
	if err != nil {
		return sched, err
	}
	if saved {
		sched.SlotLength = time.Duration(qs.SlotMinutes) * time.Minute
		sched.MaxAhead = time.Duration(qs.MaxDaysAhead) * 24 * time.Hour
		sched.MinNotice = time.Duration(qs.MinNoticeMinutes) * time.Minute
	}

	rows, err := s.pool.Query(ctx, `SELECT department_id IS NOT NULL, weekday, extract(epoch FROM opens)::bigint,
			extract(epoch FROM closes)::bigint
		FROM clinic_servicehours WHERE department_id = $1 OR department_id IS NULL`, departmentID)
	if err != nil {
		return sched, err
	}
	own, clinic := map[time.Weekday]flow.Window{}, map[time.Weekday]flow.Window{}
	for rows.Next() {
		var isOwn bool
		var weekday int
		var opens, closes int64
		if err := rows.Scan(&isOwn, &weekday, &opens, &closes); err != nil {
			rows.Close()
			return sched, err
		}
		w := flow.Window{Open: time.Duration(opens) * time.Second, Close: time.Duration(closes) * time.Second}
		if isOwn {
			own[time.Weekday(weekday)] = w
		} else {
			clinic[time.Weekday(weekday)] = w
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return sched, err
	}
	switch {
	case len(own) > 0:
		sched.Hours = own
	case len(clinic) > 0:
		sched.Hours = clinic
	}

	holidays, err := s.pool.Query(ctx, `SELECT to_char(date, 'YYYY-MM-DD'), name FROM clinic_holiday
		WHERE date >= current_date - 1 ORDER BY date`)
	if err != nil {
		return sched, err
	}
	defer holidays.Close()
	sched.Holidays = map[string]string{}
	for holidays.Next() {
		var day, name string
		if err := holidays.Scan(&day, &name); err != nil {
			return sched, err
		}
		sched.Holidays[day] = name
	}
	return sched, holidays.Err()
}
