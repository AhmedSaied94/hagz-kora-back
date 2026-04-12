# Phase 3 — Search & Discovery

**Duration:** Week 5–6
**Priority:** P0 (launch blocker)

**Goal:** Players can find stadiums by location, date, sport type, and time.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| PostGIS query design (`ST_DWithin`, distance annotation, available slot subquery) | `opus-4-6` | Extended thinking | Spatial indexing strategy, subquery vs. JOIN trade-offs, and cache key design all interact — think them through together |
| Redis caching strategy (key shape, TTL, invalidation triggers) | `opus-4-6` | High | Cache keyed on rounded lat/lng — decide rounding precision vs. cache hit rate trade-off here |
| Search endpoint implementation | `sonnet-4-6` | High | Wire PostGIS + subquery + Redis from Opus design; enforce all query params and defaults |
| Stadium detail endpoint | `sonnet-4-6` | Medium | Aggregates reviews, gallery URLs (CDN vs. signed), operating hours |
| Slots-for-date endpoint | `haiku-4-5` | Low | Simple filter on `Slot` by stadium + date |

> **Run Opus with extended thinking before writing any search SQL/ORM.** The PostGIS + Redis + subquery combination is the only part of this phase that requires architectural judgment. Implementation after the design is decided is Sonnet-level work.

---

## 3.1 Search Endpoint

```
GET /api/stadiums/search/
```

### Query Parameters

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `lat` | float | required | Player GPS or geocoded address |
| `lng` | float | required | Player GPS or geocoded address |
| `radius_km` | int | 10 | Max 50 |
| `date` | date | required | Format: YYYY-MM-DD |
| `time_from` | time | optional | Filter slots from this time |
| `time_to` | time | optional | Filter slots until this time |
| `sport_type` | enum | optional | `5v5` or `7v7` |
| `price_max` | int | optional | Max price per slot |
| `page` | int | 1 | 20 results per page |

### Implementation

- PostGIS: `ST_DWithin(location, ST_Point(lng, lat), radius_meters)` for radius filtering
- Annotate each result with:
  - `distance` — for sorting (nearest first)
  - `available_slot_count` — subquery on `Slot` table for the given date
- Exclude stadiums where `status != active`
- Redis cache: cache results 60 seconds, keyed by `(lat_rounded_3dp, lng_rounded_3dp, date, sport_type)`

### Response (per result card)

```json
{
  "id": "uuid",
  "name_ar": "...",
  "name_en": "...",
  "cover_photo_url": "...",
  "sport_type": "5v5",
  "price_per_slot": 150,
  "distance_km": 1.4,
  "avg_rating": 4.3,
  "available_slot_count": 5
}
```

---

## 3.2 Stadium Detail

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stadiums/<id>/` | GET | Full stadium detail |
| `/api/stadiums/<id>/slots/` | GET | Slots for a date (`?date=YYYY-MM-DD`) |
| `/api/stadiums/<id>/reviews/` | GET | Paginated reviews (20/page) |

### Detail Response Includes

- Full gallery (signed/CDN URLs per variant)
- Full description (`_ar` and `_en`)
- Amenities list
- Location (lat/lng for map pin)
- Operating hours
- Rating summary + sub-rating averages
- 5 most recent reviews
- Contact info: WhatsApp number, phone number

### Slots Response

All slot statuses returned for the requested date; client renders `available` ones as tappable.

```json
[
  {
    "id": "uuid",
    "start_time": "18:00",
    "end_time": "19:00",
    "status": "available",
    "price": 150
  }
]
```

---

## Deliverable

Search returns paginated, distance-sorted stadium results.
Stadium detail page shows gallery, slots, and reviews.
Map view supported via lat/lng in each search result.
