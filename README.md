# ACCRA 2026 Accreditation Management System (AMS)

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

The Accreditation Management System (AMS) is a production-grade, secure, and real-time platform for managing the full lifecycle of accreditation for the **ACCRA 2026** tournament. It handles participant onboarding, multi-step application approvals, cryptographic badge generation, and high-speed venue access control via QR scanning — all backed by a horizontally scalable AWS infrastructure.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Security Design](#security-design)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Docker (Full Stack)](#docker-full-stack)
- [Running the Application](#running-the-application)
- [Database Migrations](#database-migrations)
- [Background Workers](#background-workers)
- [Testing](#testing)
- [Environment Variables](#environment-variables)
- [Deployment (AWS)](#deployment-aws)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Role-Based Access Control (RBAC):** Six strict roles — Super Admin, LOC Admin, Accreditation Officer, Organization Admin, Scanner Operator, and Applicant — enforced at both the middleware and ORM layers.
- **Zero-Trust Global Security Middleware:** Every protected request validates a Redis-backed session, preventing hijacked JWTs even after password changes.
- **Participant Onboarding:** Multi-step registration, application submission, and S3 pre-signed document/photo uploads.
- **Multi-Step Application Review:** Officers review, approve, or reject applications and individual documents in bulk or individually, with a full audit trail and email notifications.
- **Cryptographic Badge Generation:** HMAC-SHA256 signed PDF badges with batch generation support, in-memory PDF and photo caching, and automated email delivery via Celery.
- **Badge Revocation:** Instant, O(1) revocation propagated to all venue gates via Redis version invalidation.
- **Venue Access Control:** Sub-300ms QR code scanning with cryptographic forgery detection, Redis anti-passback (Lua script), and 5-minute authorization caching.
- **Live Security Alerts:** WebSocket-based real-time denied-scan notifications on the admin dashboard, backed by Redis Pub/Sub.
- **Zone Access Matrix:** Drag-and-drop access rule configuration with instant Redis cache invalidation.
- **Dashboards & Reporting:** Real-time stats, filterable/paginated scan logs, zone capacity tracking, and CSV export.
- **Multilingual Emails:** Celery + SendGrid with localized HTML templates (EN, FR, PT, ES, AR).
- **GDPR Automation:** Celery Beat daily scheduler for automated PII scrubbing 30 days after tournament end; manual admin trigger available.
- **SendGrid Webhook:** Bounce and spam complaint tracking to protect sender reputation.
- **PII-Safe Logging:** Automatic email masking in all log outputs.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Web Framework** | FastAPI `>=0.104.0` + Uvicorn `>=0.23.2` |
| **Language** | Python 3.11 |
| **Database** | PostgreSQL 15 (via Asyncpg `>=0.28.0`) |
| **ORM** | SQLAlchemy `>=2.0.23` (async) |
| **Migrations** | Alembic `>=1.12.1` |
| **Caching / Pub-Sub** | Redis 7 (`redis>=5.0.1`) |
| **Background Tasks** | Celery `>=5.3.6` + Celery Beat |
| **File Storage** | AWS S3 (via `boto3>=1.33.0`) |
| **Email** | SendGrid `>=6.11.0` |
| **PDF Generation** | ReportLab + PyPDF |
| **QR Codes** | `qrcode>=7.4.2` + `Pillow>=10.0.1` |
| **Auth** | PyJWT `>=2.8.0` + Passlib `>=1.7.4` + bcrypt |
| **Validation** | Pydantic v2 `>=2.4.2` + pydantic-settings |
| **Testing** | pytest `>=7.4.3` + httpx `>=0.25.2` |
| **Containerization** | Docker + Docker Compose |
| **Cloud** | AWS ECS (Fargate), RDS, ElastiCache, S3, ALB, ACM, Route 53 |

---

## System Architecture

```
Internet → Route 53 → ACM (SSL) → ALB (WAF) → ECS Fargate
                                                    ├── FastAPI (API containers)
                                                    └── Celery Worker / Beat containers
                                                           ↕
                                              RDS PostgreSQL ← SQLAlchemy (async)
                                              ElastiCache Redis ← Sessions, Cache, Pub/Sub
                                              AWS S3 ← Photos, Documents, Badge PDFs
                                              SendGrid ← Transactional Email
```

**Key middleware layers (outermost → innermost):**
1. `CORSMiddleware` — Outermost, ensures CORS headers are applied to all responses including 401s.
2. `global_security_middleware` — Validates Bearer JWT + Redis session on every non-public request. Sets `contextvars` tenant context (`user_id`, `role`, `org_id`) for IDOR-safe ORM scoping.

---

## Project Structure

```
Accreditation_system/
├── app/
│   ├── main.py               # App factory, lifespan, middleware, CORS
│   ├── api/
│   │   ├── deps.py           # Shared FastAPI dependencies (auth, RBAC)
│   │   └── v1/
│   │       ├── router.py     # Central API router (v1)
│   │       └── endpoints/    # One file per feature domain
│   ├── config/
│   │   └── settings.py       # Pydantic-settings environment config
│   ├── core/
│   │   └── tenant.py         # ContextVar tenant isolation (IDOR prevention)
│   ├── db/                   # Async DB engine and session factory
│   ├── locales/              # Email translation files (EN/FR/PT/ES/AR)
│   ├── models/               # SQLAlchemy ORM models
│   ├── modules/              # Domain-specific business logic modules
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Service layer (badge, scan, email, S3, etc.)
│   ├── utils/                # Shared utility functions
│   └── workers/
│       ├── main.py           # Celery app + task definitions (email, GDPR)
│       └── tasks/            # Individual Celery task files
├── migrations/               # Alembic migration scripts
├── tests/                    # pytest test suite
├── z_docs/                   # Detailed architecture and API documentation
├── scripts/                  # Utility scripts (e.g., seeding, data clearing)
├── create_admin.py           # Bootstrap first Super Admin account
├── seed_db.py                # Seed tournament, venue, category test data
├── test_scan.py              # Manual scan flow integration test
├── Dockerfile                # Multi-stage production image
├── docker-compose.yml        # Full local stack (API + Worker + Beat + DB + Redis)
├── alembic.ini               # Alembic configuration
├── requirements.txt          # Python dependencies
└── .env                      # Local environment variables (not committed)
```

---

## API Endpoints

All endpoints are prefixed with `/api/v1`. Interactive Swagger docs available at `/docs`.

| Tag | Prefix | Description |
|---|---|---|
| Authentication | `/auth` | Login, register, invite, password reset, force-logout, session management |
| Participants | `/participants` | Create, list, and manage accredited participants |
| Applications | `/applications` | Submit, review (individual & bulk), CSV export, status tracking |
| Badges | `/badges` | Generate (single/batch), download, revoke |
| Scan | `/scan` | QR code scan endpoint, scan logs, live WebSocket alerts |
| Uploads | `/upload` | S3 pre-signed URL generation and upload confirmation |
| Venues | `/venues` | Venue CRUD and access matrix management |
| Tournaments | `/tournaments` | Tournament CRUD (public GET) |
| Zones | `/zones` | Zone CRUD, access rules toggle, capacity endpoint |
| Categories | `/categories` | Category CRUD and organization-category mapping |
| Organizations | `/organizations` | Organization CRUD (public GET) |
| User Management | `/users` | List users, activate/deactivate, force-logout |
| Dashboards & Stats | `/stats` | Real-time aggregated stats |
| Audit & Security | `/audit-logs` | Paginated audit trail for all critical actions |
| GDPR & Compliance | `/gdpr` | Manual PII scrub trigger (Super Admin only) |
| Public Data | `/public` | Public-facing stats and application status tracker |
| Webhooks | `/webhooks` | SendGrid event webhook (bounce/spam tracking) |

**Public paths (no authentication required):**
- `GET /`, `GET /health`, `/docs`, `/openapi.json`
- `POST /api/v1/auth/login`, `POST /api/v1/auth/register`
- `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`
- `GET /api/v1/auth/accept-invite`, `POST /api/v1/auth/resend-invite`
- `GET /api/v1/tournaments/*`, `GET /api/v1/organizations/*`
- `GET /api/v1/public/stats`, `GET /api/v1/applications/public`
- `GET /api/v1/applications/track/status`, `GET /api/v1/applications/options/roles`
- `POST /api/v1/webhooks/sendgrid`
- `GET /api/v1/scan/live-alerts` (WebSocket)

---

## Security Design

| Mechanism | Implementation |
|---|---|
| **JWT + Redis Sessions** | Stateless JWT (30 min) bound to a `session_id` stored in Redis. One active session per user enforced globally. |
| **Zero-Trust Middleware** | Every non-public request validates the Redis session key. Admins can instantly revoke access by deleting the key. |
| **HMAC-SHA256 Badge Signing** | Badges carry a cryptographic signature; the scanner re-computes it on every scan to detect forgeries. |
| **IDOR Prevention** | SQLAlchemy queries are automatically scoped to the requesting user's `org_id` / `user_id` via `contextvars`. |
| **Anti-Passback** | Atomic Redis Lua script prevents race-condition duplicate entries at physical gates. |
| **Rate Limiting** | Redis-backed rate limits on auth endpoints (e.g., forgot-password: 3 requests/min) and scanner devices (10 scans/10 sec). |
| **Brute-Force Protection** | Auth endpoints are rate-limited via Redis. |
| **PII-Safe Logging** | `PIISanitizerFilter` automatically masks email addresses in all log records. |
| **GDPR Scrubbing** | Automated daily Celery Beat job wipes S3 assets and overwrites PII with `"REDACTED"` 30 days post-tournament. |
| **CORS** | Configured via `settings.cors_origins_list`; applied as the outermost middleware to cover all error responses. |
| **ALB / WAF** | Production traffic routes through AWS ALB with WAF rules; raw AWS domain URLs return 403. |

---

## Prerequisites

- Python **3.11+**
- PostgreSQL **15** (local install or Docker)
- Redis **7** (local install or Docker)
- AWS CLI configured (optional for local dev — S3 is skipped when `S3_BUCKET_NAME=local-dummy-bucket`)

---

## Setup & Installation

### 1. Clone the repository

```sh
git clone <repo-url>
cd Accreditation_system
```

### 2. Create and activate a virtual environment

```sh
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```sh
pip install -r requirements.txt
```

### 4. Configure environment variables

```sh
cp .env.example .env
```

Open `.env` and fill in the required values (see [Environment Variables](#environment-variables)).

### 5. Run database migrations

```sh
alembic upgrade head
```

### 6. (Optional) Seed initial data

```sh
# Create the first Super Admin account
python create_admin.py

# Seed tournaments, venues, and categories for testing
python seed_db.py
```

### 7. Start the API server

```sh
uvicorn app.main:app --reload
```

API is available at `http://localhost:8000` — Swagger UI at `http://localhost:8000/docs`.

---

## Docker (Full Stack)

The `docker-compose.yml` spins up the complete local environment: API, Celery Worker, Celery Beat scheduler, PostgreSQL, and Redis.

```sh
# Build and start all services
docker compose up --build

# Run in detached mode
docker compose up -d --build

# Stop all services
docker compose down
```

**Services started:**

| Service | Port | Description |
|---|---|---|
| `api` | `8000` | FastAPI application (auto-runs `alembic upgrade head` on start) |
| `worker` | — | Celery background task worker |
| `celery-beat` | — | Celery Beat periodic task scheduler (GDPR automation) |
| `db` | `5432` | PostgreSQL 15 |
| `redis` | `6379` | Redis 7 |

---

## Running the Application

**Development (hot-reload):**
```sh
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production (via Docker / ECS):**  
The Dockerfile CMD automatically runs migrations then starts Uvicorn:
```sh
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Direct Python entry point:**
```sh
python app/main.py
```

---

## Database Migrations

```sh
# Apply all pending migrations
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Rollback one migration
alembic downgrade -1
```

> In production (AWS ECS), migrations are applied via an ECS **Run Task** command before deploying the new API version.

---

## Background Workers

The system uses Celery for all async workloads. Redis is the message broker.

**Start the Celery worker (handles email, badge generation, etc.):**
```sh
celery -A app.workers.main worker --loglevel=info
```

**Start the Celery Beat scheduler (GDPR automation, periodic tasks):**
```sh
celery -A app.workers.main beat --loglevel=info
```

> With Docker Compose, `worker` and `celery-beat` services are started automatically.

---

## Testing

Ensure your test database connection is configured in `.env`, then run:

```sh
pytest
```

Run with verbose output:
```sh
pytest -v
```

Run a specific test file:
```sh
pytest tests/test_auth.py -v
```

A standalone scan flow integration test is available:
```sh
python test_scan.py
```

---

## Environment Variables

Create a `.env` file in the project root. Key variables:

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost/ams_db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (keep secret!) | `your-very-secret-key` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT validity in minutes | `30` |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 | — |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 | — |
| `AWS_REGION` | AWS region | `us-east-1` |
| `S3_BUCKET_NAME` | S3 bucket for uploads | `local-dummy-bucket` (skips AWS check) |
| `SENDGRID_API_KEY` | SendGrid email API key | — |
| `FRONTEND_URL` | Frontend base URL (used in email links) | `http://localhost:3000` |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | `http://localhost:3000,https://yourdomain.com` |

---

## Deployment (AWS)

The system is designed for **AWS ECS Fargate** deployment:

1. **Build & push Docker image** to Amazon ECR.
2. **Apply migrations** via ECS Run Task (one-off task using the same image).
3. **Deploy** the ECS service (FastAPI + Celery Worker + Celery Beat as separate task definitions).
4. **Infrastructure:**
   - **ALB** — Routes HTTPS traffic; blocks raw AWS URLs (returns 403).
   - **RDS (PostgreSQL 15)** — Managed relational database.
   - **ElastiCache (Redis 7 OSS)** — Cluster-mode disabled for Celery + Pub/Sub compatibility.
   - **S3** — Private bucket for participant photos, documents, and badge PDFs.
   - **ACM + Route 53** — SSL certificate management and custom domain routing.
   - **WAF** — Perimeter security on the ALB.

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Open a Pull Request with a clear description

Please open an issue first for significant changes.

---

## License

This project is licensed under the **MIT License**.

---

> For detailed system logic, API contracts, data models, scan flow sequences, and security architecture, refer to the [`z_docs/`](z_docs/) folder.
