# TPS IB Management System — Multi-User

IB Department Operating Dashboard / Bond Portfolio & Revenue Management System
for Phòng Investment Banking – TPS. Multi-user, client–server, PostgreSQL as
the single source of truth (see `docs/original-prompt.docx` for the full
specification this repo implements, and `docs/reference-prototype.html` — an
earlier single-file prototype whose visual design and calculation formulas
this system reuses, but which is **not** part of the running application).

## Status: all 6 phases complete

The spec (`docs/original-prompt.docx` §37) explicitly asks for a phased
build rather than a cut-down one; all six shipped:

| Phase | Scope | Status |
|---|---|---|
| 1 | Repo scaffold, DB schema (all entities), auth + RBAC, audit-log infra, optimistic locking, shell UI + navigation | **Done** |
| 2 | Control tab (reference rates) + coupon engine + bond CRUD + monthly volume grid | **Done** |
| 3 | Fee engine (6 fee types, time-varying rate schedules) + revenue | **Done** |
| 4 | Dashboard aggregation + IR tab + Contracts register | **Done** |
| 5 | Weekly Portfolio + Compliance checklist + alerts | **Done** |
| 6 | Audit log viewer, backup/export/import, duplicate detection, perf, full test suite, Docker polish | **Done** (Docker build unverifiable in this sandbox — see "Full stack via Docker Compose" below) |

The **calculation engine** (coupon: fixed/floating/combined/conditional; fee
proration; dashboard aggregation) was built first, ahead of the rest of
Phase 2, because it is the highest-risk, most correctness-critical part of
the system and every later phase's API sits on top of it unchanged
(`backend/app/services/calc_engine.py`, `dashboard_engine.py`).

`backend/tests/` (59 tests, run against a real local PostgreSQL instance,
each inside a rolled-back transaction — see `tests/conftest.py`) reproduces
every acceptance test in spec §35 except one:

- **Pure unit tests against the engine** (no DB): 2–8, 10, 15, 16.
- **Integration tests against the real API**: 1, 3, 4, 5, 8, 9, 10, 12, 13,
  14, 15, 16, 17 — including multi-user conflict (409 on a stale `version`),
  rename-preserves-data, the Control→Bond coupon link, the audit trail
  recording an old/new coupon change, and duplicate-bond detection by
  normalized code.
- **Test 11** (persistence across logout/reload/another machine) is the one
  exception to "automated": a rolled-back-transaction test harness can't
  demonstrate cross-session durability by construction (that's the point of
  the rollback). It was instead verified manually, repeatedly, throughout
  development — every phase's screenshots came from data that had already
  survived backend restarts and fresh logins against the same local
  PostgreSQL instance.

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
8. **Fee-rate resolution rule for a mid-month rate change** (prompt §13.1
   explicitly asks for one of two rules to be chosen, not left
   unconfigured): the engine takes "ưu tiên rate tại ngày chốt kỳ" — the
   latest `BondFeeRatePeriod.effective_from` that has started by the
   recognition month's end wins (`fee_rate_at` in `calc_engine.py`). This
   applies uniformly to both Actual (which also prorates by day within that
   rate) and Flat methods. `BondFeeRatePeriod` overlap validation treats
   `effective_to = null` as open-ended and rejects any two periods on the
   same fee whose `[effective_from, effective_to]` windows intersect.
9. **`BondFeeConfig` got `created_at`/`updated_at`** added in a follow-up
   migration (`b480be34d7e3`) — missed in the initial schema pass, caught
   while wiring the fee API, consistent with §1.3's "mọi record quan trọng
   nên có created_at, updated_at". `IRJob` and `ContractProject` similarly
   got a `version` column added (`1b44798ef647`) once it was clear renaming
   either is a genuine multi-user race, same reasoning as assumption 6.
10. **Dashboard alerts (§18.6)** are now complete: bond-maturing-soon,
    benchmark-missing-current-month, portfolio-near/over-limit, compliance-
    incomplete (current month, across all bonds), and weekly-not-updated
    (fires once today has reached the Friday deadline and the current
    calendar week has no `WeeklyPortfolioValue` row for any bond).
