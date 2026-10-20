package api

import (
	"context"
	"errors"
	"net/http"
	"sort"
	"strings"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

// insights are what the queue engine adds on top of the plain queue: wait estimates and ESI targets.
// They are best effort: if they can't be loaded the queue is still served, just without them.
type insights struct {
	stats    map[string]flow.DeptStats
	settings store.QueueSettings
	ok       bool
}

func (s *Server) loadInsights(ctx context.Context) insights {
	stats, err := s.Store.QueueStats(ctx, s.Now().In(s.Loc))
	if err != nil {
		s.Log.Warn("queue stats unavailable", "error", err)
		return insights{settings: store.DefaultQueueSettings()}
	}
	settings, err := s.Store.QueueSettings(ctx)
	if err != nil {
		s.Log.Warn("queue settings unavailable", "error", err)
		settings = store.DefaultQueueSettings()
	}
	return insights{stats: stats, settings: settings, ok: true}
}

// departmentLoad is one department's queue right now, for the dashboard.
type departmentLoad struct {
	Name               string `json:"name"`
	Waiting            int    `json:"waiting"`
	InConsultation     int    `json:"inConsultation"`
	LongestWaitMinutes int    `json:"longestWaitMinutes"`
	OverTarget         int    `json:"overTarget"`
	LongWaits          int    `json:"longWaits"` // waiting longer than the long-wait threshold
}

func loadByDepartment(active []store.DashboardRow, settings store.QueueSettings, now time.Time) ([]departmentLoad, int, int) {
	byName := map[string]*departmentLoad{}
	overTarget, longWaits := 0, 0
	for _, v := range active {
		d := byName[v.DepartmentName]
		if d == nil {
			d = &departmentLoad{Name: v.DepartmentName}
			byName[v.DepartmentName] = d
		}
		switch v.Status {
		case flow.Waiting:
			waited := minutesBetween(v.CheckedInAt, now)
			d.Waiting++
			d.LongestWaitMinutes = max(d.LongestWaitMinutes, waited)
			if flow.OverTarget(v.ESI, waited, settings.ESITargetMinutes) {
				d.OverTarget++
				overTarget++
			}
			if settings.LongWaitMinutes > 0 && waited > settings.LongWaitMinutes {
				d.LongWaits++
				longWaits++
			}
		case flow.InProgress:
			d.InConsultation++
		}
	}
	out := make([]departmentLoad, 0, len(byName))
	for _, d := range byName {
		out = append(out, *d)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, overTarget, longWaits
}

// GET /api/queue/me: a patient's own place in the queue, with an estimate (student dashboard).
func (s *Server) myQueue(w http.ResponseWriter, r *http.Request) {
	user := userFrom(r)
	patientID, err := s.Store.PatientIDForUser(r.Context(), user.ID)
	if errors.Is(err, store.ErrNotFound) {
		writeJSON(w, http.StatusOK, map[string]any{"linked": false, "active": false})
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	mine, err := s.Store.ListVisits(r.Context(), store.VisitFilter{PatientID: patientID,
		Statuses: []string{string(flow.Waiting), string(flow.Called), string(flow.InProgress)}})
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if len(mine) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{"linked": true, "active": false})
		return
	}
	v := mine[0]
	resp := map[string]any{"linked": true, "active": true, "status": v.Status, "department": v.DepartmentName,
		"ahead": 0, "estimatedWaitMinutes": nil}
	if v.Status == flow.Waiting {
		queue, err := s.Store.ListVisits(r.Context(), store.VisitFilter{Statuses: []string{string(flow.Waiting)}, Department: v.DepartmentCode})
		if err != nil {
			s.fail(w, r, err)
			return
		}
		ahead := 0
		for _, q := range queue {
			if q.ID == v.ID {
				break
			}
			ahead++
		}
		resp["ahead"] = ahead
		if in := s.loadInsights(r.Context()); in.ok {
			resp["estimatedWaitMinutes"] = flow.EstimateWaitMinutes(ahead, in.stats[v.DepartmentCode])
		}
	}
	writeJSON(w, http.StatusOK, resp)
}

type triageChangeJSON struct {
	FromESI   int     `json:"from_esi"`
	ToESI     int     `json:"to_esi"`
	Direction string  `json:"direction"`
	Reason    string  `json:"reason"`
	ChangedBy *string `json:"changed_by"`
	ChangedAt string  `json:"changed_at"`
}

// POST /api/visits/{id}/triage {esi, reason}: escalate or de-escalate a waiting or called patient.
func (s *Server) changeTriage(w http.ResponseWriter, r *http.Request) {
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
	problems := store.ValidationError{}
	esi := 0
	if raw, present := fields["esi"]; !present {
		problems["esi"] = []string{"This field is required."}
	} else if v, ok := esiField(raw, problems); ok {
		esi = v
	}
	reason := strings.TrimSpace(stringField(fields, "reason", 300, problems))
	if reason == "" && problems["reason"] == nil {
		problems["reason"] = []string{"Say why the triage level is changing (e.g. SpO₂ dropped to 89%)."}
	}
	if len(problems) > 0 {
		writeJSON(w, http.StatusBadRequest, problems)
		return
	}
	v, err := s.Store.ChangeTriage(r.Context(), userFrom(r), id, esi, reason)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.visitOut(v))
}

// GET /api/visits/{id}/triage: the visit's ESI changes, oldest first.
func (s *Server) triageHistory(w http.ResponseWriter, r *http.Request) {
	id, ok := pathID(r)
	if !ok {
		detail(w, http.StatusNotFound, "Not found.")
		return
	}
	if _, err := s.Store.GetVisit(r.Context(), id); err != nil {
		s.fail(w, r, err)
		return
	}
	changes, err := s.Store.TriageHistory(r.Context(), id)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	out := make([]triageChangeJSON, len(changes))
	for i, c := range changes {
		out[i] = triageChangeJSON{c.FromESI, c.ToESI, flow.TriageDirection(c.FromESI, c.ToESI), c.Reason, c.ChangedBy, s.stamp(c.ChangedAt)}
	}
	writeJSON(w, http.StatusOK, out)
}
