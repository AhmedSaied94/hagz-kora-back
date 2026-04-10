# Hagz Kora — Backend

Egyptian football pitch booking platform. Django 5 REST API consumed by the Flutter mobile app, Owner Dashboard, and Admin Dashboard.

---

## Stack

| Layer | Tech |
|-------|------|
| Framework | Django 5.2 + Django REST Framework 3.15 |
| Database | PostgreSQL 16 + PostGIS (spatial search) |
| Cache / broker | Redis 7 |
| Async tasks | Celery 5 + django-celery-beat |
| Auth | djangorestframework-simplejwt (JWT) |
| API schema | drf-spectacular (OpenAPI 3) |
| Storage | S3 via django-storages (production) / local (dev) |
| Push notifications | Firebase Cloud Messaging |
| Linting | Ruff |
| Testing | pytest + pytest-django |

---

## Running locally

Backing services (DB, Redis, Celery) run in Docker. Django runs natively for fast iteration.

```bash
# 1. Install system deps (Arch Linux)
sudo pacman -S gdal geos proj

# 2. Copy and fill env
cp .env.example .env

# 3. Start backing services
docker compose -f docker-compose.local.yml up -d

# 4. Install Python deps
pip install -r requirements/local.txt --break-system-packages

# 5. Run migrations
python manage.py migrate

# 6. Start Django
python manage.py runserver
```

Health check: `GET /api/health/` — returns `{"status": "ok"}` when DB and Redis are reachable.

API docs: `GET /api/schema/swagger/`

---

## Project layout

```
config/
  settings/
    base.py          # All shared settings — edit here first
    local.py         # Dev overrides (debug toolbar, open CORS, console email)
    production.py    # Prod hardening (SSL, WhiteNoise, S3, Sentry)
  celery.py
  urls.py            # All route mounts
  wsgi.py

apps/
  core/              # TimeStampedModel, health check view
  auth_users/        # Custom User model, OTP auth, JWT, player & owner profiles
  stadiums/          # Stadium CRUD, gallery, operating hours
  bookings/          # Booking engine (Redis-locked slot reservation)
  tournaments/       # Tournament engine, fixtures, standings
  reviews/           # Ratings & reviews
  notifications/     # FCM device tokens, push delivery, broadcast
  dashboards/        # Owner dashboard views + Admin dashboard views

api/
  v1/                # All public REST API — versioned from day one
    auth/            # serializers + views for auth_users endpoints
    stadiums/        # serializers + views for stadiums endpoints
    bookings/        # serializers + views for bookings endpoints
    tournaments/     # serializers + views for tournaments endpoints
    reviews/         # serializers + views for reviews endpoints
    notifications/   # serializers + views for notifications endpoints
    urls.py          # v1 router — included by config/urls.py under /api/v1/

requirements/
  base.txt           # Shared across all environments
  local.txt          # Adds dev/test tools
  production.txt     # Adds gunicorn, whitenoise, sentry
```

---

## API versioning

All serializers and views live in `api/v1/<feature>/`, **not** inside the app packages.  
App packages (`apps/`) contain only models, managers, signals, tasks, and business logic.

```
api/
  __init__.py
  v1/
    __init__.py
    urls.py                    # Aggregates all v1 routers; mounted at /api/v1/ in config/urls.py
    auth/
      __init__.py
      serializers.py           # RegisterSerializer, OTPRequestSerializer, …
      views.py                 # OTPRequestView, OTPVerifyView, TokenRefreshView, …
    stadiums/
      __init__.py
      serializers.py
      views.py
    bookings/
      __init__.py
      serializers.py
      views.py
    tournaments/
      __init__.py
      serializers.py
      views.py
    reviews/
      __init__.py
      serializers.py
      views.py
    notifications/
      __init__.py
      serializers.py
      views.py
```

**Rules:**
- A serializer or view **must never** live inside `apps/`. If you find one there, move it.
- When a v2 is needed, copy the changed modules to `api/v2/` and leave v1 untouched.
- The `api/` package has no models — import from `apps.<app>.models` as needed.
- URL pattern: `/api/v1/<resource>/` — the `/api/v1/` prefix is set once in `config/urls.py`.

---

## Settings

Always use `python-decouple` for env vars — never `os.environ` directly.

```python
from decouple import config

VALUE = config("MY_VAR", default="fallback")
```

Set `DJANGO_SETTINGS_MODULE` in your shell or `.env`:
- Local: `config.settings.local`
- Production: `config.settings.production`

---

## Auth backend toggle

Controlled by the `DJANGO_AUTH_BACKEND` env var:

| Value | Flow | When |
|-------|------|------|
| `email` | Email + password registration/login | Dev / staging |
| `phone` | Phone OTP → JWT | Production |

Check `settings.DJANGO_AUTH_BACKEND` before enabling OTP endpoints. Never expose phone OTP in dev.

---

## Custom User model

`apps.auth_users.User` — defined before the first migration (`AUTH_USER_MODEL`).  
Primary identifier: `phone` (production) / `email` (dev/staging).  
Roles: `player`, `owner`, `admin`.

**Never switch AUTH_USER_MODEL after the first migration.**

---

## Base model

All domain models must inherit from `apps.core.models.TimeStampedModel`:

```python
from apps.core.models import TimeStampedModel

class MyModel(TimeStampedModel):
    ...
```

Provides `created_at` (indexed) and `updated_at` auto fields.

---

## URL namespaces

