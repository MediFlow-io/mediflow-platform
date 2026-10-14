# patient-flow (Go)

The Go service that **owns visits and the queue**:
- check-in
- the call → start → complete / cancel lifecycle
- the live queue, with server-sent events
- the flow dashboard

It is the only service that writes `patients_visit`. See
[ADR-0002](../../docs/handbook/decisions/ADR-0002-service-ownership.md).

It serves the same API contract the core API used to (`docs/api/core.yaml`), so the React apps didn't
change.

| Route | Who | What |
|---|---|---|
| `GET /api/visits` | staff with patient access | List, with filters `?status=a,b` `?department=opd` `?patient=12` `?today=true` |
| `POST /api/visits` | admin, doctor, nurse, reception | Check in `{patient, department, esi}`. One active visit per patient |
| `GET` / `PATCH /api/visits/{id}` | read: staff · edit: admin, doctor, reception | `esi`, `department`, `arrival_mode` and `assigned_clinician` are editable. `status` is not |
| `POST /api/visits/{id}/{call,start,complete,cancel}` | per action, see `internal/flow` | The only way to change status. `409` if not allowed from the current status |
| `GET /api/queue` | staff with patient access | Waiting patients: ESI first, then arrival. Real minutes waited |
| `GET /api/queue/events` | staff with patient access | Server-sent events (`event: visit`) on every change, after commit |
| `GET /api/dashboard` | all staff | Today's flow numbers |
| `GET /healthz` | anyone | Database check |

## How it works

| Package | Job |
|---|---|
| `internal/flow` | The rules: roles and the visit lifecycle. Pure Go, no I/O |
| `internal/store` | PostgreSQL via pgx. Each write is one transaction: row lock → change → audit entry → `pg_notify`. Check-in locks the patient row, so two simultaneous check-ins can't both succeed |
| `internal/events` | `LISTEN`s for those notifications and fans them out to stream clients. Because events come from PostgreSQL, every instance sees every change, and only after a commit |
| `internal/auth` | Verifies the core API's RS256 tokens using its JWKS |
| `internal/api` | HTTP handlers. Each request re-reads the user's role and active flag from the database, so deactivation takes effect immediately |

The schema belongs to the core API's Django migrations. This service never runs DDL.

## Run

It needs the PostgreSQL database the core API uses (SQLite won't work), migrated by the core API.

```bash
cd apps/patient-flow
POSTGRES_DB=mediflow POSTGRES_USER=mediflow POSTGRES_PASSWORD=... POSTGRES_HOST=localhost \
JWKS_URL=http://localhost:8000/api/auth/jwks go run ./cmd/patient-flow     # :8090
```

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` or `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | `mediflow` on `localhost:5432` | Same variables as the core API |
| `JWKS_URL` | `http://localhost:8000/api/auth/jwks` | Where the signing keys come from |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `mediflow-core` / `mediflow` | Must match the core API |
| `TIME_ZONE` | `Africa/Lagos` | Defines "today" and the queue's HH:MM |
| `PORT` | `8090` | |

## Test

```bash
go test ./...                                            # unit tests (no database needed)
TEST_DATABASE_URL=postgres://user:pass@localhost:5432/mediflow_test go test ./...
```

The integration tests need the core API's schema in a database whose name ends in `_test`. They
truncate tables. They cover:
- concurrent check-ins create exactly one visit
- concurrent transitions apply once
- audit rows are written
- events fire only after a commit
