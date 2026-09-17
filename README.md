# TPS IB Management System — Multi-User

IB Department Operating Dashboard / Bond Portfolio & Revenue Management System
for Phòng Investment Banking – TPS. Multi-user, client–server, PostgreSQL as
the single source of truth (see `docs/original-prompt.docx` for the full
specification this repo implements, and `docs/reference-prototype.html` — an
earlier single-file prototype whose visual design and calculation formulas
this system reuses, but which is **not** part of the running application).

## Status: phased build in progress

The spec (`docs/original-prompt.docx` §37) explicitly asks for a phased
build rather than a cut-down one. Current state:

| Phase | Scope | Status |
|---|---|---|
| 1 | Repo scaffold, DB schema (all entities), auth + RBAC, audit-log infra, optimistic locking, shell UI + navigation | **Done** |
| 2 | Control tab (reference rates) + coupon engine + bond CRUD + monthly volume grid | **Done** |
| 3 | Fee engine (6 fee types, time-varying rate schedules) + revenue | Not started |
| 4 | Dashboard aggregation + IR tab + Contracts register | Not started |
| 5 | Weekly Portfolio + Compliance checklist + alerts | Not started |
| 6 | Audit log viewer, backup/export/import, duplicate detection, perf, full test suite, Docker polish | Not started |

The **calculation engine itself** (coupon: fixed/floating/combined/conditional;
fee proration; dashboard aggregation) was built first, ahead of the rest of
Phase 2, because it is the highest-risk, most correctness-critical part of the
system and every later phase's API sits on top of it unchanged
(`backend/app/services/calc_engine.py`, `dashboard_engine.py`).
`backend/tests/` reproduces acceptance tests 1–10, 12, 13, 15, 16 from the
spec (§35): tests 2–8, 10, 15, 16 as pure unit tests against the engine
directly (no DB), and 1, 3, 4, 5, 9, 12, 13 as integration tests against the
real Reference Rates + Bonds API (`test_reference_rates_api.py`,
`test_bonds_api.py`), each round-tripped through a real local PostgreSQL
instance inside a rolled-back transaction (`tests/conftest.py`). Tests 11
(persistence across logout/reload) and 14 (audit log) were exercised manually
via the browser in this phase and get automated coverage in Phase 6 alongside
the audit log viewer.

## Architecture

```
Frontend (React + TS, Vite)  →  Backend API (FastAPI)  →  PostgreSQL
```

- **Frontend**: React 19 + TypeScript, React Router, TanStack Query for
  server-state caching (satisfies §26 "tránh render/recalculate toàn app"),
  Recharts for charts (Phase 4+). No business data is ever written to
  `localStorage` — only the refresh token (see "Auth" below) and, later,
  per-viewer UI prefs (nav-collapsed, column widths) as explicitly allowed by
  prompt §1.4.
- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic migrations + PostgreSQL
  (via `psycopg` v3). Argon2 password hashing, JWT access/refresh tokens.
  Every mutable business table has `created_at/updated_at/created_by/updated_by`
  and a `version` column used for optimistic locking (SQLAlchemy
  `version_id_col`, backed by an explicit pre-check for a friendly 409).
- **Database**: PostgreSQL 16, one migration history in `backend/alembic/`.

## Auth & roles

Four roles seeded by migration: `Admin`, `Manager`, `Staff`, `Viewer` (prompt
§2). Login issues a short-lived JWT access token (kept in memory on the
frontend, never localStorage) plus a longer-lived opaque refresh token
(stored in `localStorage` under `ib_tps_refresh_token`, revocable server-side
via the `refresh_tokens` table — logout revokes it immediately). This is
a deliberate assumption/compromise, since the spec doesn't mandate a cookie
session and CSRF protection is only required "if using cookie sessions"
(§31); documented here rather than silently decided.

`sso_subject` on `users` is unused today but present so Entra ID/M365 SSO
(prompt §2) can be added later without a schema change — a federated user
would have `sso_subject` set and `password_hash` become irrelevant at login.

## Concurrency (prompt §3)

