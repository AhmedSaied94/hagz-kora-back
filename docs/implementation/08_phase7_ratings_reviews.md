# Phase 7 — Ratings & Reviews

**Duration:** Week 10–11  
**Priority:** P1

**Goal:** Players review stadiums they've actually played at. Owners can respond.

**Dependency:** Phase 4 (Booking Engine) — review eligibility requires a completed booking.

---

## Data Model

```
Review
  id, booking FK (unique — one review per booking), player FK, stadium FK,
  overall_rating (1–5, required),
  pitch_quality (1–5, optional),
  facilities (1–5, optional),
  value_for_money (1–5, optional),
  text (plain text, max 500 chars, optional),
  owner_response (text, optional),
  created_at
```

---

## Eligibility Rules

A player may submit a review **only if:**
1. They have a `Booking` at that stadium with `status=completed`
2. No review already exists for that booking (one review per booking)

Enforced via unique constraint on `Review.booking` and server-side eligibility check.

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/bookings/<id>/review/` | POST | Submit review for a completed booking |
| `/api/stadiums/<id>/reviews/` | GET | All reviews for a stadium (paginated, 20/page) |
| `/api/owner/stadiums/<id>/reviews/<r_id>/respond/` | POST | Owner adds/updates response to a review |

---

## Rating Aggregation

- `Stadium.avg_rating` — `DecimalField` updated via Django signal on `Review.post_save`
- Sub-rating averages (`avg_pitch_quality`, `avg_facilities`, `avg_value`) computed via DB aggregation and included in stadium detail response
- Rating displayed on search result cards and stadium detail page

---

## Deliverable

Reviews gated to completed bookings only.  
Owner can respond to any review on their stadiums.  
Aggregate rating updates automatically on new review submission.  
Rating and sub-ratings displayed correctly in search results and stadium detail.
