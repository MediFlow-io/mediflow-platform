# MediFlow Change Checklist

Use this checklist for every pull request. Skip an item only when it is
clearly not applicable and explain why in the pull request.

## Before editing

- Read the relevant guide in this folder.
- Confirm whether the change is frontend, backend, AI, or cross-cutting.
- Check existing routes and scripts before adding new ones.
- Do not overwrite unrelated worktree changes.

## During editing

- Keep API request and response shapes documented.
- Validate user input on the server.
- Keep authorization server-side.
- Avoid logging passwords, session cookies, or patient details.
- Update the relevant guide and `ARCHITECTURE.yml`.

## Before handing over

```powershell
cd "FE\FUTA Health Centre Project"
Get-ChildItem -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
npm start
```

Verify in a browser:

- Login and logout.
- Protected-page redirect when logged out.
- Admin-only student account creation.
- Patient create, edit, search, and delete.
- Bottom-right AI widget after login.
- AI service error handling.

For backend changes, also test an unauthorized request and an invalid input
request; both must fail safely with an appropriate HTTP status.

## Pull request contents

Include:

- Problem statement and scope.
- Files and services changed.
- API or data-contract changes.
- Security/privacy impact.
- Test commands and results.
- Screenshots or a short recording for visible UI changes.
- Migration, deployment, or rollback notes when applicable.

## Release readiness

- No secrets, tokens, credentials, or real health data are committed.
- Documentation and `ARCHITECTURE.yml` match the implementation.
- Backward compatibility has been considered for API consumers.
- Error handling and logging do not expose sensitive information.
- A reviewer has checked accessibility for UI changes.
- A rollback or recovery procedure exists for operational changes.
