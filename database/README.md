# database/

Reserved by the repo layout in `docs/original-prompt.docx` §32. This project
keeps the actual schema/migrations next to the code that owns them instead of
duplicating that logic here:

- **Migrations**: `backend/alembic/versions/` (run via `alembic upgrade head`
  — see the root README's "Local development" section).
- **Seed data**: `backend/alembic/versions/7ace0c07f7eb_seed_roles_and_compliance_items.py`
  seeds roles and the 9 compliance checklist items. `backend/scripts/create_admin.py`
  seeds the first Admin user (a password can't live in a migration).

If a standalone SQL asset (e.g. a one-off analytics query, a manual data fix
script) is ever needed outside Alembic's migration history, it belongs here.
