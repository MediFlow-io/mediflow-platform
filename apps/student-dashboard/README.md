# Student dashboard

React + Tailwind dashboard where a student sees their **own** health record: today's visit and
place in the queue (live, every 20 s), visit history, allergies and emergency contact.

Data comes from the core API (`GET /api/me` and `GET /api/me/health`). A student only sees a record
after reception **links** it to their matric number (Patients → Edit → *Linked account* in the
staff web app). Diagnosis, treatment and clinical notes are never shown here.

Appointments, vaccines and medications aren't recorded in MediFlow yet, so those tabs say so
rather than showing sample data.

## Run

Needs **Node.js 20.19+ or 22.12+** (Vite 8), plus the core API and gateway running
(see `docs/PROJECT-STATUS.md`).

```bash
npm install
npm run dev      # http://localhost:5174 — proxies /api/auth to :8080 and /api to :8000
npm run lint
npm run build
```

Owner: see `.github/team.toml` (area `student-dashboard`).
