// patient-flow is MediFlow's Go service for visits and the queue: check-in, the
// call → start → complete lifecycle, the live queue (with server-sent events) and the flow dashboard.
// See docs/handbook/decisions/ADR-0002-service-ownership.md.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
	_ "time/tzdata" // the hospital time zone must resolve even on minimal images and Windows

	"github.com/jackc/pgx/v5/pgxpool"

	"mediflow/patient-flow/internal/api"
	"mediflow/patient-flow/internal/auth"
	"mediflow/patient-flow/internal/events"
	"mediflow/patient-flow/internal/flow"
	"mediflow/patient-flow/internal/store"
)

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// databaseURL uses DATABASE_URL, or builds one from the same POSTGRES_* variables as the core API.
func databaseURL() string {
	if dsn := strings.TrimSpace(os.Getenv("DATABASE_URL")); dsn != "" { // pasted values often end with a newline
		return dsn
	}
	u := url.URL{
		Scheme: "postgres",
		User:   url.UserPassword(env("POSTGRES_USER", "mediflow"), env("POSTGRES_PASSWORD", "")),
		Host:   env("POSTGRES_HOST", "localhost") + ":" + env("POSTGRES_PORT", "5432"),
		Path:   env("POSTGRES_DB", "mediflow"),
	}
	return u.String()
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil)).With("service", "patient-flow")
	if err := run(log); err != nil {
		log.Error("stopped", "error", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	loc, err := time.LoadLocation(env("TIME_ZONE", "Africa/Lagos"))
	if err != nil {
		return fmt.Errorf("TIME_ZONE: %w", err)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	pool, err := pgxpool.New(ctx, databaseURL())
	if err != nil {
		return fmt.Errorf("database config: %w", err)
	}
	defer pool.Close()
	pingCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	err = pool.Ping(pingCtx)
	cancel()
	if err != nil {
		return fmt.Errorf("database unreachable: %w", err)
	}

	hub := events.NewHub()
	go events.Listen(ctx, pool, store.NotifyChannel, hub, log)

	schedule, err := flow.ParseSchedule(loc, os.Getenv("CLINIC_HOURS"), os.Getenv("CLINIC_DAYS"))
	if err != nil {
		return err
	}
	httpClient := &http.Client{Timeout: 10 * time.Second}
	server := &api.Server{
		Store:    store.New(pool),
		Tokens:   auth.NewVerifier(env("JWKS_URL", "http://localhost:8000/api/auth/jwks"), env("JWT_ISSUER", "mediflow-core"), env("JWT_AUDIENCE", "mediflow"), httpClient),
		Hub:      hub,
		Loc:      loc,
		Log:      log,
		Now:      time.Now,
		Schedule: schedule,
	}
	srv := &http.Server{
		Addr:              ":" + env("PORT", "8090"),
		Handler:           server.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		IdleTimeout:       60 * time.Second,
		// No WriteTimeout: /api/queue/events is a long-lived stream.
	}

	errCh := make(chan error, 1)
	go func() {
		log.Info("listening", "addr", srv.Addr, "time_zone", loc.String(), "appointments", schedule.Describe())
		errCh <- srv.ListenAndServe()
	}()
	select {
	case err := <-errCh:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case <-ctx.Done():
		log.Info("shutting down")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		return srv.Shutdown(shutdownCtx)
	}
	return nil
}
