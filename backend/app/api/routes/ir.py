from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_manager_up, require_staff_up
from app.core.errors import NotFoundError, ValidationAppError
from app.models.ir import IRJob, IRMonthlyRevenue
from app.models.user import User
from app.schemas.ir import IRJobCreate, IRJobOut, IRJobRename, IRMonthlyValueSet
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version
from app.services.dates import is_valid_month_key

router = APIRouter(prefix="/ir-jobs", tags=["ir"])
StaffUp = Annotated[User, Depends(require_staff_up)]
ManagerUp = Annotated[User, Depends(require_manager_up)]
MODULE = "ir_jobs"


def _out(job: IRJob) -> IRJobOut:
    return IRJobOut(
        id=job.id, name=job.name, sort_order=job.sort_order, version=job.version,
        monthly_values={mv.month_key: {"revenue": float(mv.revenue), "version": mv.version} for mv in job.monthly_revenue},
    )


@router.get("", response_model=list[IRJobOut])
def list_jobs(db: DbSession, _user: CurrentUser):
    jobs = db.query(IRJob).order_by(IRJob.sort_order, IRJob.name).all()
    return [_out(j) for j in jobs]


@router.post("", response_model=IRJobOut, status_code=201)
def create_job(payload: IRJobCreate, db: DbSession, user: StaffUp):
    max_order = db.query(IRJob).count()
    job = IRJob(name=payload.name.strip(), sort_order=max_order, created_by=user.id, updated_by=user.id)
    db.add(job)
    db.flush()
    record_create(db, user_id=user.id, module=MODULE, record_id=job.id, snapshot={"name": job.name})
    db.commit()
    db.refresh(job)
    return _out(job)


@router.patch("/{job_id}", response_model=IRJobOut)
def rename_job(job_id: str, payload: IRJobRename, db: DbSession, user: StaffUp):
    job = db.get(IRJob, job_id)
    if not job:
        raise NotFoundError("Không tìm thấy công việc IR.")
    check_version(job.version, payload.version)
    before = {"name": job.name}
    job.name = payload.name.strip()
    job.updated_by = user.id
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=job.id, before=before, after={"name": job.name})
    db.commit()
    db.refresh(job)
    return _out(job)


@router.delete("/{job_id}")
def delete_job(job_id: str, db: DbSession, user: ManagerUp):
    job = db.get(IRJob, job_id)
    if not job:
        raise NotFoundError("Không tìm thấy công việc IR.")
    record_delete(db, user_id=user.id, module=MODULE, record_id=job.id, snapshot={"name": job.name})
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.put("/{job_id}/monthly/{month_key}", response_model=IRJobOut)
def set_monthly_revenue(job_id: str, month_key: str, payload: IRMonthlyValueSet, db: DbSession, user: StaffUp):
    job = db.get(IRJob, job_id)
    if not job:
        raise NotFoundError("Không tìm thấy công việc IR.")
    if not is_valid_month_key(month_key):
        raise ValidationAppError("month_key phải theo dạng YYYY-MM.")
    existing = (
        db.query(IRMonthlyRevenue)
        .filter(IRMonthlyRevenue.ir_job_id == job_id, IRMonthlyRevenue.month_key == month_key)
        .first()
    )
    if existing:
        check_version(existing.version, payload.version if payload.version is not None else -1)
        existing.revenue = payload.revenue
        existing.updated_by = user.id
    else:
        if payload.version is not None:
            raise ValidationAppError("Ô này chưa có dữ liệu; không thể gửi version.")
        db.add(IRMonthlyRevenue(ir_job_id=job_id, month_key=month_key, revenue=payload.revenue, updated_by=user.id))
    db.commit()
    db.refresh(job)
    return _out(job)
