# MediFlow Frontend Guide

## Purpose and status

The frontend is a dependency-light browser application built from HTML, CSS,
and JavaScript. It is currently not a React application despite the broader
MediFlow architecture proposal mentioning React and Tailwind. The files in
this guide are the source of truth for the current implementation.

## Location

All current frontend files are in `FE/FUTA Health Centre Project`.

| Area | Files |
|---|---|
| Public pages | `index.html`, `public index.html`, `homepage.js` |
| Authentication | `login.html`, `js/login.js`, `register.html`, `js/register.js`, `auth-guard.js` |
| Dashboard | `dashboard.html`, `dashboard main.html`, `js/dashboard.js` |
| Patient records | `patient-form.html`, `patient form.html`, `js/patient-form.js`, `patient form.js` |
| Admin students | `admin-users.html`, `js/admin-users.js`, `admin-guard.js` |
| Styling | `public style.css` |
| AI UI | `ai-assistant.js`, `ai-widget.js` |

Some files have a space and a hyphenated duplicate because both versions exist
in the current project. Keep both copies synchronized until the duplicate pages
are consolidated.

## How the frontend works

Pages are plain HTML. Scripts are loaded at the bottom of each page. The
frontend uses browser `fetch` calls to the relative `/api/...` routes served by
`server.js`; this keeps local and deployed paths consistent.

Authentication is cookie-based:

1. `js/login.js` posts credentials to `/api/login`.
2. The server sets an HTTP-only `session` cookie.
3. `auth-guard.js` checks `/api/session` before protected pages continue.
4. `admin-guard.js` additionally requires `role: "admin"`.

## Page lifecycle and responsibilities

| Page | Public/protected | Primary responsibility |
|---|---|---|
| `index.html` | Public | Landing page and public first-aid assistant |
| `login.html` | Public | Creates an authenticated session |
| `register.html` | Public | Requests a staff account |
| `dashboard.html` | Protected | Searches and manages patient records |
| `patient-form.html` | Protected | Creates or edits a patient record |
| `admin-users.html` | Admin | Creates student accounts |

`dashboard main.html`, `public index.html`, and the files with spaces are
legacy/duplicate entry points. They should remain synchronized until a
deliberate consolidation removes them.

## Browser state and accessibility

- Authentication state belongs to the server-side cookie; do not place
  passwords or session identifiers in `localStorage`.
- Use `aria-live` for asynchronous messages and preserve visible labels.
- Buttons that open panels must maintain `aria-expanded` and `aria-controls`.
- Keep keyboard focus usable when adding dialogs, popovers, or widgets.
- Use semantic headings and controls before adding styling hooks.

## Error and loading behavior

Every network action should have three visible states: loading, success, and
failure. A `401` should redirect to `login.html`; a `403` should explain that
the user lacks permission; validation errors should be shown beside or above
the relevant form. Do not display a success message when the API request
failed or returned malformed data.

## Browser security

Prefer `textContent` and DOM APIs over `innerHTML`. If a template must use
`innerHTML`, escape every server-controlled value first. Never put API keys,
passwords, or privileged decisions in frontend code. The browser guard is a
UX feature; authorization must remain on the backend.

## Making a frontend change

1. Find the page and script in the table above.
2. Reuse existing classes from `public style.css`.
3. Keep API calls relative (`/api/...`).
4. Add loading, success, and error states for network actions.
5. Escape user content before inserting it into HTML. Prefer `textContent`.
6. If a page is protected, include `auth-guard.js`; if it is admin-only,
   include `admin-guard.js`.
7. Test the page through `npm start`, not only by opening the HTML file directly.

## AI surfaces

- The larger inline assistant is `ai-assistant.js`.
- The authenticated bottom-right notification box is `ai-widget.js`.
- Both call `POST /api/ai/ask`.
- The widget first checks `/api/session`, so it appears only after login.

## Frontend validation

```powershell
Get-ChildItem -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

For manual checks, test at desktop and narrow mobile widths, with JavaScript
errors visible in the browser console. Test both a successful API response and
an unavailable backend response.
