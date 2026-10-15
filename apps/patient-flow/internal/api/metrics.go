package api

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// metrics are served at GET /metrics. That path isn't routed by the public Nginx, so only the internal
// network (a Prometheus scraper) can read it.
type metrics struct {
	registry    *prometheus.Registry
	requests    *prometheus.CounterVec
	duration    *prometheus.HistogramVec
	checkIns    prometheus.Counter
	transitions *prometheus.CounterVec
}

func newMetrics(s *Server) *metrics {
	m := &metrics{
		registry: prometheus.NewRegistry(),
		requests: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "patient_flow_http_requests_total", Help: "HTTP requests by route, method and status.",
		}, []string{"route", "method", "status"}),
		duration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name: "patient_flow_http_request_duration_seconds", Help: "HTTP request latency by route.",
			Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5},
		}, []string{"route", "method"}),
		checkIns: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "patient_flow_check_ins_total", Help: "Visits checked in.",
		}),
		transitions: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "patient_flow_visit_transitions_total", Help: "Visit lifecycle actions applied.",
		}, []string{"action"}),
	}
	m.registry.MustRegister(m.requests, m.duration, m.checkIns, m.transitions,
		prometheus.NewGaugeFunc(prometheus.GaugeOpts{
			Name: "patient_flow_event_stream_clients", Help: "Connected live-queue clients.",
		}, func() float64 { return float64(s.Hub.Subscribers()) }),
		collectors.NewGoCollector(),
		collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
	)
	return m
}

func (m *metrics) handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{})
}

// instrument labels each request with its route pattern (never the raw path, which holds IDs).
func (m *metrics) instrument(pattern string, next http.Handler) http.Handler {
	method, route, _ := strings.Cut(pattern, " ")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		m.requests.WithLabelValues(route, method, strconv.Itoa(rec.status)).Inc()
		if route != "/api/queue/events" { // long-lived stream: latency isn't meaningful
			m.duration.WithLabelValues(route, method).Observe(time.Since(start).Seconds())
		}
		if rec.status < 300 && method == http.MethodPost {
			if route == "/api/visits" {
				m.checkIns.Inc()
			} else if route == "/api/visits/{id}/{action}" {
				m.transitions.WithLabelValues(r.PathValue("action")).Inc()
			}
		}
	})
}
