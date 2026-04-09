# Hagz Kora — Backend API

Django REST API powering the Hagz Kora football pitch booking platform. Connects players to stadium owners, handles reservations, and runs a tournament engine.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.1 + Django REST Framework 3.15 |
| Database | PostgreSQL 16 + PostGIS 3.x (spatial search) |
| Cache / Queue | Redis 7 + Celery 5 + django-celery-beat |
| Auth | JWT via djangorestframework-simplejwt |
| API Docs | drf-spectacular (OpenAPI 3 / Swagger) |
| Storage | S3 via django-storages (prod) / local (dev) |
| Push Notifications | Firebase Cloud Messaging |
| Linting / Formatting | Ruff |
| Testing | pytest + pytest-django + factory-boy |

---

## Project Structure

```
backend/
├── apps/
│   ├── auth_users/      # Custom User model, OTP/JWT, player & owner profiles
│   ├── stadiums/        # Stadium CRUD, gallery, operating hours
│   ├── bookings/        # Redis-locked booking engine, slot management
│   ├── tournaments/     # Fixture generation, standings
│   ├── reviews/         # Ratings & reviews (gated to completed bookings)
│   ├── notifications/   # FCM device tokens, push delivery
│   ├── dashboards/      # Owner & Admin dashboard views
│   └── core/            # TimeStampedModel, health check
├── api/v1/              # Versioned REST endpoints
│   ├── auth/
│   ├── stadiums/
│   ├── bookings/
│   ├── tournaments/
│   ├── reviews/
│   └── notifications/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── celery.py
├── tests/
│   ├── factories.py
│   ├── base.py
│   └── integration/
└── docs/implementation/  # Phase-by-phase implementation guides
```

---

## Getting Started

### Prerequisites

- Python 3.12
- Docker & Docker Compose

### Local Development

```bash
# 1. Clone the repo
git clone git@github.com:AhmedSaied94/hagz-kora-back.git
cd hagz-kora-back

# 2. Copy environment variables
cp .env.example .env
# Edit .env with your local values

# 3. Start services (DB, Redis)
docker compose -f docker-compose.local.yml up -d

# 4. Install Python dependencies
pip install -r requirements/local.txt

# 5. Run migrations
python manage.py migrate

# 6. Start the dev server
python manage.py runserver
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/api/schema/swagger/`

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for local, `False` for production |
| `POSTGRES_*` | PostgreSQL connection details |
| `REDIS_URL` | Redis connection URL |
| `DJANGO_AUTH_BACKEND` | `email` (dev/staging) or `phone` (production OTP) |
| `FIREBASE_*` | Firebase credentials for push notifications |
| `AWS_*` | S3 credentials for media storage |

---

## Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=apps --cov-report=term-missing

# Only unit tests (no DB)
pytest -m unit

# Only integration tests
pytest -m integration
```

Coverage gate: **70%** (target: 80% as features are implemented).

---

## CI Pipeline

GitHub Actions runs on every push to `main` and `develop`:

1. **Lint** — `ruff check .` + `ruff format --check .`
2. **Test** — pytest with PostgreSQL + Redis services
3. **Build** — Docker production image build (main branch only)

---

## Implementation Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation (Docker, CI, health check) | ✅ Done |
| 1 | Auth & profiles (OTP, JWT, player/owner) | 🔲 Pending |
| 2 | Stadium management (CRUD, gallery, hours) | 🔲 Pending |
| 3 | Search & discovery (PostGIS, filters) | 🔲 Pending |
| 4 | Booking engine (Redis locks, slots) | 🔲 Pending |
| 5 | Push notifications (FCM) | 🔲 Pending |
| 6 | Tournament engine (fixtures, standings) | 🔲 Pending |
| 7 | Reviews & ratings | 🔲 Pending |
| 8 | Owner & Admin dashboards | 🔲 Pending |
| 9 | Production hardening | 🔲 Pending |

See `docs/implementation/` for detailed phase guides.

---

## API Overview

All endpoints are under `/api/v1/`. Authentication uses JWT Bearer tokens.

| Prefix | Domain |
|---|---|
| `/api/v1/auth/` | Registration, login, OTP, token refresh |
| `/api/v1/stadiums/` | Stadium listing, detail, search |
| `/api/v1/bookings/` | Create, cancel, list bookings |
| `/api/v1/tournaments/` | Tournament management, fixtures |
| `/api/v1/reviews/` | Stadium reviews and ratings |
| `/api/v1/notifications/` | Device registration, notification history |
| `/api/health/` | Health check (no auth required) |
