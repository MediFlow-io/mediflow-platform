# Testing Strategy

## Test levels

### Static validation

Run syntax and whitespace checks before every handoff:

```powershell
cd "FE\FUTA Health Centre Project"
Get-ChildItem -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

### Browser smoke tests

With `npm start` running:

1. Open the public homepage.
2. Confirm public quick tips open and display guidance.
3. Log in with a disposable development account.
4. Confirm the dashboard loads without console errors.
5. Confirm the bottom-right AI widget appears only after authentication.
6. Submit a quick tip and an AI enquiry.
7. Create, edit, search, and delete a disposable patient.
8. Open the admin page as admin and create a disposable student.
9. Log out and confirm protected pages redirect to login.

### API tests

For each endpoint test:

- success with valid input;
- malformed JSON;
- missing required fields;
- missing session;
- insufficient role;
- duplicate identifiers;
- not-found resources;
- oversized input where applicable.

Record method, route, expected status, actual status, and result. API examples
are in [API-EXAMPLES.md](./API-EXAMPLES.md).

## Test data

Use clearly fake values such as `Example Patient` and `0000000000`. Reset
`data/users.json` and `data/patients.json` after manual tests. Never use
actual names, phone numbers, diagnoses, or credentials.

## Regression priorities

The highest-risk regression areas are:

- authentication and session expiry;
- admin authorization;
- patient record data loss during edits;
- HTML injection through patient fields;
- AI responses that imply diagnosis;
- accidental disclosure in logs and error messages.

## Future automated tests

Add backend route tests, frontend DOM tests, and browser end-to-end tests when
the project adopts a test runner. Keep tests deterministic, isolate data, and
avoid calling a live AI provider in CI.