11. **Weekly Portfolio grid is one bulk endpoint** (`GET /weekly?start=...&
    end=...`), not one HTTP call per week column — `weekly_service.
    get_week_range` computes every bond's coupon once per distinct month
    (cached per request) and every week's accrual in a single pass, so the
    frontend renders the whole multi-year week grid from one request instead
    of the N+1 pattern a naive per-week-column fetch would produce (relevant
    to §26's "tránh render/recalculate toàn app" performance guidance). The
    per-week endpoints (`GET /weekly/{week_key}`, `PUT .../bonds/{bond_id}`)
    still exist for single-cell writes and are what the grid's cell editor
    calls on blur.
12. **Coupon is shown as a small hint under each week's volume input**, not
    as a separate grid row — the coupon in the reference prototype's own
    weekly grid is one row shared across every bond, which doesn't hold once
    bonds have different coupons; showing it per-cell, right where the
    volume is entered, keeps "Hiển thị rõ Khối lượng và Coupon" (§21.4) true
    without a misleading shared row.
13. **Audit Log is Manager+ only** (`require_manager_up`), matching the
    permission table in §2 verbatim ("Manager: … xem audit"; Staff/Viewer
    aren't listed as having audit access). There is deliberately no
    delete/update endpoint for `audit_logs` at all, for any role including
    Admin — stricter than "Staff không được xóa audit log" requires, but a
    trail that literally cannot be edited via the API is a stronger
    guarantee than one that's merely hidden from Staff in the UI.
14. **Export is open to every role, including Viewer** (§2: "Viewer: Chỉ
    xem và export"), while backup/import/reset are Admin-only (§2's "Admin:
    … backup/restore; reset"). Backup shells out to `pg_dump` (present in
    the backend image via `postgresql-client`) against `DATABASE_URL`, so a
    restore is the standard `psql < backup_xxx.sql` — no custom restore
    endpoint was built, since correctness of a bespoke restore path is far
    riskier than documenting the standard Postgres one.
15. **JSON import is strictly additive, never overwrites**: every entity is
    matched by a natural key (bond code, benchmark name, IR job name,
    contract project name) and skipped — not merged, not replaced — if that
    key already exists, with the counts reported back. This is the
    conservative reading of "Import JSON phải validate schema và không được
    làm hỏng dữ liệu hiện có" (§5): a merge importer that decides which
    side wins on a conflict is exactly the kind of silent-data-loss risk
    that rule is guarding against.
16. **Reset (§5) truncates business tables and `audit_logs`**, then writes
    one fresh audit row recording the reset itself (actor + timestamp) —
    keeping the old audit history around after the records it describes are
    gone would be confusing, not more transparent; the one row documenting
    "a reset happened, by whom, when" is what's actually useful afterward.
    `users`/`roles` are never touched by reset.
17. **Duplicate detection (§27) covers bonds only**, grouped by normalized
    code (trim + collapse whitespace + uppercase) since `code` is the one
    business key in this schema that's user-typed free text at creation
    time and has no natural DB-level case/whitespace-insensitive
    constraint. It only detects and lists groups for review — no merge/
    delete action exists, per §27's "không tự xóa record trùng khi user
    chưa xác nhận". The other modules' natural keys (benchmark name, job
    name, project name) are already exact-matched by the create endpoints,
    so a whitespace/case variant would need to be typed differently on
    purpose — a materially smaller risk that didn't justify the same
    machinery within this project's time budget.

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

**Verification status**: `docker compose config` was run in this repo and
parses/interpolates cleanly. The actual `docker compose build`/`up` could
not be executed in *this development sandbox*, because its outbound network
policy blocks Docker Hub's CDN (`production.cloudfront.docker.com`, where
image layers are actually served from, as opposed to the registry API host
which does resolve) — `docker pull postgres:16-alpine` fails there with
`403 Forbidden` regardless of the Dockerfile. This is a property of the
sandbox, not of this repo. Everything each Dockerfile actually runs —
`pip install -r requirements.txt`, `alembic upgrade head`, `uvicorn app.main
:app`, `npm install && npm run build`, serving `dist/` from Nginx — was
run directly, repeatedly, and successfully throughout this project's local
development (every phase's screenshots and test runs used exactly this
backend/frontend, just outside a container). If `docker compose up --build`
doesn't work in your environment, it's worth checking Docker Hub
reachability first (`docker pull postgres:16-alpine`) before assuming a
problem with the compose file or Dockerfiles here.

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
