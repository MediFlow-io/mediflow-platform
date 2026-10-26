# Hosting MediFlow on Render (free) with the database on Neon (free)

About 30 minutes, most of it waiting for the first builds. You need a GitHub login only.

What you get: eight free Render web services (from `render.yaml` at the repo root) and a free Neon
PostgreSQL database that doesn't expire.

| Address | What |
|---|---|
| `https://mediflow-io-web.onrender.com` | Staff app |
| `https://mediflow-io-student.onrender.com` | Student dashboard |
| `https://mediflow-io-admin.onrender.com` | Admin console |

**Free-tier behaviour to expect:** a free Render service sleeps after 15 minutes without visitors and takes
about a minute to wake. The first page after a quiet spell can take 1–2 minutes (several services wake one
after another); after that it's normal speed. Render gives 750 free hours a month across all services.
While the notification service sleeps, live events (e.g. "you've been called") aren't delivered.

What the apps do about it:
- A sleeping Render service only wakes for traffic from the internet. Calls from another Render service
  (our Nginx, the gateway) get Render's 502 page and do not wake it. So opening the web app or student
  dashboard makes the visitor's browser call every backend's public health check directly (the `WAKE_URLS`
  setting on mediflow-io-web and mediflow-io-student), and again if a request finds a service asleep. They
  are usually awake by the time someone signs in.
- A sleeping service answers other services with Render's own 502 page straight away. The gateway retries
  for up to `WAKE_TIMEOUT` (90s), and the apps retry too, with a "server is waking up" notice. Only Render's
  error page is retried, never an answer from our services, so a sign-in or registration is never sent twice.

## Starting again from scratch

To throw away an existing deployment (for example because its secrets were exposed) and rebuild it:

1. Render: open the Blueprint (**Blueprints** in the dashboard) → **Settings → Delete Blueprint**, and tick
   the option to delete its services. Check **Services** afterwards and delete any `mediflow-io-*` left, so
   the names are free again.
2. Neon: delete the old project (**Settings → Delete project**). Everything in that database is lost.
3. Follow steps 1–4 below with new values. Use new secrets: run `make-secrets.sh` again.

## 1. Neon: create the database (5 min)

1. Sign in at <https://console.neon.tech> (GitHub login works).
2. **Create project**: name `mediflow`, Postgres 16 or newer, region **AWS Europe Central 1 (Frankfurt)**
   (the Render services run in Frankfurt too).
3. On the project dashboard, click **Connect**. Turn **Connection pooling OFF** (the notification service
   needs a direct connection for live events), and copy the connection string. It looks like
   `postgresql://neondb_owner:…@ep-…-….eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.

## 2. Secrets (2 min)

In Git Bash, in the `mediflow-platform` folder:

```bash
bash deploy/render/make-secrets.sh > deploy/render/secrets.local.txt
```

This file holds `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `DEMO_PASSWORD` and `APP_KEY`. Files ending in
`.local.txt` here are git-ignored; keep them private.

## 3. Render: create everything from the Blueprint (20 min)

1. If you already made a Render service for this repo by hand (the one failing with "open Dockerfile: no such
   file"), delete it first: its Settings → Delete Web Service.
2. <https://dashboard.render.com> → **New → Blueprint** → connect GitHub → pick
   **MediFlow-io/mediflow-platform**, branch **main**.
3. Render reads `render.yaml` and asks for the values marked "sync: false":

   | Service | Variable | Value |
   |---|---|---|
   | mediflow-io-api | `DATABASE_URL` | the Neon connection string |
   | mediflow-io-api | `JWT_PRIVATE_KEY` | from `secrets.local.txt`, from `-----BEGIN PRIVATE KEY-----` to `-----END PRIVATE KEY-----` |
   | mediflow-io-api | `JWT_PUBLIC_KEY` | from `secrets.local.txt`, the PUBLIC KEY block |
   | mediflow-io-api | `DEMO_PASSWORD` | from `secrets.local.txt`: the password of the demo accounts |
   | mediflow-io-flow | `DATABASE_URL` | the same Neon connection string |
   | mediflow-io-notify | `DATABASE_URL` | the same Neon connection string |
   | mediflow-io-admin | `APP_KEY` | the `base64:…` line from `secrets.local.txt` |

4. **Apply**. Render builds the eight services (10–20 minutes the first time).
5. Check the names: open each service and look at its URL. If one isn't exactly
   `https://<service-name>.onrender.com` (Render adds a suffix when a name is taken), update the matching
   `*_URL` values in the other services (Environment tab) and redeploy them.

## 4. Sign in

- Staff portal: `https://mediflow-io-web.onrender.com/login`, user **admin**, password: the
  `DEMO_PASSWORD` you entered. The same password works for `manager`, `doctor` and `nurse`.
  The landing page is at `https://mediflow-io-web.onrender.com`.
- Student portal: `https://mediflow-io-student.onrender.com`. Students create their own account at
  `/register` and sign in there. Staff accounts are refused on the student portal, and student accounts
  on the staff portal.
- Admin console: `https://mediflow-io-admin.onrender.com`, same `admin` account.
- Students register in the staff app's sign-in page, then use the student dashboard.

## If something goes wrong

| Symptom | Where to look |
|---|---|
| A page spins for a long time | Normal on the first visit after a quiet spell (services waking). Wait 1–2 min and reload |
| "502" or "Bad gateway" | Only if a backend takes over 90s to wake, or failed to start: Render → that service → Logs |
| mediflow-io-api fails to start | Logs say why: usually `DATABASE_URL` (copy it again from Neon) or the JWT keys (paste the whole block) |
| Admin console "service could not be reached" | Wait a minute (backends waking) and retry |
| Notifications don't appear | The notification service was asleep; they work while someone has the app open |

## Moving off the free tier later

Upgrade the services you rely on (at least mediflow-io-api, mediflow-io-flow and mediflow-io-notify) to a
paid instance so they don't sleep, or move everything to one server with Docker (`deploy/README.md`).
