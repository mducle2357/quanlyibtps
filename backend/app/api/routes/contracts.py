from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_manager_up, require_staff_up
from app.core.errors import NotFoundError
from app.models.contracts import Contract, ContractProject
from app.models.user import User
from app.schemas.contracts import ContractCreate, ContractOut, ContractUpdate, ProjectCreate, ProjectOut, ProjectRename
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version

router = APIRouter(prefix="/contracts", tags=["contracts"])
StaffUp = Annotated[User, Depends(require_staff_up)]
ManagerUp = Annotated[User, Depends(require_manager_up)]
MODULE = "contracts"


def _contract_out(c: Contract) -> ContractOut:
    return ContractOut(
        id=c.id, contract_date=c.contract_date, title=c.title, contract_number=c.contract_number,
        status=c.status, parties=c.parties, sort_order=c.sort_order, version=c.version,
    )


def _project_out(p: ContractProject, roman_index: int) -> ProjectOut:
    contracts = sorted(p.contracts, key=lambda c: c.sort_order)
    return ProjectOut(
        id=p.id, roman_index=roman_index, name=p.name, sort_order=p.sort_order, version=p.version,
        contracts=[_contract_out(c) for c in contracts],
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: DbSession, _user: CurrentUser):
    projects = db.query(ContractProject).order_by(ContractProject.sort_order, ContractProject.created_at).all()
    return [_project_out(p, i + 1) for i, p in enumerate(projects)]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: DbSession, user: StaffUp):
    max_order = db.query(ContractProject).count()
    project = ContractProject(name=payload.name.strip(), sort_order=max_order, created_by=user.id, updated_by=user.id)
    db.add(project)
    db.flush()
    record_create(db, user_id=user.id, module=MODULE, record_id=project.id, snapshot={"name": project.name})
    db.commit()
    db.refresh(project)
    return _project_out(project, max_order + 1)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def rename_project(project_id: str, payload: ProjectRename, db: DbSession, user: StaffUp):
    project = db.get(ContractProject, project_id)
    if not project:
        raise NotFoundError("Không tìm thấy dự án.")
    check_version(project.version, payload.version)
    before = {"name": project.name}
    project.name = payload.name.strip()
    project.updated_by = user.id
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=project.id, before=before, after={"name": project.name})
    db.commit()
    db.refresh(project)
    all_projects = db.query(ContractProject).order_by(ContractProject.sort_order, ContractProject.created_at).all()
    idx = next(i for i, p in enumerate(all_projects) if p.id == project.id)
    return _project_out(project, idx + 1)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: DbSession, user: ManagerUp):
    project = db.get(ContractProject, project_id)
    if not project:
        raise NotFoundError("Không tìm thấy dự án.")
    record_delete(db, user_id=user.id, module=MODULE, record_id=project.id, snapshot={"name": project.name})
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/projects/{project_id}/contracts", response_model=ContractOut, status_code=201)
def add_contract(project_id: str, payload: ContractCreate, db: DbSession, user: StaffUp):
    project = db.get(ContractProject, project_id)
    if not project:
        raise NotFoundError("Không tìm thấy dự án.")
    max_order = db.query(Contract).filter(Contract.project_id == project_id).count()
    contract = Contract(
        project_id=project_id, contract_date=payload.contract_date, title=payload.title,
        contract_number=payload.contract_number, status=payload.status, parties=payload.parties,
        sort_order=max_order, created_by=user.id, updated_by=user.id,
    )
    db.add(contract)
    db.flush()
    record_create(db, user_id=user.id, module="contract_entries", record_id=contract.id, snapshot={"title": contract.title})
    db.commit()
    db.refresh(contract)
    return _contract_out(contract)


@router.patch("/projects/{project_id}/contracts/{contract_id}", response_model=ContractOut)
def update_contract(project_id: str, contract_id: str, payload: ContractUpdate, db: DbSession, user: StaffUp):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.project_id == project_id).first()
    if not contract:
        raise NotFoundError("Không tìm thấy hợp đồng.")
    check_version(contract.version, payload.version)
    before = {
        "contract_date": contract.contract_date, "title": contract.title, "contract_number": contract.contract_number,
        "status": contract.status, "parties": contract.parties,
    }
    contract.contract_date = payload.contract_date
    contract.title = payload.title
    contract.contract_number = payload.contract_number
    contract.status = payload.status
    contract.parties = payload.parties
    contract.updated_by = user.id
    after = {
        "contract_date": contract.contract_date, "title": contract.title, "contract_number": contract.contract_number,
        "status": contract.status, "parties": contract.parties,
    }
    record_field_changes(db, user_id=user.id, module="contract_entries", record_id=contract.id, before=before, after=after)
    db.commit()
    db.refresh(contract)
    return _contract_out(contract)


@router.delete("/projects/{project_id}/contracts/{contract_id}")
def delete_contract(project_id: str, contract_id: str, db: DbSession, user: ManagerUp):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.project_id == project_id).first()
    if not contract:
        raise NotFoundError("Không tìm thấy hợp đồng.")
    record_delete(db, user_id=user.id, module="contract_entries", record_id=contract.id, snapshot={"title": contract.title})
    db.delete(contract)
    db.commit()
    return {"ok": True}
