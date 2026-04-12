# Phase 8 — Owner & Admin Dashboards

**Duration:** Week 11–13
**Priority:** P1

**Goal:** Functional web dashboards for stadium owners and platform admins, backed by the same REST API.

---

## AI Execution Guide

| Task | Model | Effort | Notes |
|------|-------|--------|-------|
| React WC integration architecture (Vite build, Django staticfiles, CSRF pattern) | `opus-4-6` | Extended thinking | The Django-template + React WC hybrid is the trickiest part — model the full request/auth/CSRF flow before touching code |
| React Web Components (`<owner-analytics>`, `<booking-calendar>`, `<standings-table>`, etc.) | `sonnet-4-6` | High | Each WC is a self-contained React app; fetch designs from Stitch (`mcp__stitch__get_screen`) before implementing |
| Server-rendered owner pages (stadium list, create/edit, operating hours, reviews, profile) | `sonnet-4-6` | Medium | Standard Django class-based views + forms; fetch Stitch specs for layout |
| Admin server-rendered pages (KYC queue, stadium approval, users, bookings list) | `sonnet-4-6` | Medium | Same pattern — but admin namespace is separate; IP whitelist middleware must be in place |
| `<gallery-lightbox>` and `<admin-analytics>` WCs | `sonnet-4-6` | High | Data-visualization WCs — fetch Stitch screens first |
| Repetitive list/detail server-rendered admin pages (bookings, tournaments, settings) | `haiku-4-5` | Low | Pattern is established after the first few — use Haiku to crank through the remaining pages |
| Session auth views (owner login, admin login, logout) | `sonnet-4-6` | Medium | Must use session cookies, not JWT; CSRF protection required |

> **Always fetch Stitch screen specs (`mcp__stitch__get_screen` with projectId `9141633750453935736` for owner, `11388881882164762104` for admin) before implementing any page.** Do not design UI from scratch. Run Opus once at the start to design the WC integration architecture, then switch to Sonnet for all implementation.



**Architecture:** Django server-rendered templates + React Web Components (via `@bitovi/react-to-web-component`).
No separate Node.js server — React components compiled to static JS bundles served by Django/WhiteNoise.

**Auth:** Session cookie + Django session auth (not JWT). CSRF token passed in `X-CSRFToken` header from all React WC `fetch()` calls.

**Important:** The Admin Dashboard is a fully custom Django web application — it does **not** extend Django Admin. Django's built-in `/admin/` is disabled in production.

---

## UI Design References

### Owner Dashboard Design (Stitch)
- **Project:** Hagz Kora Owner Dashboard — ID: `9141633750453935736`
- 57 screens (use only those mapping to the 12 owner pages below; rest are redundant variants)

### Admin Dashboard Design (Stitch)
- **Project:** Hagz Kora Admin Dashboard — ID: `11388881882164762104`
- 16 screens — one per admin page, exact 1:1 mapping to the spec below

**Design system (both dashboards):** "The Pitch Curator" — primary `#012d1d`, gold accent `#735c00`, surface `#f8f9fa`, RTL-first, no 1px borders, tonal layering, glassmorphism overlays. Fonts: Manrope (display/headlines), Inter (labels/body).

Use `mcp__stitch__list_screens` and `mcp__stitch__get_screen` with the relevant `projectId` to pull exact specs before implementing each page.

**Note (Owner Dashboard):** The Stitch project contains redundant variants. Only use screens that directly map to the 12 owner pages defined below.

---

## Owner Dashboard (`/owner/`) — 12 Pages

Requires Owner authentication. Owner must have `kyc_approved` status.

| # | Page | URL | Implementation |
|---|------|-----|---------------|
| 1 | Dashboard home / analytics | `/owner/` | React WC: `<owner-analytics>` — booking counts, occupancy rate |
| 2 | Stadium list | `/owner/stadiums/` | Server-rendered — list of owner's stadiums with status badges |
| 3 | Create stadium | `/owner/stadiums/new/` | Server-rendered — multi-step form |
| 4 | Edit stadium details | `/owner/stadiums/:id/edit/` | Server-rendered — pre-filled form |
| 5 | Gallery management | `/owner/stadiums/:id/gallery/` | React WC: `<stadium-gallery-editor>` — drag-and-drop reorder, cover photo, upload |
| 6 | Operating hours | `/owner/stadiums/:id/hours/` | Server-rendered — per-day time range form |
| 7 | Booking calendar | `/owner/stadiums/:id/bookings/` | React WC: `<booking-calendar data-stadium-id="">` — month view, slot blocking/unblocking |
| 8 | Tournament list | `/owner/tournaments/` | Server-rendered — list with status badges |
| 9 | Create tournament | `/owner/tournaments/new/` | Server-rendered — form |
| 10 | Tournament detail (fixtures + score entry) | `/owner/tournaments/:id/` | React WC: `<standings-table>` + server-rendered score entry forms per fixture |
| 11 | Reviews | `/owner/reviews/` | Server-rendered — reviews across all stadiums, inline owner response form |
| 12 | Profile & KYC status | `/owner/profile/` | Server-rendered — editable profile, read-only KYC status |

