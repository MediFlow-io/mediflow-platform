package api

import (
	"io"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestMetricsCountRequestsByRoutePattern(t *testing.T) {
	_, s := newFixture()
	h := s.Routes()
	call(t, h, "POST", "/api/visits/11/start", "user-1", "")    // 200
	call(t, h, "POST", "/api/visits/10/complete", "user-2", "") // 409
	call(t, h, "POST", "/api/visits", "user-6", `{"patient": 7, "department": 1, "esi": 3}`)
	call(t, h, "GET", "/api/visits/10", "user-1", "")

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/metrics", nil))
	body, _ := io.ReadAll(rec.Body)
	text := string(body)
	for _, want := range []string{
		`patient_flow_http_requests_total{method="POST",route="/api/visits/{id}/{action}",status="200"} 1`,
		`patient_flow_http_requests_total{method="POST",route="/api/visits/{id}/{action}",status="409"} 1`,
		`patient_flow_http_requests_total{method="GET",route="/api/visits/{id}",status="200"} 1`,
		`patient_flow_visit_transitions_total{action="start"} 1`,
		`patient_flow_check_ins_total 1`,
		`patient_flow_event_stream_clients 0`,
		`go_goroutines`,
	} {
		if !strings.Contains(text, want) {
			t.Errorf("metrics missing %q", want)
		}
	}
	if strings.Contains(text, `route="/api/visits/10"`) {
		t.Error("raw paths with IDs must never become labels")
	}
}
