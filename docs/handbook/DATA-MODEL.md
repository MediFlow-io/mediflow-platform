# Data Model and Record Handling

## Scope

The current development backend stores JSON records in:

```text
FE/FUTA Health Centre Project/data/users.json
FE/FUTA Health Centre Project/data/patients.json
```

These files are fixtures for local development, not a production database.
The field descriptions below document the current browser/API contract.

## User record

```json
{
  "id": "UUID",
  "staffId": "admin001",
  "fullName": "Display Name",
  "role": "admin|staff|student",
  "passwordHash": "salt:derived-hash",
  "createdAt": "ISO-8601 timestamp"
}
```

Rules:

- `id` is server-generated and stable.
- `staffId` is unique, case-insensitive, and limited to the account
  validation format.
- `role` is assigned by the server. A client must not grant itself `admin`.
- `passwordHash` must never be returned to the browser.
- `createdAt` is server-generated.

## Patient record

The current form supports these fields:

| Field | Meaning |
|---|---|
| `id` | Server-generated record identifier |
| `hospitalNumber` | Human-facing record number |
| `fullName` | Patient name |
| `dateOfBirth` | Optional ISO date |
| `sex` | Required current options: Male, Female, Other |
| `phone` | Required contact number |
| `address` | Address |
| `nextOfKin` | Emergency contact name |
| `nextOfKinPhone` | Emergency contact phone |
| `allergies` | Allergy information |
| `medicalHistory` | Previous history |
| `complaint` | Presenting complaint |
| `diagnosis` | Diagnosis notes |
| `treatment` | Treatment/prescription notes |
| `notes` | Additional notes |

`fullName`, `sex`, and `phone` are required by the current API. The backend
must preserve the record ID and should preserve fields it does not own during
partial updates.

## Future database migration

When moving to PostgreSQL or another durable database:

1. Define migrations rather than creating tables manually.
2. Add unique constraints for user staff IDs and hospital numbers.
3. Add foreign keys for visits, diagnoses, prescriptions, and audit events.
4. Add created/updated timestamps and actor IDs.
5. Decide retention, archival, deletion, and legal-hold behavior.
6. Migrate using a reversible, tested process.
7. Never copy production records into a developer workstation without an
   approved de-identification process.
