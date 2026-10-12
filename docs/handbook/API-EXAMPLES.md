# API Examples

These examples target the local server at `http://localhost:3000`. They use
PowerShell and are intended for development troubleshooting, not production
automation.

## Login and session

```powershell
$login = Invoke-WebRequest `
  -Uri http://localhost:3000/api/login `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"staffId":"admin","password":"your-password"}' `
  -SessionVariable session

$login.Content
Invoke-WebRequest http://localhost:3000/api/session -WebSession $session
```

The server sets an HTTP-only session cookie. Keep using the same web session
for subsequent protected requests.

## Ask AI

```powershell
Invoke-WebRequest `
  -Uri http://localhost:3000/api/ai/ask `
  -Method Post `
  -WebSession $session `
  -ContentType "application/json" `
  -Body '{"question":"What should I do for a minor burn?"}'
```

Expected successful shape:

```json
{ "answer": "..." }
```

## Create a student account

This requires an authenticated administrator session.

```powershell
Invoke-WebRequest `
  -Uri http://localhost:3000/api/admin/users `
  -Method Post `
  -WebSession $session `
  -ContentType "application/json" `
  -Body '{"staffId":"student001","fullName":"Example Student","password":"Strong!Password1","role":"student"}'
```

## Search patients

```powershell
Invoke-WebRequest `
  -Uri "http://localhost:3000/api/patients?search=smith" `
  -WebSession $session
```

## Create a patient

```powershell
$patient = @{
  fullName = "Example Patient"
  sex = "Other"
  phone = "0000000000"
  complaint = "Example only"
} | ConvertTo-Json

Invoke-WebRequest `
  -Uri http://localhost:3000/api/patients `
  -Method Post `
  -WebSession $session `
  -ContentType "application/json" `
  -Body $patient
```

Do not use real patient information in examples, fixtures, screenshots, or
manual testing.