Every editable entity carries `version`. Update endpoints (from Phase 2
onward) require the client's last-seen `version` in the request body; a
mismatch returns **409** with the exact message the spec requires:
"Dữ liệu đã được thay đổi bởi người dùng khác. Vui lòng tải lại hoặc xem thay
đổi trước khi ghi đè." The same 409 is also produced by SQLAlchemy's
`version_id_col` if two requests race past the initial check (defense in
depth — see `app/services/concurrency.py` and the `StaleDataError` handler in
`app/main.py`).

## Assumptions (prompt §0: "ghi chú giả định trong README thay vì tự sửa logic nghiệp vụ")

1. **6 fee types are a fixed Python constant, not a DB table.** They are not
   user-creatable/deletable per the spec, so a lookup table would be pure
   ceremony. `FEE_DEFS` in `calc_engine.py` and `models/bond.py` are the
   single source of truth.
2. **`BondFeeRatePeriod.calculation_method`** is stored (schema fidelity with
   §29's suggested `bond_fee_rate_periods.calculation_method`) but not yet
   consulted by the engine — §13.2 ties calculation method (Actual vs. Flat)
   to the *fee type as configured on the bond*, not to a time slice, so the
   engine applies `BondFeeConfig.method` uniformly. The column is there if a
   future requirement needs per-period method overrides.
3. **Refresh tokens in `localStorage`** — see "Auth" above.
4. **`bond_holding_period_overrides`** (suggested as a separate table in §29)
   is folded into `bond_monthly_data.hold_start_override` /
   `hold_end_override` instead of a separate table, mirroring the reference
   prototype's `months[k].startDate/endDate` — same information, fewer joins.
5. **Weekly key format** is `YYYY-MM-Wn` (string), validated in the service
   layer rather than a `weekly_periods` lookup table, since a week is fully
   determined by its month + index (max 5/month) and never referenced from
   outside the Weekly Portfolio module.
6. **Every editable grid cell carries a `version`**, not just structural
   records — `reference_rate_monthly_values` and `ir_monthly_revenue` got a
   `version` column added in a follow-up migration (`0efeba53be5f`) once it
   became clear the spec's "cùng sửa một bảng" concurrency requirement (§3)
   reads naturally as applying to every editable cell, not only whole rows.
   `bond_monthly_data` versions the whole row (4 volume fields together)
   since those 4 fields are edited and displayed as one unit.
7. **`GET /reference-rates/resolved`** returns every benchmark's per-month
   value with calculated (average/min/max) rates already resolved
   server-side. This exists so the frontend chart/grid never re-implements
   the resolution/circular-dependency logic in TypeScript — a second
   implementation of that logic is exactly the kind of duplication that goes
   stale and quietly diverges from the engine used for real calculations.

## Local development

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 16 (or use Docker Compose
for Postgres only).

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then edit DATABASE_URL / JWT_SECRET_KEY if needed
alembic upgrade head
python scripts/create_admin.py admin@tps.vn "Quan Tri Vien" 'YourStrongPass123!'
uvicorn app.main:app --reload --port 8000
```

Run tests: `pytest` (from `backend/`, with the venv active).

### Frontend

```bash
cd frontend
npm install
npm run dev  # proxies /api to http://localhost:8000 by default (VITE_BACKEND_URL to override)
```

Open http://localhost:5173 and log in with the admin account created above.

### Full stack via Docker Compose

```bash
cp .env.example .env   # edit passwords/secrets
docker compose up --build
# then, once, bootstrap the first Admin:
docker compose exec backend python scripts/create_admin.py admin@tps.vn "Quan Tri Vien" 'YourStrongPass123!'
```

Frontend: http://localhost:8080 · Backend: http://localhost:8000 · Postgres:
localhost:5432. Postgres data persists in the `pgdata` named volume across
container restarts (prompt §33).

### Production notes

Put Nginx/Caddy in front of the `frontend` and `backend` services for TLS
termination (prompt §33); the `frontend` container's own Nginx already
proxies `/api/*` to `backend:8000` inside the compose network, so a single
public hostname is enough. Set a strong, unique `JWT_SECRET_KEY` and
`POSTGRES_PASSWORD` in `.env` — never the defaults in `.env.example`.

## Repository layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, calc engine, tests
frontend/   React + TypeScript SPA (Vite)
database/   (reserved for standalone SQL/seed assets if needed later)
docs/       original prompt, reference prototype, this README's companions
docker/     (reserved for shared compose fragments / reverse-proxy config)
```
