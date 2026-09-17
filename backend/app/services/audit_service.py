"""Every write to a business record must be traceable: who, when, which field,
old value, new value (prompt §4). Routers call `record_field_changes` after
diffing the old and new state of an entity, inside the same DB transaction as
the write itself, so an audit row can never exist without the change it
describes (or vice versa).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import ACTION_CREATE, ACTION_DELETE, ACTION_UPDATE, AuditLog


def _stringify(v: Any) -> str | None:
    if v is None:
        return None
    return str(v)


def record_field_changes(
    db: Session,
    *,
    user_id: str | None,
    module: str,
    record_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    for field in after:
        old = before.get(field)
        new = after.get(field)
        if old == new:
            continue
        db.add(
            AuditLog(
                user_id=user_id,
                module=module,
                record_id=str(record_id),
                field=field,
                old_value=_stringify(old),
                new_value=_stringify(new),
                action=ACTION_UPDATE,
            )
        )


def record_create(db: Session, *, user_id: str | None, module: str, record_id: str, snapshot: dict[str, Any]) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            module=module,
            record_id=str(record_id),
            field=None,
            old_value=None,
            new_value=_stringify(snapshot),
            action=ACTION_CREATE,
        )
    )


def record_delete(db: Session, *, user_id: str | None, module: str, record_id: str, snapshot: dict[str, Any]) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            module=module,
            record_id=str(record_id),
            field=None,
            old_value=_stringify(snapshot),
            new_value=None,
            action=ACTION_DELETE,
        )
    )
