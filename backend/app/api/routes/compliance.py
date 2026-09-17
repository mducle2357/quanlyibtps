from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_staff_up
from app.core.errors import NotFoundError, ValidationAppError
from app.models.bond import Bond
from app.models.compliance import ComplianceChecklistEntry, ComplianceItem
from app.models.user import User
from app.schemas.compliance import ComplianceEntryCreate, ComplianceEntryOut, ComplianceEntryUpdate, ComplianceItemGroup
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version
from app.services.dates import is_valid_month_key

router = APIRouter(prefix="/bonds/{bond_id}/compliance", tags=["compliance"])
StaffUp = Annotated[User, Depends(require_staff_up)]
MODULE = "compliance_checklist_entries"


def _entry_out(e: ComplianceChecklistEntry) -> ComplianceEntryOut:
    return ComplianceEntryOut(
        id=e.id, month_key=e.month_key, text=e.text, done=e.done, note=e.note,
        deadline=e.deadline, assignee_id=e.assignee_id, version=e.version,
    )


@router.get("", response_model=list[ComplianceItemGroup])
def list_compliance(bond_id: str, db: DbSession, _user: CurrentUser, month: str):
    if not is_valid_month_key(month):
        raise ValidationAppError("month phải theo dạng YYYY-MM.")
    if not db.get(Bond, bond_id):
        raise NotFoundError("Không tìm thấy trái phiếu.")
    items = db.query(ComplianceItem).order_by(ComplianceItem.sort_order).all()
    out = []
    for item in items:
        entries = (
            db.query(ComplianceChecklistEntry)
            .filter(
                ComplianceChecklistEntry.bond_id == bond_id,
                ComplianceChecklistEntry.compliance_item_id == item.id,
                ComplianceChecklistEntry.month_key == month,
            )
            .all()
        )
        done = sum(1 for e in entries if e.done)
        out.append(
            ComplianceItemGroup(
                item_id=item.id, group_key=item.group_key, item_key=item.item_key, name=item.name,
                entries=[_entry_out(e) for e in entries], done_count=done, total_count=len(entries),
            )
        )
    return out


@router.post("/{item_key}/entries", response_model=ComplianceEntryOut, status_code=201)
def add_entry(bond_id: str, item_key: str, payload: ComplianceEntryCreate, db: DbSession, user: StaffUp):
    if not is_valid_month_key(payload.month_key):
        raise ValidationAppError("month_key phải theo dạng YYYY-MM.")
    if not db.get(Bond, bond_id):
        raise NotFoundError("Không tìm thấy trái phiếu.")
    item = db.query(ComplianceItem).filter(ComplianceItem.item_key == item_key).first()
    if not item:
        raise NotFoundError("Không tìm thấy đầu mục compliance.")
    entry = ComplianceChecklistEntry(
        bond_id=bond_id, compliance_item_id=item.id, month_key=payload.month_key, text=payload.text,
        note=payload.note, deadline=payload.deadline, assignee_id=payload.assignee_id,
        created_by=user.id, updated_by=user.id,
    )
    db.add(entry)
    db.flush()
    record_create(db, user_id=user.id, module=MODULE, record_id=entry.id, snapshot={"item_key": item_key, "month_key": payload.month_key})
    db.commit()
    db.refresh(entry)
    return _entry_out(entry)


@router.patch("/entries/{entry_id}", response_model=ComplianceEntryOut)
def update_entry(bond_id: str, entry_id: str, payload: ComplianceEntryUpdate, db: DbSession, user: StaffUp):
    entry = db.query(ComplianceChecklistEntry).filter(ComplianceChecklistEntry.id == entry_id, ComplianceChecklistEntry.bond_id == bond_id).first()
    if not entry:
        raise NotFoundError("Không tìm thấy mục compliance.")
    check_version(entry.version, payload.version)
    before = {"text": entry.text, "done": entry.done, "note": entry.note, "deadline": entry.deadline, "assignee_id": entry.assignee_id}
    entry.text = payload.text
    entry.done = payload.done
    entry.note = payload.note
    entry.deadline = payload.deadline
    entry.assignee_id = payload.assignee_id
    entry.updated_by = user.id
    after = {"text": entry.text, "done": entry.done, "note": entry.note, "deadline": entry.deadline, "assignee_id": entry.assignee_id}
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=entry.id, before=before, after=after)
    db.commit()
    db.refresh(entry)
    return _entry_out(entry)


@router.delete("/entries/{entry_id}")
def delete_entry(bond_id: str, entry_id: str, db: DbSession, user: StaffUp):
    entry = db.query(ComplianceChecklistEntry).filter(ComplianceChecklistEntry.id == entry_id, ComplianceChecklistEntry.bond_id == bond_id).first()
    if not entry:
        raise NotFoundError("Không tìm thấy mục compliance.")
    record_delete(db, user_id=user.id, module=MODULE, record_id=entry.id, snapshot={"text": entry.text})
    db.delete(entry)
    db.commit()
    return {"ok": True}
