# MediFlow Backend Guide

## Purpose and status

`server.js` is a local development backend and API compatibility layer. It is
useful for demonstrating the current frontend, but it is not production
infrastructure. It uses JSON files and in-memory sessions to avoid external
dependencies.

## Location and runtime

The current development backend is:

```text
FE/FUTA Health Centre Project/server.js
```

It uses only Node.js built-ins and has no npm dependencies. Start it with:

```powershell
cd "FE\FUTA Health Centre Project"
npm start
```

`package.json` defines the start command. The server serves both the static
frontend and the API on `PORT` (default `3000`).

## Configuration

| Variable | Purpose |
|---|---|
| `PORT` | HTTP port; defaults to `3000` |
| `SESSION_SECRET` | Reserved deployment configuration; set a long random value |
| `ADMIN_PASSWORD` | Password used when the initial admin user is created |

For production, replace the JSON storage and in-memory sessions with a real
database and a durable session or token system. Do not use the fallback admin
password in production.

Create a local environment using PowerShell:

```powershell
$env:PORT = "3000"
$env:SESSION_SECRET = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
$env:ADMIN_PASSWORD = "use-a-long-unique-password"
npm start
```

The current server reads `ADMIN_PASSWORD` only when it needs to create the
initial admin user. Changing the variable later does not automatically change
an existing user password.

## API contract

| Method | Route | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/login` | No | Create a session |
| `POST` | `/api/logout` | No | End a session |
| `GET` | `/api/session` | Session | Return current user |
| `POST` | `/api/register` | No | Create a staff account |
| `POST` | `/api/admin/users` | Admin | Create a student account |
| `POST` | `/api/ai/ask` | Session | Return an AI/first-aid answer |
| `GET` | `/api/patients?search=` | Session | List/search patients |
| `GET` | `/api/patients/:id` | Session | Read one patient |
| `POST` | `/api/patients` | Session | Create a patient |
| `PUT` | `/api/patients/:id` | Session | Update a patient |
| `DELETE` | `/api/patients/:id` | Session | Delete a patient |

JSON errors use the shape:

```json
{ "message": "Human-readable error" }
```

### Status code conventions

| Status | Meaning |
|---|---|
| `200` | Successful read, update, or action |
| `201` | Resource created |
| `204` | Successful logout with no response body |
| `400` | Invalid or incomplete request |
| `401` | Missing or invalid session |
| `403` | Authenticated but not authorized |
| `404` | Route or record does not exist |
| `409` | Duplicate account or conflicting resource |
| `500` | Unexpected server failure |

### Account roles

The current roles are `admin`, `staff`, and `student`. Only `admin` may call
`POST /api/admin/users`. Do not rely on a role supplied by the browser; the
server derives authorization from the authenticated session.

## Data and security

- Users are stored in `data/users.json`.
- Patients are stored in `data/patients.json`.
- Passwords are stored as PBKDF2 hashes, never plaintext.
- Sessions are held in memory and expire after eight hours.
- Admin authorization is enforced on the server, not only in the browser.
- Do not store real health records in this JSON development backend.

### Data model summary

Users contain an ID, staff ID, display name, role, password hash, and creation
timestamp. Patients contain an ID, generated hospital number, identity and
contact fields, emergency contact fields, and medical report fields. Preserve
unknown patient fields during updates so newer form fields are not discarded.

### Production gaps

Before production, add a database with migrations, durable sessions, HTTPS,
CSRF protection appropriate to the authentication design, rate limiting,
structured logging with redaction, backups, health checks, monitoring, and
automated tests. Add audit events for patient reads and writes. Obtain a
privacy/compliance review before processing real health information.

## Adding an endpoint

1. Add the route in `handleApi` in `server.js`.
2. Validate request body types, lengths, and required fields.
3. Check authentication with `requireUser` or `requireAdmin`.
4. Return consistent status codes and `{ message }` errors.
5. Update [ARCHITECTURE.yml](./ARCHITECTURE.yml).
6. Update the frontend guide if a browser script consumes it.
7. Test both authorized and unauthorized requests.

## Testing API changes

At minimum test: valid input, missing fields, malformed JSON, unauthenticated
access, insufficient role, duplicate identifiers, not-found records, and
server restart behavior. Use a disposable data directory or restore local
JSON fixtures after manual tests.
