package api

import (
	"math"
	"net/http"
	"sort"
	"strconv"
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
	// Called → consultation started: time spent getting to the clinician (rooms, hand-over).
	AvgCallToStartMinutes *int `json:"averageCallToStartMinutes"`
	// Share of patients seen (called or started) within their ESI level's target, in percent.
	SeenWithinTargetPercent *int `json:"seenWithinTargetPercent"`
	waitSum, waitN          int
	consultSum, consN       int
	callSum, callN          int
	inTarget                int
	targets                 *[6]int
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
		waited := minutesBetween(v.CheckedInAt, *seen)
		r.waitSum += waited
		r.waitN++
		if r.targets != nil && !flow.OverTarget(v.ESI, waited, *r.targets) {
			r.inTarget++
		}
	}
	if v.CalledAt != nil && v.StartedAt != nil {
		r.callSum += minutesBetween(*v.CalledAt, *v.StartedAt)
		r.callN++
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
	r.AvgCallToStartMinutes = avg(r.callSum, r.callN)
	if r.targets != nil && r.waitN > 0 {
		r.SeenWithinTargetPercent = avg(r.inTarget*100, r.waitN)
	}
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

type hourReport struct {
	Hour int `json:"hour"` // 0–23, hospital time, by check-in
	reportStats
}

type weekdayReport struct {
	Weekday int    `json:"weekday"` // 0 = Sunday
	Day     string `json:"day"`
	reportStats
}

type clinicianReport struct {
	Clinician string `json:"clinician"`
	reportStats
}

type flowReport struct {
	From         string            `json:"from"`
	To           string            `json:"to"`
	TimeZone     string            `json:"timeZone"`
	Totals       reportStats       `json:"totals"`
	Days         []dayReport       `json:"days"`
	ByDepartment []deptReport      `json:"byDepartment"`
	ByESI        []esiReport       `json:"byEsi"`
	ByHour       []hourReport      `json:"byHour"`
	ByWeekday    []weekdayReport   `json:"byWeekday"`
	ByClinician  []clinicianReport `json:"byClinician"`
	Targets      map[string]int    `json:"targetMinutes"` // ESI level → target used for seenWithinTargetPercent
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
	settings, err := s.Store.QueueSettings(r.Context())
	if err != nil {
		s.Log.Warn("queue settings unavailable", "error", err)
		settings = store.DefaultQueueSettings()
	}
	writeJSON(w, http.StatusOK, buildFlowReport(rows, from, days, s.Loc, settings.ESITargetMinutes))
}

func buildFlowReport(rows []store.ReportRow, from time.Time, days int, loc *time.Location, targets [6]int) flowReport {
	totals := reportStats{targets: &targets}
	byDay := map[string]*reportStats{}
	byDept := map[string]*reportStats{}
	byESI := map[int]*reportStats{}
	byHour := map[int]*reportStats{}
	byWeekday := map[int]*reportStats{}
	byClinician := map[string]*reportStats{}
	bucket := func(m map[string]*reportStats, k string) *reportStats { return getT(m, k, &targets) }
	for _, v := range rows {
		local := v.CheckedInAt.In(loc)
		buckets := []*reportStats{&totals, bucket(byDay, local.Format("2006-01-02")), bucket(byDept, v.DepartmentName),
			getT(byESI, v.ESI, &targets), getT(byHour, local.Hour(), &targets), getT(byWeekday, int(local.Weekday()), &targets)}
		if v.ClinicianName != nil {
			buckets = append(buckets, bucket(byClinician, *v.ClinicianName))
		}
		for _, b := range buckets {
			b.add(v)
		}
	}
	report := flowReport{
		From: from.Format("2006-01-02"), To: from.AddDate(0, 0, days-1).Format("2006-01-02"), TimeZone: loc.String(),
		Totals: totals.finish(), Days: []dayReport{}, ByDepartment: []deptReport{}, ByESI: []esiReport{},
		ByHour: []hourReport{}, ByWeekday: []weekdayReport{}, ByClinician: []clinicianReport{}, Targets: map[string]int{},
	}
	for esi := 1; esi <= 5; esi++ {
		report.Targets[strconv.Itoa(esi)] = targets[esi]
	}
	for hour := 0; hour < 24; hour++ {
		stats := reportStats{targets: &targets}
		if s, ok := byHour[hour]; ok {
			stats = *s
		}
		report.ByHour = append(report.ByHour, hourReport{hour, stats.finish()})
	}
	for day := 0; day < 7; day++ {
		stats := reportStats{targets: &targets}
		if s, ok := byWeekday[day]; ok {
			stats = *s
		}
		report.ByWeekday = append(report.ByWeekday, weekdayReport{day, time.Weekday(day).String()[:3], stats.finish()})
	}
	for name, s := range byClinician {
		report.ByClinician = append(report.ByClinician, clinicianReport{name, s.finish()})
	}
	sort.Slice(report.ByClinician, func(i, j int) bool {
		a, b := report.ByClinician[i], report.ByClinician[j]
		return a.Completed > b.Completed || a.Completed == b.Completed && a.Clinician < b.Clinician
	})
	for i := 0; i < days; i++ {
		day := from.AddDate(0, 0, i).Format("2006-01-02")
		stats := reportStats{targets: &targets}
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

func getT[K comparable](m map[K]*reportStats, k K, targets *[6]int) *reportStats {
	if m[k] == nil {
		m[k] = &reportStats{targets: targets}
	}
	return m[k]
}
