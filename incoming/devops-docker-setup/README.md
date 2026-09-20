# MediFlow Core Backend

The MediFlow core backend is a Django REST API. It is the source of truth for staff, patients, visits, and the ESI/FCFS queue. It is deliberately a core service rather than an attempt to combine the future Go queue, Flask notification, AI, and reporting services into one application.

## What is implemented

- Session login/logout compatible with the current FUTA frontend (`POST /api/login`, `POST /api/logout`).
- Role-based access: admin, doctor, nurse, reception, lab, pharmacy, and IT.
- Patient search and CRUD, using the frontend's camelCase field names.
- Departments and visits/check-ins; each visit has ESI 1–5 and is sorted by ESI then check-in time.
- Queue and dashboard summary endpoints.
- User-management, development seed data, PostgreSQL-ready Docker Compose setup, and API tests.

## Run locally

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

The API runs on `http://127.0.0.1:8000`. Serve the current frontend from the same origin through a reverse proxy, or add its development URL to `CORS_ALLOWED_ORIGINS` in `.env`. Do not use the demo accounts outside local development.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/login` | Session login: `{ "staffId", "password" }` |
| POST | `/api/logout` | End current session |
| GET | `/api/me` | Current staff member |
| GET/POST | `/api/patients` | Search (`?search=`) / register patient |
| GET/PUT/PATCH/DELETE | `/api/patients/:id` | Read or manage one patient |
| GET/POST | `/api/visits` | Check-ins and triage visits |
| GET | `/api/queue?department=opd` | Waiting patients, ESI then FCFS |
| GET | `/api/dashboard` | Daily operational counts |
| GET/POST | `/api/users` | Admin-only staff management |

Run the verification suite with `python manage.py test`.

## Security notes

Set a strong `DJANGO_SECRET_KEY`, turn `DJANGO_DEBUG=false`, use HTTPS, and restrict `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` before deployment. This starter is not a substitute for clinical validation, a privacy impact assessment, encrypted backups, monitoring, or compliance controls.

## Docker Setup

MediFlow is containerized using Docker. The application consists of four services:

* **Frontend** — React application served with Nginx
* **Backend** — Django application served with Gunicorn
* **Gateway** — Go authentication gateway
* **Database** — PostgreSQL

Docker Compose is used to build, connect, and run all services together.

### Project Docker Files

```text
MediFlow-main/
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── gateway/
    └── Dockerfile
```

* `Dockerfile.backend` — builds the Django backend.
* `Dockerfile.frontend` — builds the React frontend and serves it with Nginx.
* `gateway/Dockerfile` — builds the Go authentication gateway.
* `docker-compose.yml` — defines and coordinates all application services.

### Service Ports

| Service    |              Port |
| ---------- | ----------------: |
| Frontend   |              `80` |
| Gateway    |            `8080` |
| Backend    |            `8000` |
| PostgreSQL | `5432` (internal) |

### Running the Application

Make sure Docker and Docker Compose are installed, then from the project root run:

```bash
docker-compose up --build
```

The `--build` option rebuilds the application images before starting the services.

For subsequent runs, when no Dockerfile or dependency changes have been made:

```bash
docker-compose up
```

To run the services in the background:

```bash
docker-compose up -d
```

### Accessing the Application

Once the containers are running:

* Frontend: `http://localhost`
* Gateway health check: `http://localhost:8080/healthz`
* Backend: `http://localhost:8000`

### Checking Containers

To view running containers:

```bash
docker ps
```

To view all containers, including stopped containers:

```bash
docker ps -a
```

To view application logs:

```bash
docker-compose logs -f
```

### Stopping the Application

If running in the foreground, press:

```text
Ctrl + C
```

If running in detached mode:

```bash
docker-compose down
```

### Database Persistence

PostgreSQL uses a Docker named volume called `postgres_data` to persist database data.

The volume is created automatically by Docker Compose and is not removed when running:

```bash
docker-compose down
```

To remove the database volume as well:

```bash
docker-compose down -v
```

> **Warning:** Removing the volume deletes the PostgreSQL data stored in it.
