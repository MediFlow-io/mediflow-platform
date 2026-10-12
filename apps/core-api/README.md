# MediFlow Core Backend

> **Start here:** [../../docs/PROJECT-STATUS.md](../../docs/PROJECT-STATUS.md) covers the architecture diagrams, what's built, what's left, and the full run guide (Django + Go gateway + React).

The MediFlow core backend is a Django REST API. It is the source of truth for staff, patients, visits, and the ESI/FCFS queue. It is deliberately a core service rather than an attempt to combine the future Go queue, Flask notification, AI, and reporting services into one application.

## What is implemented

- Session login/logout compatible with the current FUTA frontend (`POST /api/login`, `POST /api/logout`).
- RS256 JWT access/refresh tokens with rotation and revocation; public key published at `GET /api/auth/jwks`.
- Role-based access: admin, doctor, nurse, reception, lab, pharmacy, IT, and student. Students and IT cannot read patient data.
- Go gateway (`../gateway/`) that verifies access tokens and roles before proxying protected auth routes.
- FastAPI AI service (`../ai-service/`): ESI triage suggestions and first-aid Q&A, decision support only, reached via Django `/api/ai/*`.
- Docker Compose stack (Postgres, Django, AI, gateway, Nginx + React) and GitHub Actions CI.
- Patient search and CRUD, using the frontend's camelCase field names.
- Departments and visits/check-ins; each visit has ESI 1–5 and is sorted by ESI then check-in time.
- Queue and dashboard summary endpoints.
- User-management, development seed data, PostgreSQL-ready Docker Compose setup, and API tests.

## Run with Docker (whole stack)

```bash
docker compose up --build
```

Open http://localhost:8080. Migrations and demo data run automatically. See [../../docs/PROJECT-STATUS.md](../../docs/PROJECT-STATUS.md#4-how-to-run-it) for details.

## Run locally

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Django does not read `.env` (only Docker Compose does); the defaults work for local development. The API runs on `http://127.0.0.1:8000`. Serve the current frontend from the same origin through a reverse proxy, or add its development URL to `CORS_ALLOWED_ORIGINS` in `.env`. Do not use the demo accounts outside local development.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/login` | Session login: `{ "staffId", "password" }` |
| POST | `/api/logout` | End current session |
| GET | `/api/me` | Current staff member |
| GET/POST | `/api/patients` | Search (`?search=`) / register patient |
| GET/PUT/PATCH/DELETE | `/api/patients/:id` | Read or manage one patient |
| GET/POST | `/api/visits` | Check-ins and triage visits |
| GET | `/api/queue?department=opd` | Waiting patients, ESI then FCFS |
| GET | `/api/dashboard` | Daily operational counts |
| GET/POST | `/api/users` | Admin-only staff management |
| POST | `/api/auth/login` | JWT login: `{ "unique_id", "password" }` → profile + `access`/`refresh` |
| POST | `/api/auth/token/refresh` | Rotate refresh token (old one is revoked) |
| POST | `/api/auth/logout` | Revoke refresh token |
| POST | `/api/auth/change-password` | `{ old_password, new_password, confirm_password }`; revokes all refresh tokens |
| POST | `/api/auth/register/student` | Public student registration |
| POST | `/api/auth/register/staff` | Admin-only staff account creation |
| GET | `/api/auth/jwks` | Public verifying key for other services |
| POST | `/api/ai/ask` | First-aid question (any signed-in user) |
| POST | `/api/ai/triage` | ESI suggestion (nurse, doctor, admin); advisory only |
| GET | `/api/health` | Health check (public) |

Contracts: [docs/api/auth.yaml](../../docs/api/auth.yaml), [docs/api/ai.yaml](../../docs/api/ai.yaml).

Run the verification suites with `python manage.py test`, `cd ../ai-service && pytest`, and `cd ../gateway && go test ./...`.

## JWT keys

Django signs tokens with an RSA private key; every other service verifies with the public key from `/api/auth/jwks` and must check `alg=RS256`, `iss=mediflow-core`, `aud=mediflow`, `token_type=access` and `exp`. `user_id` is a string claim.

With `DJANGO_DEBUG=true`, a key pair is generated into `.keys/` (git-ignored) on first start. In production, set `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` or mount PEM files at `JWT_KEYS_DIR`; startup fails without them. Revoked refresh tokens are stored in the database (`token_blacklist`); run `python manage.py flushexpiredtokens` periodically.

Run the gateway with `cd ../gateway && DJANGO_BASE_URL=http://localhost:8000 go run .` (port 8080).

## Security notes

Set a strong `DJANGO_SECRET_KEY`, turn `DJANGO_DEBUG=false`, use HTTPS, and restrict `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` before deployment. This starter is not a substitute for clinical validation, a privacy impact assessment, encrypted backups, monitoring, or compliance controls.
