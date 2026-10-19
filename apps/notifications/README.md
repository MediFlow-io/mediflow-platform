# Notifications (Flask)

Tells people when something changes for them. Ownership is set in [ADR-0002](../../docs/handbook/decisions/ADR-0002-service-ownership.md).

| Who | When | Trigger |
|---|---|---|
| Patient | Called, checked in, cancelled | event |
| Patient | You're next; your turn is near (within `turn_near_ahead` of the front) | event |
| Patient | Appointment booked, confirmed, declined, cancelled by the clinic | event |
| Patient | Appointment reminder about a day before, and within the hour | scheduled |
| Patient | Waiting longer than `long_wait_minutes` ("Sorry for the wait") | scheduled |
| Front desk | New appointment request; appointment cancelled by the patient | event |
| Doctors and nurses | ESI 1–2 patient arrives or is escalated to ESI 1–2 (those rostered for the department now; everyone clinical if nobody is) | event |

Thresholds come from the clinic settings (`/api/clinic/queue-settings`).

```
patient-flow (Go) ──pg_notify('mediflow_visits')──▶ listener ──▶ rules.plan() ──▶ notifications_notification
                                                                              └──▶ email / SMS hooks (optional)
React apps ──/api/notifications──▶ Flask API (own notifications only)
```

## API

All endpoints need an access token (`Authorization: Bearer ...`) and only ever return the caller's own notifications.

| Endpoint | |
|---|---|
| `GET /api/notifications?unread=1&limit=30&before=<id>` | `{results: [...], unread}`, newest first |
| `GET /api/notifications/unread-count` | `{unread}`, for the bell |
| `POST /api/notifications/{id}/read` | Mark one read. Someone else's → `404` |
| `POST /api/notifications/read-all` | Mark all read |
| `GET` / `PUT /api/notifications/preferences` | `{in_app, email, sms}`. Email and SMS can be turned off; in-app can't |
| `GET /healthz` | Database check |

The full contract is in [`docs/api/core.yaml`](../../docs/api/core.yaml).

## How it works

| File | Job |
|---|---|
| `app/rules.py` | Which notifications an event produces. Pure functions, no I/O. Start here to change wording or add a rule |
| `app/store.py` | All SQL. Loads the facts an event refers to and inserts the notifications. `dedupe_key` is unique, so an event handled twice notifies once |
| `app/listener.py` | `LISTEN mediflow_visits` in a background thread, reconnecting with backoff |
| `app/scheduler.py` | Every minute: reminders, long-delay notices, email/SMS retries. One runner across replicas (PostgreSQL advisory lock) |
| `app/channels.py` | Email/SMS hooks. Built-in ones only log. To go live, add a class with `address()` and `send()` and register it in `CHANNELS` |
| `app/auth.py` | RS256 token check against the core API's JWKS (same rules as the Go services) |

Failed email/SMS deliveries are retried after 2 and 4 minutes (3 attempts), then left as `failed` in
`notifications_delivery`. Channels a person turned off are recorded as `skipped`.

Not built yet: web push and inbound webhooks (delivery receipts). Both depend on choosing a provider.

Privacy:
- Text for patients never includes the complaint, vitals or triage level: only where and when. Staff alerts may name the ESI level (shown on the queue anyway), never the complaint.
- Email and SMS carry a generic "you have a new notification" message. The content stays behind the login.
- The patient's own words (an appointment's reason) are never copied into notifications.

Events published while the service is down are not replayed. That is fine for "you've been called", which is
only useful in the moment, but keep it in mind before adding anything that must never be missed.

## Run

The tables come from the core API's migrations (`apps/core-api/apps/notifications`), so run those first.

```bash
pip install -r requirements-dev.txt
flask --app app.wsgi run --port 8095        # development
gunicorn app.wsgi:app --bind 0.0.0.0:8095 --workers 1 --threads 8   # production (Docker does this)
```

Keep one worker process: it also runs the listener. Scale the API by adding replicas with `LISTEN_EVENTS=0`.

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` or `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | `mediflow` on `localhost:5432` | Same as the core API |
| `JWKS_URL` | `http://localhost:8000/api/auth/jwks` | |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `mediflow-core` / `mediflow` | Must match the core API |
| `TIME_ZONE` | `Africa/Lagos` | How appointment times are written |
| `NOTIFY_CHANNELS` | empty | `email,sms` to also deliver on those channels |
| `LISTEN_EVENTS` | `1` | `0` to run the API without the listener |

## Test

```bash
pytest -q                                    # rules, channels and tokens
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/mediflow_test pytest -q   # + PostgreSQL tests (wipes that database)
```
