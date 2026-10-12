# Development Workflow

## Prerequisites

For the current checkout install:

- Git
- Node.js 18 or newer
- A modern browser
- PowerShell on Windows, or an equivalent shell

No npm package installation is required for the current Node.js server.

## Local setup

```powershell
git clone https://github.com/MediFlow-io/MediFlow-FE.git
cd MediFlow-FE
cd "FE\FUTA Health Centre Project"
$env:SESSION_SECRET = "local-only-long-secret"
$env:ADMIN_PASSWORD = "local-only-admin-password"
npm start
```

Visit `http://localhost:3000`. Keep the server running while testing browser
flows. Opening HTML with `file://` bypasses the API and is not a valid test.

## Branching and commits

Use a focused branch such as `feature/ai-widget` or `fix/patient-search`.
Keep commits small and explain behavior changes. Do not commit generated
records from manual testing. Follow the repository's pull-request policy and
include the checklist from `CHANGE-CHECKLIST.md`.

## Debugging order

1. Check the browser console and Network panel.
2. Confirm the request route, method, status, and response body.
3. Check the Node process output.
4. Confirm environment variables are set in the same shell as `npm start`.
5. Check JSON fixture validity and permissions.
6. Reproduce with a minimal request before changing code.

## Common problems

| Symptom | Likely cause | Action |
|---|---|---|
| `404 /api/...` | Static server used instead of Node server | Run `npm start` |
| Redirect to login | No session or expired session | Log in again; inspect `/api/session` |
| `403` on student creation | Account is not an admin | Use an admin session |
| Login fails after changing `ADMIN_PASSWORD` | Existing admin was not reset | Remove local fixture only, then restart |
| AI box absent | User is not authenticated or widget script missing | Check session and page script order |
| JSON parse error | Corrupt fixture or malformed request | Restore fixture and inspect request body |

## Adding a dependency

Prefer Node built-ins for this small development server. If a dependency is
necessary, update `package.json` and lockfile, document why it is needed,
review its license/security posture, and run a clean install before merging.
