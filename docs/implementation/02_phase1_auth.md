# Phase 1 — Authentication & User Profiles

**Duration:** Week 2–3
**Priority:** P0 (launch blocker)

**Goal:** Players and Owners can register, verify, and authenticate. JWT tokens issued.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| OTP security design (hashing, rate limiting, lock strategy) | `opus-4-6` | Extended thinking | Security-critical and irreversible design choices; think through all attack vectors |
| JWT config (TTLs, blacklist, rotation strategy) | `opus-4-6` | High | Wrong TTL or missing blacklist = auth vulnerability |
| OTP endpoints implementation | `sonnet-4-6` | High | Follow design from Opus step; enforce all rules from §1.2 |
| Email/password auth (dev only) | `sonnet-4-6` | Medium | Simpler flow; validate backend toggle is correctly gated |
| Player & Owner profile endpoints | `sonnet-4-6` | Medium | Standard CRUD; ensure role-based permission classes are wired |
| FCM device token registration | `haiku-4-5` | Low | Straightforward upsert pattern |
| Permission classes (`IsPlayer`, `IsOwner`, etc.) | `haiku-4-5` | Low | Simple role checks; defined once, reused everywhere |

> **Run `/django-security` before writing any auth code.** OTP flows are the highest-risk surface in the entire backend.

---

## 1.1 Custom User Model

```
User: id, phone, email, full_name, role (player|owner|admin), is_active, date_joined
```

- Must be defined before first migration — `AUTH_USER_MODEL = 'auth_users.User'`
- `phone` is the primary identifier in production; `email` in test/staging mode

---

## 1.2 Phone OTP Auth (Production)

Active when `DJANGO_AUTH_BACKEND=phone`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/otp/request/` | POST | Generate 6-digit OTP → Redis (5 min TTL) → SMS |
| `/api/auth/otp/verify/` | POST | Validate OTP → invalidate immediately → return JWT pair |

**Rules:**
- Rate limit: 3 requests per phone per 15 minutes
- After 3 failed verify attempts → lock phone for 15 minutes
- OTP stored as **hashed** value in Redis, never plaintext
- OTP invalidated immediately after successful use

---

## 1.3 Email/Password Auth (Dev/Staging)

Active only when `DJANGO_AUTH_BACKEND=email`. Never available in production.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register/` | POST | Email + password registration |
| `/api/auth/login/` | POST | Return JWT pair |

---

## 1.4 JWT Token Management

Library: `djangorestframework-simplejwt` with token blacklist enabled.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/token/refresh/` | POST | Rotate refresh token |
| `/api/auth/logout/` | POST | Blacklist refresh token |

| Token | TTL |
|-------|-----|
| Access token | 60 minutes |
| Refresh token | 30 days |

---

## 1.5 Player Profile

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/players/me/` | GET, PATCH | View/edit own profile |
| `/api/players/me/bookings/` | GET | Booking history |
| `/api/players/me/tournaments/` | GET | Tournament participation history |

**Fields:** full name, phone (read-only), profile photo (optional), preferred position (optional), date of birth (optional), city

---

## 1.6 Stadium Owner Profile & KYC

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/owners/register/` | POST | Submit owner profile + national ID |
| `/api/owners/me/` | GET, PATCH | Owner profile |

**Owner status flow:** `pending_kyc → kyc_approved → active`

- Admin approves KYC via Admin Dashboard
- Owner cannot publish stadiums until status is `kyc_approved`
- Fields: full name, phone, business name, national ID, city, bank account info (future payouts)

---

## 1.7 FCM Device Token

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices/` | POST | Register/update FCM token on login |
| `/api/devices/<token>/` | DELETE | Deregister on logout |

---

## Deliverable

Full auth flow working. JWT issued on successful OTP/login. Role-based permission classes in place:
- `IsPlayer`
- `IsOwner`
- `IsAdmin`
- `IsOwnerOrAdmin`
