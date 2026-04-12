# Phase 5 — Notifications

**Duration:** Week 7–8 (parallel with Phase 4)
**Priority:** P0 (launch blocker)

**Goal:** Centralized, provider-swappable notification service layer for FCM push and SMS.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| Service layer abstraction design (`fcm.py`, `sms.py`, `dispatcher.py`) | `sonnet-4-6` | Medium | The abstraction boundary is already specified — implement it cleanly; SMS provider must be swappable via env var with zero code changes |
| Celery task definitions (push + SMS, retry logic) | `haiku-4-5` | Low | Formulaic `bind=True` pattern; copy retry config from CLAUDE.md |
| Wiring notification triggers to booking/stadium events | `sonnet-4-6` | Medium | Each trigger in the table must fire via Celery, not inline — verify all are covered |
| FCM device token CRUD | `haiku-4-5` | Low | Upsert on POST, soft-delete on DELETE |
| Locale-based language selection for push content | `haiku-4-5` | Low | Read device locale from `FCMDevice`, pick `_ar`/`_en` field |

> **No extended thinking needed.** This phase is well-specified service wiring. The only judgment call is the `dispatcher.py` routing logic, which Sonnet handles comfortably.

---

## Service Layer Structure

```
services/
  notifications/
    fcm.py        # FCM Admin SDK wrapper — dispatched via Celery tasks
    sms.py        # SMS gateway abstraction (Vonage or local Egyptian provider)
    dispatcher.py # Routes by notification type: determines channels (push/SMS/both)
```

The SMS provider is swappable without touching business logic — abstracted behind `sms.py`.
Configured via `SMS_PROVIDER` and `SMS_API_KEY` environment variables.

---

## Notification Triggers

| Event | Recipients | Channels |
|-------|-----------|---------|
| OTP requested | User | SMS only |
| Booking confirmed | Player | FCM + SMS |
| Booking confirmed | Owner | FCM + SMS |
| Booking cancelled by player | Owner | FCM |
| Booking cancelled by owner | Player | FCM + SMS |
| Stadium approved | Owner | FCM + SMS |
| Stadium rejected | Owner | FCM + SMS |
| Tournament registration opens | Team captains | FCM |
| Tournament match score entered | All team members | FCM |

All SMS content is in Arabic.
Push notifications support Arabic and English based on device locale preference stored at registration.

---

## Device Token Management

```
FCMDevice
  id, user FK, token (unique), platform (android|ios), is_active, updated_at
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices/` | POST | Register or update FCM token on login (upsert by token) |
| `/api/devices/<token>/` | DELETE | Deregister on logout |

On logout: token is deregistered (soft delete — `is_active=False`).
On next login: token is re-registered or updated if rotated by FCM.

---

## Celery Task Pattern

All notification sends are fire-and-forget Celery tasks with retry logic:

```python
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification(self, user_id, title, body, data=None):
    ...

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms(self, phone_number, message):
    ...
```

---

## Deliverable

All notification triggers wired to Celery tasks.
SMS provider swappable via environment variable with zero code changes.
FCM tokens managed per device per user.
