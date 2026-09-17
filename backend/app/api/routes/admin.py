import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook

from app.api.deps import CurrentUser, DbSession, require_admin, require_manager_up
from app.core.errors import ValidationAppError
from app.core.security import verify_password
from app.models.audit import BackupMetadata
from app.models.bond import Bond
from app.models.user import User
from app.schemas.admin import BackupOut, DuplicateGroup, ImportReport, ResetRequest
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_admin)]
ManagerUp = Annotated[User, Depends(require_manager_up)]


@router.post("/backup", response_model=BackupOut)
def trigger_backup(db: DbSession, user: Admin):
    try:
        meta = admin_service.run_backup(db, user.id)
    except RuntimeError as e:
        raise ValidationAppError(str(e))
    db.commit()
    return BackupOut(id=meta.id, filename=meta.filename, created_at=meta.created_at, size_bytes=meta.size_bytes, status=meta.status)


@router.get("/backups", response_model=list[BackupOut])
def list_backups(db: DbSession, _user: Admin):
    rows = db.query(BackupMetadata).order_by(BackupMetadata.created_at.desc()).all()
    return [BackupOut(id=r.id, filename=r.filename, created_at=r.created_at, size_bytes=r.size_bytes, status=r.status) for r in rows]


@router.get("/export/json")
def export_json(db: DbSession, _user: CurrentUser):
    data = admin_service.export_full_json(db)
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(body.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="tps_ib_export.json"'},
    )


@router.get("/export/csv/bonds")
def export_bonds_csv(db: DbSession, _user: CurrentUser):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Mã trái phiếu", "Ngày phát hành", "Ngày đáo hạn", "Mệnh giá (tr.đ)", "XHTN"])
    for b in db.query(Bond).filter(Bond.is_deleted.is_(False)).order_by(Bond.code).all():
        w.writerow([b.code, b.issue_date or "", b.maturity_date or "", float(b.par_value), b.xhtn or ""])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bonds.csv"'},
    )


@router.get("/export/xlsx/bonds")
def export_bonds_xlsx(db: DbSession, _user: CurrentUser):
    wb = Workbook()
    ws = wb.active
    ws.title = "Bonds"
    ws.append(["Mã trái phiếu", "Ngày phát hành", "Ngày đáo hạn", "Mệnh giá (tr.đ)", "XHTN"])
    for b in db.query(Bond).filter(Bond.is_deleted.is_(False)).order_by(Bond.code).all():
        ws.append([b.code, str(b.issue_date or ""), str(b.maturity_date or ""), float(b.par_value), b.xhtn or ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="bonds.xlsx"'},
    )


@router.post("/import/json", response_model=ImportReport)
async def import_json(file: UploadFile, db: DbSession, user: Admin):
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValidationAppError("File không phải JSON hợp lệ.")
    try:
        report = admin_service.import_full_json(db, data, user.id)
    except ValueError as e:
        raise ValidationAppError(str(e))
    db.commit()
    return ImportReport(**report)


@router.post("/reset")
def reset_data(payload: ResetRequest, db: DbSession, user: Admin):
    if not verify_password(payload.password, user.password_hash):
        raise ValidationAppError("Mật khẩu không đúng.")
    if payload.confirm_word != "RESET":
        raise ValidationAppError("Vui lòng gõ đúng từ xác nhận RESET.")
    admin_service.reset_all_business_data(db, user.id)
    db.commit()
    return JSONResponse({"ok": True, "message": "Đã xóa toàn bộ dữ liệu nghiệp vụ. Thao tác này ảnh hưởng tới tất cả người dùng."})


@router.get("/duplicates/bonds", response_model=list[DuplicateGroup])
def duplicate_bonds(db: DbSession, _user: ManagerUp):
    return [DuplicateGroup(**g) for g in admin_service.find_duplicate_bonds(db)]
