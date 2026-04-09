# Phase 3 — Search & Discovery

**Duration:** Week 5–6  
**Priority:** P0 (launch blocker)

**Goal:** Players can find stadiums by location, date, sport type, and time.

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
