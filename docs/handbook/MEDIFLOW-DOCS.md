# MediFlow Documentation

**Document status:** Maintained
**Audience:** Developers, reviewers, maintainers, QA, DevOps, and service owners
**Scope:** Current `MediFlow-FE` checkout and its local Node.js development API
**Last reviewed:** 2026-09-14

This folder is the change guide for the current MediFlow checkout. Read this
file first, then the area-specific document:

- [Frontend guide](./FRONTEND.md)
- [Backend guide](./BACKEND.md)
- [AI guide](./AI.md)
- [Architecture and API map](./ARCHITECTURE.yml)
- [Change checklist](./CHANGE-CHECKLIST.md)
- [Development workflow](./DEVELOPMENT.md)
- [Security guide](./SECURITY.md)
- [Deployment and operations](./OPERATIONS.md)
- [Data model](./DATA-MODEL.md)
- [API examples](./API-EXAMPLES.md)
- [Testing strategy](./TESTING.md)
- [Glossary](./GLOSSARY.md)
- [Architecture decisions](./decisions/README.md)

## Current repository reality

This checkout currently contains a browser frontend and a small Node.js
development backend in `FE/FUTA Health Centre Project`. The larger MediFlow
microservices described in the root project README (Django, Go, Flask,
FastAPI, and Laravel) are not present in this checkout yet.

Do not add a second server or duplicate API contract without first updating
`ARCHITECTURE.yml` and the backend guide.

## Quick start

```powershell
cd "FE\FUTA Health Centre Project"
$env:SESSION_SECRET = "replace-with-a-long-random-secret"
$env:ADMIN_PASSWORD = "replace-with-a-secure-admin-password"
npm start
```

Open `http://localhost:3000`.

The local server creates the initial admin user on first start. Local
development records are stored in `FE/FUTA Health Centre Project/data`.
Never commit real patient data, credentials, or production secrets.

## Documentation conventions

- Paths are repository-relative unless explicitly marked as local.
- API examples use JSON and show the relevant HTTP method and route.
- “Current” means implemented in the checkout documented here.
- “Future” means described by the wider MediFlow architecture but not
  implemented in this repository.
- Update the relevant document in the same change as the code. If a route,
  environment variable, data model, security control, or service boundary
  changes, update `ARCHITECTURE.yml` too.

## Ownership and review

The contributor changing a component owns keeping its documentation accurate.
Reviewers should check both behavior and documentation. Significant API or
security changes should receive review from the backend/security owners before
merge.
