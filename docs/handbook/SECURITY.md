# Security and Privacy Guide

## Sensitive data classification

Patient identity, contact details, diagnoses, prescriptions, medical history,
and AI questions containing health information are sensitive. Treat account
credentials, session cookies, API keys, and environment files as secrets.

## Required controls

- Enforce authorization on every protected backend route.
- Hash passwords; never log or store plaintext passwords.
- Use HTTPS and secure cookie flags in deployed environments.
- Validate length, type, format, and allowed values on the server.
- Escape or safely render user-controlled content in the browser.
- Redact health data and credentials from logs and error messages.
- Use least-privilege service accounts and rotate secrets.
- Back up production data securely and test restoration.
- Define retention and deletion procedures for health records and AI prompts.

## Current development limitations

The local server uses JSON files and an in-memory session map. It is not
suitable for real patient data, multiple instances, production availability,
or regulated deployment. `personal.env` and equivalent files must never be
committed.

## Incident response

If a secret or health record is committed: stop sharing it, revoke/rotate the
secret, preserve relevant audit information, notify the repository owner, and
follow the organization's privacy incident process. Do not silently rewrite
history and assume exposure is resolved.

Security issues should be reported privately to the maintainers rather than
opened publicly with exploit details.