---

## Admin Dashboard (`/admin-panel/`) — 16 Pages

Fully custom Django views — no Django Admin extension. Restricted to IP whitelist in production.
Separate admin-only session auth (admin users have `role=admin` on the User model).

| # | Page | URL | Implementation | Notes |
|---|------|-----|---------------|-------|
| 1 | Login | `/admin-panel/login/` | Server-rendered | Admin-specific login form; separate from player/owner auth |
| 2 | Overview / Home | `/admin-panel/` | React WC: `<admin-overview>` | KPIs: total bookings, active stadiums, registered users, open queue counts |
| 3 | KYC Queue | `/admin-panel/kyc/` | Server-rendered | Paginated list of `pending_kyc` owner submissions |
| 4 | KYC Detail | `/admin-panel/kyc/:owner_id/` | Server-rendered | National ID document viewer, owner info, approve / reject with reason |
| 5 | Stadium Approvals Queue | `/admin-panel/stadiums/pending/` | Server-rendered | Paginated list of `pending_review` stadiums |
| 6 | Stadium Approval Detail | `/admin-panel/stadiums/:id/review/` | Server-rendered + React WC: `<gallery-lightbox>` | Gallery viewer, map pin, full stadium info, approve / reject |
| 7 | All Stadiums | `/admin-panel/stadiums/` | Server-rendered | Full list, filterable by status / city / sport type; suspend / reactivate actions |
| 8 | Stadium Detail (read) | `/admin-panel/stadiums/:id/` | Server-rendered | Stadium info, booking log, review list — read-only |
| 9 | Users | `/admin-panel/users/` | Server-rendered | All players + owners, filterable by role / status; suspend / reactivate |
| 10 | User Detail | `/admin-panel/users/:id/` | Server-rendered | Profile, booking history, account status, suspend / reactivate action |
| 11 | All Bookings | `/admin-panel/bookings/` | Server-rendered | Platform-wide booking log, filterable by date / stadium / status |
| 12 | All Tournaments | `/admin-panel/tournaments/` | Server-rendered | Platform-wide list, filterable by status |
| 13 | Tournament Detail (read) | `/admin-panel/tournaments/:id/` | Server-rendered + React WC: `<standings-table>` | Fixtures, standings, team list — read-only |
| 14 | Analytics | `/admin-panel/analytics/` | React WC: `<admin-analytics>` | Booking volume over time, user growth, active stadiums, top stadiums |
| 15 | Notification Broadcast | `/admin-panel/notifications/` | Server-rendered | Audience segmentation (all / players / owners / city), compose + send SMS/push |
| 16 | Settings | `/admin-panel/settings/` | Server-rendered | Platform config: maintenance mode, feature flags |

---

## Page Count Summary

| Dashboard | Pages |
|-----------|-------|
| Owner Dashboard | 12 |
| Admin Dashboard | 16 |
| **Total** | **28** |

---

## React Web Components Used

| WC Tag | Used On | Purpose |
|--------|---------|---------|
| `<owner-analytics>` | Owner home | Booking counts, occupancy rate charts |
| `<stadium-gallery-editor>` | Owner gallery page | Drag-and-drop photo reorder, cover flag, upload |
| `<booking-calendar data-stadium-id="">` | Owner booking calendar | Month view, slot status, block/unblock |
| `<standings-table data-tournament-id="">` | Owner tournament detail, Admin tournament detail | Live standings |
| `<admin-overview>` | Admin home | Platform KPI cards |
| `<gallery-lightbox>` | Admin stadium approval detail | Full-screen gallery review |
| `<admin-analytics>` | Admin analytics | Time-series charts, growth metrics |

---

## Key Technical Notes

- React WCs communicate with the REST API via `fetch()` using session cookies (no JWT needed in dashboards)
- All WC `fetch()` calls include `X-CSRFToken: <token>` header (token injected into page via Django template tag)
- Static JS bundles built with Vite and served via Django staticfiles (WhiteNoise in production)
- Each React WC is independently buildable — changes to one don't require rebuilding others
- Admin dashboard has its own URL namespace (`admin_panel`) — completely separate from owner views
- Django's built-in `/admin/` is **disabled** in production (`INSTALLED_APPS` excludes `django.contrib.admin` or `AdminSite` is overridden)

---

## Deliverable

Owner can: manage stadiums, upload/reorder gallery, set operating hours, view booking calendar, block slots, create and run tournaments, enter match scores, respond to reviews, and view their analytics — all via browser.

Admin can: log in via dedicated login page, process KYC and stadium approval queues, manage users (suspend/reactivate), view all platform bookings and tournaments, send broadcast notifications, view analytics, and configure platform settings.
