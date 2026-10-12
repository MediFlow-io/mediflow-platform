# Deployment and Operations

## Development

Run the Node server from `FE/FUTA Health Centre Project` with `npm start`.
Use a process manager or container only after documenting the chosen runtime
and environment configuration.

## Pre-deployment checklist

- Use a strong unique `SESSION_SECRET` and admin credential.
- Set `NODE_ENV`/deployment configuration according to the hosting platform.
- Put the service behind HTTPS and a reverse proxy.
- Disable or remove demo credentials and public account registration if not
  required.
- Replace JSON files with a managed database and configure backups.
- Configure log redaction, monitoring, health checks, and alerting.
- Review CORS, cookie, CSRF, rate-limit, and security-header policy.
- Confirm no fixture contains real patient data.

## Health and observability

The current server has no dedicated health route or metrics endpoint. A future
deployment should provide a non-sensitive health check, structured request
logging, latency/error metrics, dependency checks, and alert thresholds.
Never include passwords, cookies, prompts, or medical records in health output.

## Backup and recovery

For the current development files, stop the server before copying JSON data.
For production, use database-native backups, encryption, retention policies,
restore drills, and documented recovery-point/recovery-time objectives.

## Scaling limitations

In-memory sessions are local to one process. JSON writes are not suitable for
concurrent instances. Before horizontal scaling, move sessions and records to
shared durable services and define migration/rollback procedures.
