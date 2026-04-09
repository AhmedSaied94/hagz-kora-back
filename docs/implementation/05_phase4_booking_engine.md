# Phase 4 — Booking Engine

**Duration:** Week 6–8  
**Priority:** P0 (launch blocker)

**Goal:** Race-condition-safe slot booking with state management and notifications.

---

## Data Model

```
Booking
  id, player FK, slot FK, stadium FK (denormalized for query performance),
  status (confirmed|cancelled_by_player|cancelled_by_owner|completed|no_show),
  cancellation_reason, cancelled_by, is_late_cancellation,
  price_at_booking, deposit_amount, created_at
```

**Booking status flow:**
```
confirmed → completed         (Celery Beat: slot end_time passed)
confirmed → cancelled_by_player
confirmed → cancelled_by_owner
confirmed → no_show           (future: if player doesn't show)
```

---

## 4.1 Booking Flow

```
POST /api/bookings/
Body: { "slot_id": "uuid" }
```

**Backend sequence (critical — must be atomic):**

1. Validate: player authenticated, slot exists, slot belongs to active stadium
2. Acquire Redis distributed lock: `SET booking:slot:<slot_id> <user_id> NX EX 10`
3. Re-check slot status in DB **inside the lock** (avoid TOCTOU race)
4. **If `available`:**
   - Create `Booking` with `status=confirmed`
   - Update `Slot.status = booked`
   - Release lock
   - Enqueue Celery tasks: FCM + SMS to player and owner
5. **If `booked` or `blocked`:**
   - Release lock
   - Return `409 Conflict` with `{ "code": "SLOT_TAKEN", "error": "This slot was just booked" }`

**Response on success:**
```json
{
  "id": "uuid",
  "stadium_name_ar": "...",
  "stadium_name_en": "...",
  "date": "2025-06-01",
  "start_time": "18:00",
  "end_time": "19:00",
  "price": 150,
  "deposit_amount": 75,
  "status": "confirmed"
}
```

> **Phase 1 note:** Deposit is informational only. No online payment gateway. Full payment is cash at venue.

---

## 4.2 Booking Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/bookings/` | GET | Player's own booking list |
| `/api/bookings/<id>/` | GET | Booking detail |
| `/api/bookings/<id>/cancel/` | POST | Player cancels booking |
| `/api/owner/bookings/` | GET | All bookings for owner's stadiums |
| `/api/owner/bookings/<id>/cancel/` | POST | Owner cancels a booking (reason required) |

---

## 4.3 Cancellation Rules

**Player cancellation:**
- Allowed if `slot.start_time - now > 2 hours`
- If within 2 hours: still allowed but `is_late_cancellation = True` flagged on player profile
- On cancel: `Slot.status` → `available` again

**Owner cancellation:**
- Allowed at any time
- `cancellation_reason` required in request body
- Triggers FCM + SMS notification to player
- On cancel: `Slot.status` → `available` again

---

## 4.4 Celery Beat: Mark Completed Bookings

- **Schedule:** every hour
- **Logic:** find all `Booking` records where `status=confirmed` and `slot.end_time < now(UTC)` → bulk update to `status=completed`

---

## Deliverable

Booking works correctly under concurrent load — no double-bookings possible.  
All booking state transitions handled.  
Cancellation rules enforced.  
Notifications dispatched via Celery for all booking events.
