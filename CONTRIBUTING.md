# Contributing to MediFlow

Everyone works in this one repository. **Nobody pushes to `main`.** Every change goes through a pull request, and only the maintainer (@gifted-g1) merges.

## The workflow

1. **Pick or get a task.** Your areas and current task are listed in [`.github/team.toml`](.github/team.toml). To change them, edit your entry in a PR.
2. **Create a branch from `main`** named `<github-username>/<area>-<short-topic>`:
   ```bash
   git checkout main
   git pull
   git checkout -b david296-gif/futa-web-queue-page
   ```
3. **Commit small, clear changes** using [Conventional Commits](https://www.conventionalcommits.org):
   `feat(web): add queue page`, `fix(core-api): reject empty password`, `docs: update setup steps`.
4. **Push your branch and open a PR into `main`:**
   ```bash
   git push -u origin david296-gif/futa-web-queue-page
   gh pr create --base main --fill      # or use the link git prints
   ```
5. **CI must pass.** Fix anything red. A reviewer may request changes.
6. **The maintainer merges.** Then delete your branch and start the next task from an updated `main`.

> **Git Bash on Windows:** use forward slashes in paths (`cd /c/Users/you/mediflow-platform`). Backslashes are escape characters there.
> **Never run template commands literally.** Replace placeholders like `<github-username>` first.

## Who is working on what

A bot updates the **"📋 Team status"** issue every weekday morning and whenever a PR opens or closes. It shows each person's task, open PRs, branches without a PR, CI and review state, and what needs attention. To run it yourself:

```bash
GITHUB_TOKEN=$(gh auth token) python scripts/team_status.py
```

## Where things live

| Folder | What | Test / build command (run inside the folder) |
|---|---|---|
| `apps/core-api/` | Django REST API: auth, RBAC, patients, visits, queue | `python manage.py test` |
| `apps/gateway/` | Go auth gateway | `go test ./...` |
| `apps/ai-service/` | FastAPI AI decision support | `pytest -q` |
| `apps/web/` | React client (served by Nginx in Docker) | `npm ci && npm run build` |
| `apps/first-aid-ui/` | React first-aid tips UI | `npm ci && npm run build` |
| `apps/futa-web/` | Legacy FUTA staff frontend (plain JS) | open in a browser |
| `docs/` | Status, architecture, API contracts, team handbook | — |
| `scripts/` | Repo automation (team status) | `pytest -q scripts/tests` |

Full setup: [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md#4-how-to-run-it).

## Rules

- **Never commit** secrets, `.env` files, `.keys/`, databases, `node_modules/`, `dist/`, or real patient data. Use made-up (synthetic) data only.
- **Database changes ship as migrations.** Never edit a migration that's already merged.
- **Keep PRs to one area** where possible. Labels are added automatically from the files you touch.
- **AI features are decision support only.** Never let them diagnose or decide care (see `docs/handbook/AI.md`).
