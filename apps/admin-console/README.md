# Admin console (Laravel)

Server-rendered admin console for MediFlow **administrators**:

| Page | What it shows | Data from |
|---|---|---|
| Overview | Today's flow numbers, check-ins over the last 7 days, recent activity | Go `/api/dashboard`, `/api/reports/flow`; Django `/api/audit-logs` |
| Flow reports | Check-ins, completed, cancelled, average wait and consultation time per day, department and ESI level, for up to 92 days. CSV download | Go `/api/reports/flow` |
| Audit log | Every sign-in, record access and patient-flow change, filterable and read-only. Viewing it is itself logged | Django `/api/audit-logs` |
| Departments | Add a department; close or reopen one (closing blocks new check-ins) | Django `/api/departments` |

## How it fits in

Following [ADR-0002](../../docs/handbook/decisions/ADR-0002-service-ownership.md), the console **owns no
patient, visit or account data and has no database**. It signs in through the Go gateway, then reads
and writes only through the other services' APIs, which enforce the admin role on every call.

- Tokens are kept in the **server-side session** (encrypted, 60-minute lifetime) and never reach the browser.
- An expired access token is refreshed once. If the refresh fails, or the account is no longer an admin,
  the console signs the user out.
- Non-admins can't sign in; their just-issued refresh token is revoked straight away.
- CSRF protection on every form, plus strict security headers (`frame-ancestors 'none'`, no third-party
  scripts) and `no-store` caching on signed-in pages.

## Run locally

Needs PHP 8.2+ and Composer, plus the core API, gateway and patient-flow service running
(see `docs/PROJECT-STATUS.md`).

```bash
cd apps/admin-console
composer install
cp .env.example .env
php artisan key:generate
php artisan serve --port=8082        # http://localhost:8082 — sign in as admin
php artisan test
```

| Variable | Default |
|---|---|
| `MEDIFLOW_GATEWAY_URL` | `http://localhost:8080` |
| `MEDIFLOW_API_URL` | `http://localhost:8000` |
| `MEDIFLOW_FLOW_URL` | `http://localhost:8090` |

In Docker, Compose sets these and serves the console at **http://localhost:8082**. Set `ADMIN_APP_KEY`
to your own key (`php artisan key:generate --show`) anywhere other than local development.

Uses Laravel 12. Laravel 11 was rejected because Composer blocks it for open security advisories.
