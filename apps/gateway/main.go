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
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
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

	client := &http.Client{Timeout: 10 * time.Second}
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

	upstreamReq, err := http.NewRequestWithContext(req.Context(), req.Method, target.String(), bytes.NewReader(body))
	if err != nil {
		http.Error(w, `{"detail":"gateway error building request"}`, http.StatusBadGateway)
		return
	}

	// Forward relevant headers, including the bearer token from the client.
	upstreamReq.Header.Set("Content-Type", "application/json")
	if auth := req.Header.Get("Authorization"); auth != "" {
		upstreamReq.Header.Set("Authorization", auth)
	}

	resp, err := client.Do(upstreamReq)
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
