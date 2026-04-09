# Phase 6 — Tournament Engine

**Duration:** Week 8–11  
**Priority:** P1 (Phase 1, post-MVP launch)

**Goal:** Full tournament lifecycle — creation, team registration, fixture generation (3 formats), score entry, live standings, public page.

---

## Data Models

```
Tournament
  id, stadium FK, organizer FK (owner), name, format (round_robin|knockout|group_knockout),
  max_teams, registration_deadline, start_date,
  status (draft|registration_open|registration_closed|in_progress|completed|cancelled),
  prize_info, rules, public_slug (unique, URL-safe)

TournamentTeam
  id, tournament FK, name, captain FK (player), join_code (unique 6-char), registered_at

TournamentPlayer
  id, team FK, player FK, joined_at

Fixture
  id, tournament FK, home_team FK, away_team FK, round_number,
  scheduled_at, home_score, away_score,
  status (scheduled|completed|cancelled),
  stage (group|knockout), group_name
```

> **Standing is NOT stored.** It is computed dynamically from Fixture results to avoid sync bugs.

---

## 6.1 Tournament CRUD (Owner)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/owner/tournaments/` | GET, POST | List / create tournaments |
| `/api/owner/tournaments/<id>/` | GET, PATCH, DELETE | Manage tournament (draft only) |
| `/api/owner/tournaments/<id>/publish/` | POST | Open registration (draft → registration_open) |
| `/api/owner/tournaments/<id>/close-registration/` | POST | Lock registrations → generate all fixtures |
| `/api/owner/tournaments/<id>/fixtures/<f_id>/score/` | PATCH | Enter match score |
| `/api/owner/tournaments/<id>/complete/` | POST | Mark tournament as completed |

---

## 6.2 Team Registration (Player)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tournaments/<id>/register/` | POST | Register new team; registering player becomes captain |
| `/api/tournaments/join/` | POST | Join existing team via `join_code` |
| `/api/tournaments/<id>/my-team/` | GET | View own team and teammates |

**Rules:**
- Min players: 5 for 5v5, 7 for 7v7
- Registration auto-closes at deadline or when `max_teams` reached
- Owner can manually close/reopen registration before deadline

---

## 6.3 Fixture Generation Service

`services/tournament/fixture_generator.py`

### Round Robin

- N*(N-1)/2 unique fixtures for N teams
- Uses the standard **circle method** algorithm
- Fixtures distributed across available days between start date and auto-calculated end date

### Knockout

- Single-elimination bracket
- Teams seeded randomly at creation
- Byes added if N is not a power of 2
- Next round fixtures **auto-generated** when all prior round matches are completed

### Group then Knockout

1. Teams divided into 2–4 equal groups
2. Round-robin run within each group
3. Top 2 from each group advance
4. Knockout fixtures auto-generated after group stage completes

---

## 6.4 Score Entry & Results

```
PATCH /api/owner/tournaments/<id>/fixtures/<fixture_id>/score/
Body: { "home_score": 3, "away_score": 1 }
```

On score entry:
- Fixture `status` → `completed`
- For round-robin/group: standings recomputed on next GET (no stored state)
- For knockout: if all matches in current round complete → auto-generate next round fixtures

---

## 6.5 Standings Computation

```
GET /api/tournaments/<id>/standings/
```

Computed dynamically from all completed `Fixture` records.

**Columns:** Team · Played · Won · Drawn · Lost · Goals For · Goals Against · Goal Difference · Points

**Tiebreaker order:** Points → Goal Difference → Goals For → Head-to-head result

---

## 6.6 Public Tournament Page (No Auth Required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tournaments/<id>/` | GET | Tournament info, status, team list |
| `/api/tournaments/<id>/fixtures/` | GET | Full fixture schedule |
| `/api/tournaments/<id>/standings/` | GET | Live standings |

Each tournament also has a shareable public web URL at `/tournaments/<public_slug>/`.

---

## Deliverable

All 3 fixture formats generate correct, complete schedules.  
Standings compute correctly including all tiebreakers.  
Public page accessible without authentication.  
Next-round knockout fixtures auto-generate on round completion.
