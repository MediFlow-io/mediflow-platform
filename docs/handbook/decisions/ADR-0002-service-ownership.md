# ADR-0002: Service ownership — Go owns patient flow

- Status: Accepted
- Date: 2026-10-13
- Owner: @gifted-g1 (team lead)

## Context

MediFlow runs several languages: Go, Python (Django, FastAPI), React, and later PHP/Laravel. Without clear
ownership, two services end up writing the same records and their rules drift apart. Until now Django
owned everything, and Go was only an auth gateway.

## Decision

Every domain has **one authoritative writer**. Other services read through that owner's API, or, where
noted, read its tables without writing to them.

| Domain | Owner (only writer) | Code |
|---|---|---|
| Accounts, login, JWT issuing, roles | Django | `apps/core-api` (accounts) |
| Patient records, student ↔ record link, payment category, long-term conditions | Django | `apps/core-api` (patients) |
| **Clinical records (EMR Lite): notes, diagnoses, prescriptions, referrals, admissions** | **Django** | `apps/core-api` (emr), under `/api/emr` |
| **Clinic settings: hours, holidays, queue rules, staff rota** | **Django** (stored), Laravel (edits) | `apps/core-api` (clinic) |
| Departments | Django (admin) | `apps/core-api` |
| **Visits: check-in, call/start/complete/cancel** | **Go** | `apps/patient-flow` |
| **Queue, live updates, flow dashboard** | **Go** | `apps/patient-flow` |
| **Appointments: requests, bookings, same-day check-in** | **Go** | `apps/patient-flow` |
| AI triage and first-aid answers | FastAPI | `apps/ai-service` (called via Django) |
| **Notifications: in-app, plus email/SMS hooks** | **Flask** | `apps/notifications`: turns patient-flow events into notifications |
| Audit log | Shared, append-only | every service inserts; nobody updates or deletes |
| Admin console and reporting | Laravel | `apps/admin-console`: reads through the APIs, no database of its own |
| Edge auth checks | Go gateway | `apps/gateway` |

Technology choices:
- **Database: PostgreSQL** (one cluster). MySQL was considered and rejected for now: PostgreSQL already
  runs and is CI-tested, and both Go and Laravel support it well.
- **Flask owns notifications** (amendment, 2026-10-16, see below). Plain PHP is not used.

Rules:
1. **Schema changes go through Django migrations** for now, including `patients_visit`, so there is one
   migration history. Go never runs DDL. Revisit this if Go's tables diverge from Django's models.
2. Go writes visits inside transactions with row locks and records audit entries in the same transaction.
3. Django still *reads* visits for `GET /api/me/health` (a student's own record). That read-only access is
   allowed; Django must not write visits.
4. Go keeps the documented API contract (`docs/api/core.yaml`) so the React apps don't change when
   ownership moves.
5. Routing is by path: Nginx (Docker) and the Vite dev proxies send `/api/visits*`, `/api/queue*` and
   `/api/dashboard` to Go, and the rest of `/api` to Django.

## Consequences

- Go can add real-time features (queue events) without a second writer for visits.
- Authorization is enforced in two places (Django and Go) from the same JWT and the same `accounts_user`
  row. Go re-reads the role and `is_active` flag from the database on every request, so deactivations take
  effect immediately in both services.
- The role and transition rules now live in Go (`internal/flow`). Django's copy was removed so the two
  can't drift apart.

## Amendment (2026-10-16): Flask owns notifications

The team chose Flask for a notification service. It has a job no other service does, so it doesn't
duplicate anything:

- It **listens** on the same PostgreSQL channel the Go service publishes (`mediflow_visits`), after commit.
  Go doesn't call it and doesn't wait for it: if it's down, check-ins and the queue keep working, and only
  notifications for that period are lost.
- It is the **only writer** of `notifications_notification` and `notifications_delivery`. As with every
  table, the schema comes from a Django migration (`apps/core-api/apps/notifications`).
- It **reads** visits, appointments, patients, departments, users, triage changes, clinic settings and
  rosters, and the audit log (to know who made a change). It never writes them.
- It also owns `notifications_preference`. Its scheduled jobs run on one instance at a time (advisory lock).
- It verifies the same RS256 access tokens via the JWKS, and re-reads `is_active` on every request.
- Notification text has no clinical details. Email/SMS (when a provider is plugged in) only say "you have a
  new notification": the content stays behind the login.
- Routing: `/api/notifications*` goes to Flask in Nginx and the Vite dev proxies.

