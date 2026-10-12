# MediFlow - Hospital Backend API

[![Django](https://img.shields.io/badge/Django-6.1-green.svg)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.18-red.svg)](https://www.django-rest-framework.org/)
[![SimpleJWT](https://img.shields.io/badge/SimpleJWT-5.5-blue.svg)](https://django-rest-framework-simplejwt.readthedocs.io/)
[![OpenAPI 3.0](https://img.shields.io/badge/OpenAPI-3.0-orange.svg)](https://drf-spectacular.readthedocs.io/)
[![License](https://img.shields.io/badge/License-Proprietary-lightgrey.svg)]()

**MediFlow** is a backend API for modern Hospital Management Systems, engineered with **Django**, **Django REST Framework (DRF)**, **SimpleJWT**, and **drf-spectacular** for automated OpenAPI 3.0 documentation.

The core module provides secure authentication, role-based access control, health card issuance for students, staff credentialing, and JWT lifecycle management with token rotation and blacklisting.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Architecture](#project-architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
  - [Database Migrations](#database-migrations)
  - [Running the Server](#running-the-server)
- [API Documentation & Swagger UI](#api-documentation--swagger-ui)
- [Authentication Endpoints](#authentication-endpoints)
- [Automated Testing](#automated-testing)
- [Environment Variables](#environment-variables)
- [License](#license)

---

## Features

- **Custom User Model (`users.User`)**:
  - Employs `unique_id` as the primary identifier (`USERNAME_FIELD`) supporting university Matriculation Numbers (`SEN/22/9269`) and Staff IDs (`2018002`).
  - Strict email uniqueness with normalization.
  - Role-Based Access Control (`Admin`, `Doctor`, `Nurse`, `Reception`, `Lab`, `Pharmacy`, `IT`, `Student`).
  - Django password validation enforced via a custom `CustomUserManager`.

- **Student Patient Registration**:
  - Validates matriculation format regex (`^[A-Za-z]{2,6}/\d{2,4}/\d{3,6}$`).
  - Strict minimum age enforcement (\(\ge 16\) years old).
  - Phone format validation (strictly 11 digits).
  - Automated unique Health Card Number generation in `<number>/<registration_year>` format (e.g. `0001/2026`).

- **Staff Registration**:
  - Restricted to administrators (`IsAdminUserRole` permission).
  - Allows onboarding of Doctors, Nurses, Receptionists, Lab Technicians, Pharmacists, IT personnel, and Admins.
  - Rejects invalid roles and prevents registering students through staff endpoints.
  - Atomic transaction ensuring both user credentials and linked `StaffProfile` records are created together.

- **JWT Authentication & Lifecycle**:
  - Secure login issuing HMAC-SHA256 signed access and refresh tokens.
  - Token refresh endpoint with rotation enabled (`ROTATE_REFRESH_TOKENS = True`).
  - Token revocation and blacklisting via `rest_framework_simplejwt.token_blacklist`.
  - Secure change-password endpoint enforcing old password verification and password complexity checks.

- **Interactive OpenAPI 3.0 Documentation**:
  - Powered by `drf-spectacular` with offline sidecar UI assets.
  - Native Swagger UI "Authorize" button integrating Bearer JWT headers.
  - Explicit request serializers, error models, and typed status-coded responses for all endpoints.

---

## Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Framework** | Django 6.1+ | Python web framework |
| **API Engine** | Django REST Framework (DRF) 3.18+ | Toolkit for Web APIs |
| **Authentication** | SimpleJWT 5.5+ | JSON Web Token authentication with token blacklisting |
| **Documentation** | drf-spectacular 0.30+ | OpenAPI 3.0 schema generation with Swagger UI & ReDoc |
| **Configuration** | django-environ 0.14+ | Twelve-Factor environment variable management |
| **CORS** | django-cors-headers 4.9+ | Cross-Origin Resource Sharing handling |
| **Database** | SQLite / PostgreSQL | Local file-based DB for dev/tests; PostgreSQL for production |

---

## Project Architecture

```
mediflow/
├── manage.py                     # Django management utility
├── requirements.txt              # Pinned project dependencies
├── .env                          # Local environment variables (git-ignored)
├── .env.example                  # Environment template for onboarding
├── .gitignore                    # Comprehensive version control exclusions
├── README.md                     # Project documentation
├── mediflow/
│   ├── __init__.py
│   ├── settings.py               # Application settings (env, JWT, CORS, OpenAPI)
│   ├── urls.py                   # Root routing & documentation views
│   ├── wsgi.py                   # WSGI server entry point
│   └── asgi.py                   # ASGI server entry point
└── users/
    ├── __init__.py
    ├── apps.py                   # App configuration
    ├── admin.py                  # Django admin registration with inlines
    ├── managers.py               # CustomUserManager with password validation
    ├── models.py                 # User, StudentProfile, and StaffProfile models
    ├── permissions.py            # IsAdminUserRole permission class
    ├── serializers.py            # Request/Response validation serializers
    ├── views.py                  # APIViews decorated with @extend_schema
    ├── urls.py                   # /api/v1/auth/* routing
    ├── migrations/               # Database schema migrations
    └── tests/                    # Automated test suite
        ├── __init__.py
        ├── test_models.py        # Model and manager unit tests
        ├── test_auth.py          # Registration, login, JWT & password tests
        └── test_docs.py          # OpenAPI schema and documentation tests
```

---

## Getting Started

### Prerequisites

- **Python**: Version 3.12 or newer
- **pip**: Latest package manager
- **Git**

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/mediflow.git
   cd mediflow
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Environment Configuration

Copy the sample `.env.example` file to `.env`:

- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **Linux / macOS**:
  ```bash
  cp .env.example .env
  ```

Inspect and update `.env` with your development preferences (e.g., `SECRET_KEY`, `DEBUG`, database credentials).

### Database Migrations

Apply database migrations:

```bash
python manage.py migrate
```

Create an administrator account:

```bash
python manage.py createsuperuser
```

### Running the Server

Start the Django development server:

```bash
python manage.py runserver
```

The API will be accessible at `http://127.0.0.1:8000/`.

---

## API Documentation & Swagger UI

Interactive OpenAPI 3.0 documentation is generated dynamically and served via offline sidecar assets:

| Interface | URL | Purpose |
| :--- | :--- | :--- |
| **Swagger UI** | [`/api/docs/swagger/`](http://127.0.0.1:8000/api/docs/swagger/) | Interactive sandbox with JWT **Authorize** button |
| **ReDoc** | [`/api/docs/redoc/`](http://127.0.0.1:8000/api/docs/redoc/) | Structured three-column technical reference |
| **OpenAPI Schema** | [`/api/schema/`](http://127.0.0.1:8000/api/schema/) | Raw OpenAPI 3.0 YAML specification |

> **Tip:** In Swagger UI, click the **Authorize** button at the top right, enter your token in the format `Bearer <your_access_token>`, and all authenticated requests will automatically include the JWT header.

---

## Authentication Endpoints

Base URL path: `/api/v1/auth/`

| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register/student/` | Register a new student patient & generate Health Card No | `AllowAny` |
| `POST` | `/api/v1/auth/register/staff/` | Register a new hospital staff member (Doctor, Nurse, etc.) | `IsAdminUserRole` |
| `POST` | `/api/v1/auth/login/` | Authenticate user credentials & issue JWT tokens | `AllowAny` |
| `POST` | `/api/v1/auth/token/refresh/` | Exchange a valid refresh token for a new access token | `AllowAny` |
| `POST` | `/api/v1/auth/logout/` | Blacklist the refresh token to revoke session | `IsAuthenticated` |
| `POST` | `/api/v1/auth/change-password/` | Update user password with current password verification | `IsAuthenticated` |

### Sample Payloads

#### 1. Student Registration (`POST /api/v1/auth/register/student/`)
```json
{
  "name": "Jane Doe",
  "unique_id": "SEN/22/9269",
  "email": "jane.doe@mediflow.edu",
  "password": "SecurePassword123!",
  "gender": "Female",
  "dob": "2004-05-18",
  "address": "Campus Hostel Block A",
  "department": "Software Engineering",
  "level": "300",
  "phone": "08012345678"
}
```

#### 2. Staff Registration (`POST /api/v1/auth/register/staff/`)
*Requires `Authorization: Bearer <admin_token>`*
```json
{
  "unique_id": "2018002",
  "email": "doctor.smith@mediflow.org",
  "password": "DoctorPassword123!",
  "role": "Doctor",
  "name": "Dr. Sarah Smith",
  "gender": "Female",
  "department": "Cardiology",
  "phone_number": "08098765432"
}
```

#### 3. Login (`POST /api/v1/auth/login/`)
```json
{
  "unique_id": "SEN/22/9269",
  "password": "SecurePassword123!"
}
```
**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1Ni...",
  "refresh": "eyJhbGciOiJIUzI1Ni...",
  "role": "Student",
  "id": 1,
  "unique_id": "SEN/22/9269",
  "name": "Jane Doe",
  "email": "jane.doe@mediflow.edu"
}
```

---

## Automated Testing

MediFlow comes with a test suite covering models, custom managers, serializers, authentication flows, permission boundaries, and OpenAPI documentation endpoints.

To run the complete test suite:

```bash
python manage.py test users
```

To validate the OpenAPI 3.0 schema:

```bash
python manage.py spectacular --validate
```

---

## Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | `str` | Required | Django secret key for cryptographic signing |
| `DEBUG` | `bool` | `False` | Toggle development debug mode |
| `ALLOWED_HOSTS` | `list` | `localhost,127.0.0.1` | Comma-separated list of allowed hostnames |
| `DB_ENGINE` | `str` | `django.db.backends.sqlite3` | Database engine (`sqlite3` or `postgresql`) |
| `DB_NAME` | `str` | `mediflow_db` | Database name |
| `DB_USER` | `str` | `mediflow_user` | Database user (PostgreSQL) |
| `DB_PASSWORD` | `str` | `""` | Database password (PostgreSQL) |
| `DB_HOST` | `str` | `localhost` | Database host |
| `DB_PORT` | `str` | `5432` | Database port |
| `CORS_ALLOWED_ORIGINS` | `list` | `http://localhost:3000` | Allowed origins for web/frontend clients |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | `int` | `60` | JWT Access token expiration in minutes |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | `int` | `1` | JWT Refresh token expiration in days |

---

## License

This project is proprietary software for the **MediFlow** Hospital Management System. All rights reserved.
