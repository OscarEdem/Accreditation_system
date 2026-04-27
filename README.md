# ACCRA 2026 Accreditation Management System (AMS)

## Overview
The Accreditation Management System (AMS) is a secure, scalable, and real-time platform for managing the full lifecycle of accreditation for the ACCRA 2026 tournament. It handles participant onboarding, multi-step application approvals, cryptographic badge generation, and high-speed venue access control via QR scanning.


## Features
- **Role-Based Access Control (RBAC):** Strict roles for Super Admin, LOC Admin, Accreditation Officer, Organization Admin, Scanner Operator, and Applicant.
- **Participant Onboarding:** Registration, application submission, and document uploads with dynamic category filtering.
- **Multi-Step Application Review:** Officers can review, approve, or reject applications and documents, with audit logging and email notifications.
- **Badge Generation:** Secure, cryptographically signed PDF badges with automated email delivery and revocation support.
- **Venue Access Control:** Real-time QR code scanning at gates, anti-passback, and instant access decisioning with Redis caching.
- **Live Dashboards & Reporting:** Real-time stats, scan logs, and capacity tracking for venues and zones.
- **Security & Compliance:** Hybrid JWT/session authentication, brute-force protection, GDPR data scrubbing, and zero-trust QR validation.
- **Automated Communications:** Email invites, notifications, and SendGrid webhook integration for bounce tracking.
- **Scalable Infrastructure:** AWS-native deployment with ECS, RDS, ElastiCache, S3, and ALB.

## Tech Stack
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (Asyncpg)
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Caching & Pub/Sub:** Redis
- **Background Tasks:** Celery
- **File Storage:** AWS S3
- **Email:** SendGrid
- **PDF Generation:** ReportLab, PyPDF

## System Architecture
- **Containerized Deployment:** AWS ECS Fargate for FastAPI and Celery workers
- **Load Balancing:** AWS ALB with WAF for perimeter defense
- **Data Layer:** RDS (PostgreSQL), Redis (ElastiCache), S3
- **Security:** VPC isolation, SSL via ACM, NAT Gateway for outbound access

## Security Highlights
- Hybrid JWT and stateful Redis session management
- Strict RBAC and IDOR protection at the ORM layer
- Cryptographic QR badge signing (HMAC-SHA256)
- Automated GDPR data scrubbing and manual purge endpoints
- Rate limiting for authentication and sensitive endpoints

## API Overview
- **Applications:** Create, list, and retrieve applications
- **Participants:** Register and manage participants
- **Scanning:** Real-time QR scan and access control
- **Audit Logs:** Track all critical actions and status changes
- **Stats & Reporting:** Real-time and historical data endpoints

## Prerequisites
- Python 3.10+
- PostgreSQL (Running locally or via Docker)
- Redis (For caching, rate limiting, and session management)
- AWS CLI (Configured for S3/ECR access, optional for local dev)

## Setup & Installation
1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd Accreditation_system
   ```
2. **Create and activate a virtual environment:**
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and ensure `DATABASE_URL` and `REDIS_URL` are set.
5. **Run database migrations:**
   ```sh
   alembic upgrade head
   ```
6. **Start the application:**
   ```sh
   uvicorn app.main:app --reload
   ```

## Testing
To run the automated test suite, ensure your test database is configured in `.env` and run:
```sh
pytest
```

## Usage
- Access the API at `http://localhost:8000/docs` for interactive Swagger documentation.
- Use the provided endpoints for registration, application submission, badge generation, and scanning.
- Admin and officer features are accessible based on assigned roles.

## Contributing
Contributions are welcome! Please open issues or submit pull requests for improvements or bug fixes.

## License
This project is licensed under the MIT License.

---
For detailed system logic, API contracts, data models, and security architecture, see the `z_docs/` folder.