| Prefix | Module |
|--------|--------|
| `/api/v1/auth/` | `api/v1/auth/views.py` — OTP, login, token refresh, logout |
| `/api/v1/players/` | `api/v1/auth/views.py` — player profile |
| `/api/v1/owners/` | `api/v1/auth/views.py` — owner registration + profile |
| `/api/v1/devices/` | `api/v1/notifications/views.py` — FCM token registration |
| `/api/v1/stadiums/` | `api/v1/stadiums/views.py` |
| `/api/v1/bookings/` | `api/v1/bookings/views.py` |
| `/api/v1/tournaments/` | `api/v1/tournaments/views.py` |
| `/api/v1/reviews/` | `api/v1/reviews/views.py` |
| `/api/v1/notifications/` | `api/v1/notifications/views.py` |
| `/owner/` | `apps/dashboards/` — owner dashboard (session auth) |
| `/admin-panel/` | `apps/dashboards/` — admin dashboard (session auth) |
| `/api/schema/` | drf-spectacular — OpenAPI 3 schema |
| `/api/health/` | `apps/core/views.py` — health check |

Django's built-in `/admin/` is **disabled** in production.  
Dashboard views (`/owner/`, `/admin-panel/`) stay inside `apps/dashboards/` because they are server-rendered Django views, not versioned REST endpoints.

---

## Celery

Queues: `default`, `bookings`, `notifications`

```bash
# Start worker locally
celery -A config worker -l info -Q default,bookings,notifications

# Start beat locally
celery -A config beat -l info
```

All tasks must use `bind=True` and include retry logic:

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def my_task(self, ...):
    try:
        ...
    except SomeTransientError as exc:
        raise self.retry(exc=exc)
```

---

## Database conventions

- Use `select_related` / `prefetch_related` for every FK / M2M traversal — no lazy N+1.
- Prefer ORM over raw SQL. If raw SQL is needed, always use parameterized queries.
- Bilingual text fields use `name_ar` + `name_en` naming (not `translations` FK).
- Spatial fields use `django.contrib.gis.db.models.PointField`.
- All migrations live in `apps/<app>/migrations/` — never hand-edit generated migrations.

---

## API conventions

- All responses use DRF serializers — no hand-built dicts.
- Pagination: `PageNumberPagination`, 20 per page default.
- Filtering: `django-filter` + `SearchFilter` + `OrderingFilter`.
- Error format follows DRF default (`{"detail": "..."}` or field-level `{"field": ["error"]}`).
- Throttling: 100/hour anon, 1000/hour authenticated (tighten per endpoint where needed).

---

## Permission classes

Defined in `apps.auth_users.permissions`:

| Class | Checks |
|-------|--------|
| `IsPlayer` | `request.user.role == "player"` |
| `IsOwner` | `request.user.role == "owner"` |
| `IsAdmin` | `request.user.role == "admin"` |
| `IsOwnerOrAdmin` | owner or admin |
| `IsKycApproved` | owner with `kyc_status == "kyc_approved"` |

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=apps --cov-report=term-missing

# Run only fast unit tests (no DB)
pytest -m unit

# Run integration tests
pytest -m integration
```

**Test structure:**
```
conftest.py              # Root fixtures: api_client, player, owner, admin_user,
                         #   player_client, owner_client, admin_client
tests/
  factories.py           # All factory_boy factories (one file, imported everywhere)
  base.py                # BaseTestCase + BaseAPITestCase with assertion helpers
  unit/                  # Fast tests — no DB, no Redis (@pytest.mark.unit)
  integration/           # Tests that hit real DB / Redis (@pytest.mark.integration)

apps/<app>/tests/        # App-specific tests live inside the app package
```

**Rules:**
- Coverage gate: **80% minimum** (`pyproject.toml` enforces this)
- Use `factory_boy` factories from `tests/factories.py` — never raw `Model.objects.create()` in tests
- Add each phase's model factories to `tests/factories.py` as the model is implemented
- `conftest.py` fixtures (`player`, `owner`, `player_client`, etc.) are available to every test automatically
- Mark every test with `@pytest.mark.unit` or `@pytest.mark.integration`

---

## Linting

```bash
ruff check .          # lint
ruff format .         # format
ruff check --fix .    # auto-fix
```

Pre-commit hooks run Ruff automatically on every commit. Install once:

```bash
pre-commit install
```

---

## Environment variables

See [.env.example](.env.example) for the full list.  
Required at startup: `SECRET_KEY`, `POSTGRES_PASSWORD`.  
Never commit `.env` or `.env.prod`.

---

## Deployment

Production runs all services in Docker:

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec app python manage.py migrate
docker compose -f docker-compose.prod.yml exec app python manage.py collectstatic --no-input
```

CI pipeline (GitHub Actions): lint → test → build Docker image (on `main` only).

---

## Starting a new phase

Before implementing any new phase, always branch off the latest `main`:

```bash
git checkout main
git pull origin main
git checkout -b phase/<phase-name>
```

Never implement a new phase on `main` directly or on a stale branch.

---

## Django implementation standards

Every Django implementation must follow the relevant Claude skill commands:

| Skill | When to use |
|-------|-------------|
| `/django-patterns` | Architecture, REST API design, ORM, caching, signals, middleware |
| `/django-tdd` | Writing tests first with pytest-django, factory_boy, and coverage |
| `/django-security` | Auth, authorization, CSRF, SQL injection, XSS, secure deployment |
| `/django-verification` | Before any PR or release — migrations, lint, tests, security scan |

Run the appropriate skill **before** writing implementation code, not after.

---

## Pre-push checklist

**Always run `/review-pr` before pushing.** Do not push without it.

```bash
# In Claude Code, before git push:
/review-pr
```

This triggers a full blast-radius review of your changes. Address any CRITICAL or HIGH issues before pushing.
