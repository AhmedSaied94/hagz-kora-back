# Phase 2 — Stadium Management

**Duration:** Week 3–5
**Priority:** P0 (launch blocker)

**Goal:** Owners can create and manage stadium listings. Admins can approve/reject.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| Data models (`Stadium`, `StadiumPhoto`, `OperatingHour`, `Slot`) | `sonnet-4-6` | Medium | Spatial `PointField`, JSONField for amenities; no surprises but needs care |
| Stadium CRUD + approval workflow | `sonnet-4-6` | Medium | Standard DRF views; status machine is simple — draft → pending → active |
| Photo upload + S3 pipeline | `sonnet-4-6` | High | Celery task for thumbnail/medium generation; validate file type/size before S3 upload |
| Daily slot generation (Celery Beat) | `sonnet-4-6` | High | Must be idempotent; off-by-one errors in time range generation are common here |
| Gallery reorder endpoint | `haiku-4-5` | Low | Bulk update of `order` field — straightforward |
| Slot block/unblock endpoints | `haiku-4-5` | Low | Simple status toggle with permission guard |
| Admin approval/rejection endpoints | `haiku-4-5` | Low | Status update + trigger notification task |

> **Extended thinking not needed.** Highest complexity is the idempotent slot generator and Celery S3 pipeline — Sonnet at high effort covers both.

---

## Data Models

```
Stadium
  id, owner FK, name_ar, name_en, description_ar, description_en,
  sport_type (5v5|7v7), location (PointField), address_ar, address_en,
  city, price_per_slot, slot_duration_minutes, phone, whatsapp_number,
  amenities (JSONField), status (draft|pending_review|active|suspended),
  rejection_note, created_at, updated_at

StadiumPhoto
  id, stadium FK, s3_url, order, is_cover, thumbnail_url, medium_url

OperatingHour
  id, stadium FK, day_of_week (0–6), open_time, close_time, is_closed

Slot
  id, stadium FK, date, start_time, end_time, status (available|booked|blocked)
```

---

## 2.1 Stadium CRUD (Owner)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stadiums/` | POST | Create stadium (status: draft) |
| `/api/stadiums/<id>/` | GET, PATCH, DELETE | Manage own stadium |
| `/api/stadiums/<id>/submit/` | POST | Submit for review (draft → pending_review) |
| `/api/stadiums/<id>/operating-hours/` | GET, PUT | Set operating hours per day of week |

---

## 2.2 Gallery Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stadiums/<id>/photos/` | GET, POST | List / upload photos |
| `/api/stadiums/<id>/photos/<photo_id>/` | PATCH, DELETE | Update order/cover flag / delete |
| `/api/stadiums/<id>/photos/reorder/` | POST | Bulk reorder (array of IDs) |

**Upload rules:**
- Accepted formats: JPEG, PNG, WebP
- Max file size: 8 MB per photo
- Min 1 photo, max 20 photos per stadium
- One photo must be designated as cover (`is_cover=True`)

**S3 pipeline (Celery):**
1. Validate file type and size
2. Upload original to S3
3. Celery task: generate `thumbnail` (400×300) and `medium` (800×600) variants
4. Store variant URLs on `StadiumPhoto`

**URL access:**
- Player-facing: CDN public-read URLs
- Dashboard: S3 signed URLs with 1-hour expiry

---

## 2.3 Slot Generation

**Celery Beat daily task:** generate slots for `today + 60 days` based on each stadium's `OperatingHour` records.

- Idempotent: slots already existing are not regenerated
- Owner can block/unblock individual slots

**Slot blocking endpoint:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/owner/stadiums/<id>/slots/<slot_id>/block/` | POST | Block a slot |
| `/api/owner/stadiums/<id>/slots/<slot_id>/unblock/` | POST | Unblock a slot |

---

## 2.4 Stadium Approval Workflow (Admin)

**Status flow:** `draft → pending_review → active` (or back to `draft` with rejection note)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/stadiums/pending/` | GET | Queue of pending_review stadiums |
| `/api/admin/stadiums/<id>/approve/` | POST | Set status → active, notify owner |
| `/api/admin/stadiums/<id>/reject/` | POST | Set status → draft + rejection_note, notify owner |

On approval/rejection: push notification + SMS sent to owner.

---

## Deliverable

Owner can create a stadium, upload photos, set operating hours, and submit for review.
Admin can approve or reject from the pending queue.
Approved stadiums have slots auto-generated 60 days ahead.
