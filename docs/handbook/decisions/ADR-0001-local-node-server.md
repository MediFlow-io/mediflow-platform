# ADR-0001: Local Node Development Server

- Status: Accepted for development only
- Date: 2026-09-14
- Owners: MediFlow maintainers

## Context

The current frontend needs working authentication, patient routes, account
creation, and AI enquiry behavior, but the wider MediFlow backend services are
not present in the frontend checkout.

## Decision

Use a dependency-free Node.js server in
`FE/FUTA Health Centre Project/server.js` to serve static files and provide a
small local API compatibility layer. Store development records in JSON files
and sessions in memory.

## Alternatives considered

- Opening HTML directly: cannot provide `/api` routes or authentication.
- Adding a full database stack immediately: increases setup cost for a demo
  and is outside the current frontend scope.
- Calling a provider directly from the browser: would expose credentials and
  bypass server-side authorization.

## Consequences

Local setup is simple and the frontend can be demonstrated end-to-end.
However, the design is single-process, non-durable, not horizontally
scalable, and unsuitable for real patient records or production deployment.

## Follow-up

Replace JSON storage and in-memory sessions with the agreed core backend and
database. Preserve the browser-facing API contract or document a versioned
migration for consumers.
