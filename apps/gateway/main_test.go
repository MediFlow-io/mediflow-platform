package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

// Django (WSGI) ignores chunked request bodies, so the proxy must send a Content-Length.
func TestProxySendsContentLength(t *testing.T) {
	const payload = `{"unique_id":"nurse","password":"x"}`
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if r.ContentLength != int64(len(payload)) || len(r.TransferEncoding) > 0 || string(body) != payload {
			t.Errorf("upstream got ContentLength=%d TransferEncoding=%v body=%q", r.ContentLength, r.TransferEncoding, body)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()
	target, _ := url.Parse(upstream.URL)

	// io.NopCloser hides the length, as with a real streamed client body.
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", io.NopCloser(strings.NewReader(payload)))
	req.ContentLength = -1
	rec := httptest.NewRecorder()
	handleProxy(rec, req, upstream.Client(), target, route{djangoPath: "/api/auth/login/", methods: []string{http.MethodPost}})
	if rec.Code != http.StatusOK {
		t.Fatalf("got status %d", rec.Code)
	}
}

// While Django wakes up, the host answers with its own error page: the gateway retries until Django answers.
func TestProxyWaitsForDjangoToWake(t *testing.T) {
	calls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls < 3 {
			w.Header().Set("Content-Type", "text/html")
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"access":"a"}`))
	}))
	defer upstream.Close()
	target, _ := url.Parse(upstream.URL)
	wakeWait = 10 * time.Second
	defer func() { wakeWait = 0 }()

	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(`{}`))
	rec := httptest.NewRecorder()
	handleProxy(rec, req, upstream.Client(), target, route{djangoPath: "/api/auth/login/", methods: []string{http.MethodPost}})
	if rec.Code != http.StatusOK || calls != 3 {
		t.Fatalf("got status %d after %d calls", rec.Code, calls)
	}
}

// Django's own errors are JSON and are passed straight through, never retried.
func TestProxyDoesNotRetryDjangoErrors(t *testing.T) {
	calls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"detail":"busy"}`))
	}))
	defer upstream.Close()
	target, _ := url.Parse(upstream.URL)
	wakeWait = 10 * time.Second
	defer func() { wakeWait = 0 }()

	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(`{}`))
	rec := httptest.NewRecorder()
	handleProxy(rec, req, upstream.Client(), target, route{djangoPath: "/api/auth/login/", methods: []string{http.MethodPost}})
	if rec.Code != http.StatusServiceUnavailable || calls != 1 {
		t.Fatalf("got status %d after %d calls", rec.Code, calls)
	}
}
