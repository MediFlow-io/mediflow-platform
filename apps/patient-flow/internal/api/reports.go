package api

import (
	"math"
	"net/http"
	"sort"
	"time"

	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

// MaxReportDays bounds a report's range so one request can't scan years of visits.
const MaxReportDays = 92

type reportStats struct {
	CheckIns          int  `json:"checkIns"`
	Completed         int  `json:"completed"`
	Cancelled         int  `json:"cancelled"`
	AvgWaitMinutes    *int `json:"averageWaitMinutes"`
	AvgConsultMinutes *int `json:"averageConsultationMinutes"`
	waitSum, waitN    int
	consultSum, consN int
}

func (r *reportStats) add(v store.ReportRow) {
	r.CheckIns++
	switch v.Status {
	case flow.Completed:
		r.Completed++
	case flow.Cancelled:
		r.Cancelled++
	}
	// Wait: check-in until first seen (called, or started directly).
	seen := v.CalledAt
	if seen == nil {
		seen = v.StartedAt
	}
	if seen != nil {
		r.waitSum += minutesBetween(v.CheckedInAt, *seen)
		r.waitN++
	}
	if v.Status == flow.Completed && v.StartedAt != nil && v.CompletedAt != nil {
		r.consultSum += minutesBetween(*v.StartedAt, *v.CompletedAt)
		r.consN++
	}
}

func avg(sum, n int) *int {
	if n == 0 {
		return nil
	}
	v := int(math.RoundToEven(float64(sum) / float64(n)))
	return &v
}

func (r *reportStats) finish() reportStats {
	r.AvgWaitMinutes = avg(r.waitSum, r.waitN)
	r.AvgConsultMinutes = avg(r.consultSum, r.consN)
	return *r
}

type dayReport struct {
	Date string `json:"date"`
	reportStats
}

type deptReport struct {
	Department string `json:"department"`
	reportStats
}

type esiReport struct {
	ESI int `json:"esi"`
	reportStats
}

type flowReport struct {
	From         string       `json:"from"`
	To           string       `json:"to"`
	TimeZone     string       `json:"timeZone"`
	Totals       reportStats  `json:"totals"`
	Days         []dayReport  `json:"days"`
	ByDepartment []deptReport `json:"byDepartment"`
	ByESI        []esiReport  `json:"byEsi"`
}

func badRange(w http.ResponseWriter, field, msg string) {
	writeJSON(w, http.StatusBadRequest, store.ValidationError{field: {msg}})
}

// flowReport serves GET /api/reports/flow?from=YYYY-MM-DD&to=YYYY-MM-DD (inclusive, hospital time zone).
// Defaults to the last 7 days. Every day in the range is listed, including days with no visits.
func (s *Server) flowReport(w http.ResponseWriter, r *http.Request) {
	today, _ := s.today()
	to, from := today, today.AddDate(0, 0, -6)
	var err error
	if v := r.URL.Query().Get("to"); v != "" {
		if to, err = time.ParseInLocation("2006-01-02", v, s.Loc); err != nil {
			badRange(w, "to", "Use the format YYYY-MM-DD.")
			return
		}
	}
	if v := r.URL.Query().Get("from"); v != "" {
		if from, err = time.ParseInLocation("2006-01-02", v, s.Loc); err != nil {
			badRange(w, "from", "Use the format YYYY-MM-DD.")
			return
		}
	} else if r.URL.Query().Get("to") != "" {
		from = to.AddDate(0, 0, -6)
	}
	if to.Before(from) {
		badRange(w, "from", "The start date must be on or before the end date.")
		return
	}
	days := int(to.Sub(from).Hours()/24) + 1
	if days > MaxReportDays {
		badRange(w, "to", "A report can cover at most 92 days.")
		return
	}
	rows, err := s.Store.ReportRows(r.Context(), from, to.AddDate(0, 0, 1))
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, buildFlowReport(rows, from, days, s.Loc))
}

func buildFlowReport(rows []store.ReportRow, from time.Time, days int, loc *time.Location) flowReport {
	var totals reportStats
	byDay := map[string]*reportStats{}
	byDept := map[string]*reportStats{}
	byESI := map[int]*reportStats{}
	for _, v := range rows {
		day := v.CheckedInAt.In(loc).Format("2006-01-02")
		for _, bucket := range []*reportStats{&totals, get(byDay, day), get(byDept, v.DepartmentName), get(byESI, v.ESI)} {
			bucket.add(v)
		}
	}
	report := flowReport{
		From: from.Format("2006-01-02"), To: from.AddDate(0, 0, days-1).Format("2006-01-02"), TimeZone: loc.String(),
		Totals: totals.finish(), Days: []dayReport{}, ByDepartment: []deptReport{}, ByESI: []esiReport{},
	}
	for i := 0; i < days; i++ {
		day := from.AddDate(0, 0, i).Format("2006-01-02")
		stats := reportStats{}
		if s, ok := byDay[day]; ok {
			stats = *s
		}
		report.Days = append(report.Days, dayReport{day, stats.finish()})
	}
	for name, s := range byDept {
		report.ByDepartment = append(report.ByDepartment, deptReport{name, s.finish()})
	}
	sort.Slice(report.ByDepartment, func(i, j int) bool { return report.ByDepartment[i].Department < report.ByDepartment[j].Department })
	for esi, s := range byESI {
		report.ByESI = append(report.ByESI, esiReport{esi, s.finish()})
	}
	sort.Slice(report.ByESI, func(i, j int) bool { return report.ByESI[i].ESI < report.ByESI[j].ESI })
	return report
}

func get[K comparable](m map[K]*reportStats, k K) *reportStats {
	if m[k] == nil {
		m[k] = &reportStats{}
	}
	return m[k]
}
