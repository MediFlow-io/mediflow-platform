# MediFlow

Patient-flow platform for the FUTA Health Centre. Staff register and triage patients; each department gets a live queue ordered by urgency (ESI 1–5), then arrival time. AI decision support suggests triage levels and answers first-aid questions. A clinician always makes the final call.

**This is the single repository for the whole team.** Every part of MediFlow lives here, and all work arrives through pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

**Docker (whole stack):**
```bash
docker compose up --build
```
Open http://localhost:8080 and sign in as `nurse` / `nurse123` (demo account, local only).

**Without Docker:** see [docs/PROJECT-STATUS.md § 4.2](docs/PROJECT-STATUS.md#42-option-b-run-each-service-locally-development).

## Repository layout

```
apps/
├── core-api/        Django REST API: auth (RS256 JWT), RBAC, patients, visits, queue, audit
├── gateway/         Go auth gateway: verifies tokens and roles at the edge
├── ai-service/      FastAPI: ESI triage suggestions + first-aid Q&A (internal only)
├── web/             React client + Nginx image (public entry point)
├── first-aid-ui/    React first-aid tips UI
└── futa-web/        Legacy FUTA staff frontend (plain JS)
docs/                Status & architecture, API contracts, team handbook
scripts/             Team status automation
.github/             CI, team.toml (who works on what), CODEOWNERS, templates
docker-compose.yml   Full stack: postgres, api, ai, gateway, web
```

## Team

- **Who's working on what:** the [📋 Team status](../../issues?q=is%3Aissue+is%3Aopen+label%3Ateam-status) issue, updated automatically from [`.github/team.toml`](.github/team.toml) and live GitHub activity.
- **Rules:** nobody pushes to `main`. Open a PR from `<github-username>/<area>-<topic>`; CI must pass; the maintainer (@gifted-g1) merges.

## Documentation

| Doc | What's in it |
|---|---|
| [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) | Architecture diagrams, what's built, what's left, run guide, troubleshooting |
| [docs/api/](docs/api/) | OpenAPI contracts (auth, AI) |
| [docs/TEAM-GUIDE.md](docs/TEAM-GUIDE.md) | Beginner guide: the product, team responsibilities, ESI queue logic |
| [docs/handbook/](docs/handbook/) | Engineering handbook: security, AI rules, data model, testing |

## License

MIT, see [LICENSE](LICENSE).
