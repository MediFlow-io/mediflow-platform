// MediFlow Auth Gateway
//
// Sits between the React frontend and the Django auth service.
// Responsibilities:
//   - Terminates CORS for the browser so Django doesn't need to know about it
//   - Exposes a stable /api/auth/* surface to the frontend, decoupled from
//     whatever path Django happens to mount its views on
//   - Adds request logging, timeouts, and a single place to add rate limiting
//   - Verifies RS256 access tokens (via Django's JWKS) on protected routes
package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

// route maps a public gateway path to a Django path.
type route struct {
	gatewayPath string
	djangoPath  string
	methods     []string
	auth        bool     // require a valid access token
	roles       []string // if set, the token's role must be one of these
}

var routes = []route{
	{"/api/auth/register/student", "/api/auth/register/student/", []string{http.MethodPost}, false, nil},
	{"/api/auth/register/staff", "/api/auth/register/staff/", []string{http.MethodPost}, true, []string{"admin"}},
	{"/api/auth/login", "/api/auth/login/", []string{http.MethodPost}, false, nil},
	{"/api/auth/token/refresh", "/api/auth/token/refresh/", []string{http.MethodPost}, false, nil},
	// Logout stays open so a client with an expired access token can still revoke its refresh token.
	{"/api/auth/logout", "/api/auth/logout/", []string{http.MethodPost}, false, nil},
	{"/api/auth/change-password", "/api/auth/change-password/", []string{http.MethodPost}, true, nil},
	// Two-step sign-in. verify is the second login step, so it needs no token; the rest manage the authenticator.
	{"/api/auth/mfa/verify", "/api/auth/mfa/verify/", []string{http.MethodPost}, false, nil},
	{"/api/auth/mfa/status", "/api/auth/mfa/status/", []string{http.MethodGet}, true, nil},
	{"/api/auth/mfa/setup", "/api/auth/mfa/setup/", []string{http.MethodPost}, true, nil},
	{"/api/auth/mfa/confirm", "/api/auth/mfa/confirm/", []string{http.MethodPost}, true, nil},
	{"/api/auth/mfa/disable", "/api/auth/mfa/disable/", []string{http.MethodPost}, true, nil},
	{"/api/auth/jwks", "/api/auth/jwks", []string{http.MethodGet}, false, nil},
}

func mustGetenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	djangoBaseURL := mustGetenv("DJANGO_BASE_URL", "http://localhost:8000")
	allowedOrigin := mustGetenv("ALLOWED_ORIGIN", "http://localhost:5173")
	port := mustGetenv("PORT", "8080")

	upstream, err := url.Parse(djangoBaseURL)
	if err != nil {
		log.Fatalf("invalid DJANGO_BASE_URL %q: %v", djangoBaseURL, err)
	}

	// UPSTREAM_TIMEOUT: how long to wait for Django. Raise it where Django can be asleep (free hosting).
	timeout, err := time.ParseDuration(mustGetenv("UPSTREAM_TIMEOUT", "10s"))
	if err != nil {
		log.Fatalf("invalid UPSTREAM_TIMEOUT: %v", err)
	}
	client := &http.Client{Timeout: timeout}
	// WAKE_TIMEOUT: how long to keep retrying while Django is starting. Free hosts put idle services to
	// sleep and answer with their own 502/503 page until the service is up again. 0 = no retries.
	if wakeWait, err = time.ParseDuration(mustGetenv("WAKE_TIMEOUT", "0s")); err != nil {
		log.Fatalf("invalid WAKE_TIMEOUT: %v", err)
	}
	jwt := newVerifier(
		djangoBaseURL+"/api/auth/jwks",
		mustGetenv("JWT_ISSUER", "mediflow-core"),
		mustGetenv("JWT_AUDIENCE", "mediflow"),
		client,
	)

	mux := http.NewServeMux()

	for _, r := range routes {
		r := r // capture
		handler := func(w http.ResponseWriter, req *http.Request) {
			handleProxy(w, req, client, upstream, r)
		}
		if r.auth {
			handler = requireAuth(jwt, r.roles, handler)
		}
		mux.HandleFunc(r.gatewayPath, handler)
	}

	mux.HandleFunc("/healthz", func(w http.ResponseWriter, req *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	handler := withCORS(allowedOrigin, withLogging(mux))

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("mediflow auth gateway listening on :%s (proxying to %s)", port, djangoBaseURL)
	log.Fatal(srv.ListenAndServe())
}

func handleProxy(w http.ResponseWriter, req *http.Request, client *http.Client, upstream *url.URL, r route) {
	if req.Method == http.MethodOptions {
		w.WriteHeader(http.StatusNoContent)
		return
	}

	if !methodAllowed(req.Method, r.methods) {
		http.Error(w, `{"detail":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	target := *upstream
	target.Path = r.djangoPath
	target.RawQuery = req.URL.RawQuery

	// Buffer the body so the upstream request carries a Content-Length. Streaming
	// req.Body directly makes Go send it chunked, and Django (WSGI) then reads an
	// empty body.
	body, err := io.ReadAll(http.MaxBytesReader(w, req.Body, maxBodyBytes))
	if err != nil {
		http.Error(w, `{"detail":"request body too large or unreadable"}`, http.StatusRequestEntityTooLarge)
		return
	}

	resp, err := send(req.Context(), client, req.Method, target.String(), body, req.Header.Get("Authorization"))
	if err != nil {
		log.Printf("upstream error for %s: %v", r.djangoPath, err)
		http.Error(w, `{"detail":"auth service unavailable"}`, http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	for key, values := range resp.Header {
		if key == "Content-Length" {
			continue
		}
		for _, v := range values {
			w.Header().Add(key, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

var wakeWait time.Duration

// send forwards the request to Django, retrying for up to wakeWait while Django isn't up yet. Retries are
// only made when the request can't have reached Django (no connection, or the host's own error page),
// so a login or registration is never processed twice.
func send(ctx context.Context, client *http.Client, method, target string, body []byte, auth string) (*http.Response, error) {
	deadline := time.Now().Add(wakeWait)
	delay := time.Second
	for {
		upstreamReq, err := http.NewRequestWithContext(ctx, method, target, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		// Forward relevant headers, including the bearer token from the client.
		upstreamReq.Header.Set("Content-Type", "application/json")
		if auth != "" {
			upstreamReq.Header.Set("Authorization", auth)
		}
		resp, err := client.Do(upstreamReq)
		if (err == nil && !hostErrorPage(resp)) || (err != nil && !notConnected(err)) || time.Now().Add(delay).After(deadline) {
			return resp, err
		}
		if resp != nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
		log.Printf("%s not ready yet, retrying in %s", target, delay)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(delay):
		}
		delay = min(delay*2, 5*time.Second)
	}
}

// hostErrorPage reports a 502/503 that came from the host, not Django: Django's API always answers in JSON.
func hostErrorPage(resp *http.Response) bool {
	return (resp.StatusCode == http.StatusBadGateway || resp.StatusCode == http.StatusServiceUnavailable) &&
		!strings.HasPrefix(resp.Header.Get("Content-Type"), "application/json")
}

// notConnected reports a failure to connect (DNS or dial), when nothing was sent.
func notConnected(err error) bool {
	var op *net.OpError
	return errors.As(err, &op) && op.Op == "dial"
}

// Auth payloads are tiny; anything larger is rejected at the edge.
const maxBodyBytes = 1 << 20

func methodAllowed(method string, allowed []string) bool {
	for _, m := range allowed {
		if m == method {
			return true
		}
	}
	return false
}

func withCORS(allowedOrigin string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", allowedOrigin)
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		next.ServeHTTP(w, req)
	})
}

func withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, req)
		log.Printf("%s %s (%s)", req.Method, req.URL.Path, time.Since(start))
	})
}
