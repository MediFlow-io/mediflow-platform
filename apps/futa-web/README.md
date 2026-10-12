# FUTA staff frontend (legacy)

Plain HTML/CSS/JS pages for health-centre staff: login, registration, dashboard and patient forms.
They call the API on the **same origin** (`/api/login`, `/api/patients`, …) using session cookies,
which the Django core API in `apps/core-api` supports.

> The Node `server.js` that used to serve these pages was never committed. To use them today,
> serve this folder from the same origin as the API (for example behind the Nginx in `apps/web`).
> Planned: move these screens into the React client (see `docs/PROJECT-STATUS.md` § 5).

Owner: see `.github/team.toml` (area `futa-web`).
