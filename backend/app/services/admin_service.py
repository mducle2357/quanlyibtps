"""Backup, full JSON export/import, reset, and duplicate detection (prompt §5, §27).

The JSON export/import format uses natural keys (bond code, benchmark name,
job name, project name) instead of internal UUIDs so a dump is portable
across environments — re-importing into a fresh database reconstructs the
same references by name/code rather than expecting identical primary keys.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit import AuditLog, BackupMetadata
from app.models.bond import Bond, BondFeeConfig, BondFeeRatePeriod, BondInterestConfig, BondMonthlyData, FEE_DEFS
from app.models.compliance import ComplianceChecklistEntry, ComplianceItem
from app.models.contracts import Contract, ContractProject
from app.models.ir import IRJob, IRMonthlyRevenue
from app.models.reference_rate import ReferenceRate, ReferenceRateComponent, ReferenceRateMonthlyValue
from app.models.weekly import EquityMonthlyValue, WeeklyPortfolioValue
from app.services.audit_service import record_create

settings = get_settings()


# --------------------------------------------------------------------------- #
# Backup (prompt §5: "Database backup là cơ chế backup chính")
# --------------------------------------------------------------------------- #


def run_backup(db: Session, user_id: str | None) -> BackupMetadata:
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"backup_{ts}.sql"
    path = backup_dir / filename

    parsed = urlparse(settings.database_url.replace("postgresql+psycopg://", "postgresql://"))
    env_url = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}{parsed.path}"

    result = subprocess.run(["pg_dump", env_url, "-f", str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr[:2000]}")

    size = path.stat().st_size
    meta = BackupMetadata(filename=filename, created_by=user_id, size_bytes=size, status="completed")
    db.add(meta)
    db.flush()
    return meta


# --------------------------------------------------------------------------- #
# Full JSON export (prompt §5)
# --------------------------------------------------------------------------- #


def export_full_json(db: Session) -> dict:
    rates = db.query(ReferenceRate).all()
    rate_name_by_id = {r.id: r.name for r in rates}

    reference_rates = []
    for r in rates:
        reference_rates.append(
            {
                "name": r.name,
                "rate_type": r.rate_type,
                "calc_method": r.calc_method,
                "component_names": [rate_name_by_id.get(c.component_rate_id) for c in r.components],
                "monthly_values": {mv.month_key: float(mv.rate) for mv in r.monthly_values},
            }
        )

    bonds_out = []
    for b in db.query(Bond).filter(Bond.is_deleted.is_(False)).all():
        ic = b.interest_config
        bonds_out.append(
            {
                "code": b.code,
                "issue_date": b.issue_date.isoformat() if b.issue_date else None,
                "maturity_date": b.maturity_date.isoformat() if b.maturity_date else None,
                "first_fee_date": b.first_fee_date.isoformat() if b.first_fee_date else None,
                "pay_freq_months": b.pay_freq_months,
                "xhtn": b.xhtn,
                "par_value": float(b.par_value),
                "interest_config": {
                    "rate_type": ic.rate_type,
                    "fixed_rate": float(ic.fixed_rate) if ic and ic.fixed_rate is not None else None,
                    "spread": float(ic.spread) if ic and ic.spread is not None else None,
                    "reference_rate_name": rate_name_by_id.get(ic.reference_rate_id) if ic else None,
                    "first4_rate": float(ic.first4_rate) if ic and ic.first4_rate is not None else None,
                    "floor_rate": float(ic.floor_rate) if ic and ic.floor_rate is not None else None,
                    "cap_rate": float(ic.cap_rate) if ic and ic.cap_rate is not None else None,
                } if ic else None,
                "monthly_data": {
                    md.month_key: {
                        "advised_volume": float(md.advised_volume) if md.advised_volume is not None else None,
                        "buyback_volume": float(md.buyback_volume) if md.buyback_volume is not None else None,
                        "invested_volume": float(md.invested_volume) if md.invested_volume is not None else None,
                        "sold_volume": float(md.sold_volume) if md.sold_volume is not None else None,
                    }
                    for md in b.monthly_data
                },
                "fee_configs": [
                    {
                        "fee_type_key": f.fee_type_key,
                        "default_rate": float(f.default_rate),
                        "method": f.method,
                        "recognition_month": f.recognition_month,
                        "freq_months": f.freq_months,
                        "timing": f.timing,
                        "periods": [
                            {
                                "effective_from": p.effective_from.isoformat(),
                                "effective_to": p.effective_to.isoformat() if p.effective_to else None,
                                "fee_rate": float(p.fee_rate),
                            }
                            for p in f.rate_periods
                        ],
                    }
                    for f in b.fee_configs
                ],
            }
        )

    contracts_projects = []
    for p in db.query(ContractProject).order_by(ContractProject.sort_order).all():
        contracts_projects.append(
            {
                "name": p.name,
                "contracts": [
                    {
                        "contract_date": c.contract_date.isoformat() if c.contract_date else None,
                        "title": c.title,
                        "contract_number": c.contract_number,
                        "status": c.status,
                        "parties": c.parties,
                    }
                    for c in sorted(p.contracts, key=lambda c: c.sort_order)
                ],
            }
        )

    ir_jobs = [
        {"name": j.name, "monthly_values": {mv.month_key: float(mv.revenue) for mv in j.monthly_revenue}}
        for j in db.query(IRJob).order_by(IRJob.sort_order).all()
    ]

    equity = {e.month_key: float(e.value) for e in db.query(EquityMonthlyValue).all()}

    bond_code_by_id = {b.id: b.code for b in db.query(Bond).all()}
    weekly = [
        {"bond_code": bond_code_by_id.get(w.bond_id), "week_key": w.week_key, "volume": float(w.volume)}
        for w in db.query(WeeklyPortfolioValue).all()
        if w.bond_id in bond_code_by_id
    ]

    item_key_by_id = {i.id: i.item_key for i in db.query(ComplianceItem).all()}
    compliance = [
        {
            "bond_code": bond_code_by_id.get(e.bond_id),
            "item_key": item_key_by_id.get(e.compliance_item_id),
            "month_key": e.month_key,
            "text": e.text,
            "done": e.done,
            "note": e.note,
            "deadline": e.deadline.isoformat() if e.deadline else None,
        }
        for e in db.query(ComplianceChecklistEntry).all()
        if e.bond_id in bond_code_by_id
    ]

    return {
        "schema": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "reference_rates": reference_rates,
        "bonds": bonds_out,
        "contracts_projects": contracts_projects,
        "ir_jobs": ir_jobs,
        "equity": equity,
        "weekly_portfolio": weekly,
        "compliance": compliance,
    }


# --------------------------------------------------------------------------- #
# Full JSON import — additive only, never overwrites an existing record
# (prompt §5: "không được làm hỏng dữ liệu hiện có")
# --------------------------------------------------------------------------- #


def import_full_json(db: Session, data: dict, user_id: str | None) -> dict:
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("File JSON không đúng định dạng export (thiếu 'schema': 1).")

    created: dict[str, int] = {}
    skipped: dict[str, int] = {}
    errors: list[str] = []

    def bump(counter: dict[str, int], key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    # -- reference rates: two passes so calculated rates can reference names created in this same import
    rate_by_name = {r.name: r for r in db.query(ReferenceRate).all()}
    pending_components: list[tuple[ReferenceRate, list[str]]] = []
    for item in data.get("reference_rates", []):
        name = item.get("name")
        if not name or name in rate_by_name:
            bump(skipped, "reference_rates")
            continue
        rate = ReferenceRate(name=name, rate_type=item["rate_type"], calc_method=item.get("calc_method"), created_by=user_id, updated_by=user_id)
        db.add(rate)
        db.flush()
        rate_by_name[name] = rate
        for ym, val in (item.get("monthly_values") or {}).items():
            db.add(ReferenceRateMonthlyValue(reference_rate_id=rate.id, month_key=ym, rate=val, updated_by=user_id))
        if item.get("component_names"):
            pending_components.append((rate, [n for n in item["component_names"] if n]))
        bump(created, "reference_rates")

    for rate, names in pending_components:
        for n in names:
            comp = rate_by_name.get(n)
            if comp:
                db.add(ReferenceRateComponent(reference_rate_id=rate.id, component_rate_id=comp.id))
            else:
                errors.append(f"Reference rate '{rate.name}': không tìm thấy component '{n}'.")

    # -- bonds
    bond_by_code = {b.code: b for b in db.query(Bond).all()}
    for item in data.get("bonds", []):
        code = item.get("code")
        if not code or code in bond_by_code:
            bump(skipped, "bonds")
            continue
        bond = Bond(
            code=code,
            issue_date=item.get("issue_date"), maturity_date=item.get("maturity_date"),
            first_fee_date=item.get("first_fee_date"), pay_freq_months=item.get("pay_freq_months", 3),
            xhtn=item.get("xhtn"), par_value=item.get("par_value", 100),
            created_by=user_id, updated_by=user_id,
        )
        db.add(bond)
        db.flush()
        bond_by_code[code] = bond

        ic = item.get("interest_config") or {}
        ref_id = rate_by_name[ic["reference_rate_name"]].id if ic.get("reference_rate_name") in rate_by_name else None
        db.add(BondInterestConfig(
            bond_id=bond.id, rate_type=ic.get("rate_type", "fixed"), fixed_rate=ic.get("fixed_rate"),
            spread=ic.get("spread"), reference_rate_id=ref_id, first4_rate=ic.get("first4_rate"),
            floor_rate=ic.get("floor_rate"), cap_rate=ic.get("cap_rate"), updated_by=user_id,
        ))

        for ym, md in (item.get("monthly_data") or {}).items():
            db.add(BondMonthlyData(
                bond_id=bond.id, month_key=ym, advised_volume=md.get("advised_volume"),
                buyback_volume=md.get("buyback_volume"), invested_volume=md.get("invested_volume"),
                sold_volume=md.get("sold_volume"), created_by=user_id, updated_by=user_id,
            ))

        fee_by_key = {f["key"]: f for f in FEE_DEFS}
        for fc in item.get("fee_configs", []):
            key = fc.get("fee_type_key")
            if key not in fee_by_key:
                continue
            cfg = BondFeeConfig(
                bond_id=bond.id, fee_type_key=key, default_rate=fc.get("default_rate", 0),
                method=fc.get("method", fee_by_key[key]["methods"][0]), recognition_month=fc.get("recognition_month"),
                freq_months=fc.get("freq_months", 1), timing=fc.get("timing", "end"), updated_by=user_id,
            )
            db.add(cfg)
            db.flush()
            for p in fc.get("periods", []):
                db.add(BondFeeRatePeriod(
                    bond_fee_config_id=cfg.id, effective_from=p["effective_from"], effective_to=p.get("effective_to"),
                    fee_rate=p["fee_rate"], created_by=user_id,
                ))
        bump(created, "bonds")

    # -- contracts
    project_by_name = {p.name: p for p in db.query(ContractProject).all()}
    for item in data.get("contracts_projects", []):
        name = item.get("name")
        if not name or name in project_by_name:
            bump(skipped, "contracts_projects")
            continue
        project = ContractProject(name=name, sort_order=len(project_by_name), created_by=user_id, updated_by=user_id)
        db.add(project)
        db.flush()
        project_by_name[name] = project
        for i, c in enumerate(item.get("contracts", [])):
            db.add(Contract(
                project_id=project.id, contract_date=c.get("contract_date"), title=c.get("title", ""),
                contract_number=c.get("contract_number"), status=c.get("status", "Dự thảo"), parties=c.get("parties"),
                sort_order=i, created_by=user_id, updated_by=user_id,
            ))
        bump(created, "contracts_projects")

    # -- IR jobs
    job_by_name = {j.name: j for j in db.query(IRJob).all()}
    for item in data.get("ir_jobs", []):
        name = item.get("name")
        if not name or name in job_by_name:
            bump(skipped, "ir_jobs")
            continue
        job = IRJob(name=name, sort_order=len(job_by_name), created_by=user_id, updated_by=user_id)
        db.add(job)
        db.flush()
        job_by_name[name] = job
        for ym, rev in (item.get("monthly_values") or {}).items():
            db.add(IRMonthlyRevenue(ir_job_id=job.id, month_key=ym, revenue=rev, updated_by=user_id))
        bump(created, "ir_jobs")

    # -- equity
    equity_months = {e.month_key for e in db.query(EquityMonthlyValue).all()}
    for ym, val in (data.get("equity") or {}).items():
        if ym in equity_months:
            bump(skipped, "equity")
            continue
        db.add(EquityMonthlyValue(month_key=ym, value=val, updated_by=user_id))
        bump(created, "equity")

    # -- weekly portfolio (needs bond by code, pre-existing or just imported)
    existing_weekly = {(w.bond_id, w.week_key) for w in db.query(WeeklyPortfolioValue).all()}
    for item in data.get("weekly_portfolio", []):
        bond = bond_by_code.get(item.get("bond_code"))
        if not bond:
            errors.append(f"Weekly: không tìm thấy bond code '{item.get('bond_code')}'.")
            continue
        key = (bond.id, item["week_key"])
        if key in existing_weekly:
            bump(skipped, "weekly_portfolio")
            continue
        db.add(WeeklyPortfolioValue(bond_id=bond.id, week_key=item["week_key"], volume=item.get("volume", 0), updated_by=user_id))
        bump(created, "weekly_portfolio")

    # -- compliance (always additive — multiple entries per item/month are expected)
    item_by_key = {i.item_key: i for i in db.query(ComplianceItem).all()}
    for item in data.get("compliance", []):
        bond = bond_by_code.get(item.get("bond_code"))
        citem = item_by_key.get(item.get("item_key"))
        if not bond or not citem:
            errors.append(f"Compliance: không tìm thấy bond/item cho {item.get('bond_code')}/{item.get('item_key')}.")
            continue
        db.add(ComplianceChecklistEntry(
            bond_id=bond.id, compliance_item_id=citem.id, month_key=item["month_key"], text=item.get("text", ""),
            done=item.get("done", False), note=item.get("note"), deadline=item.get("deadline"),
            created_by=user_id, updated_by=user_id,
        ))
        bump(created, "compliance")

    return {"created": created, "skipped": skipped, "errors": errors}


# --------------------------------------------------------------------------- #
# Reset (Admin only, prompt §5)
# --------------------------------------------------------------------------- #


def reset_all_business_data(db: Session, user_id: str | None) -> None:
    for model in [
        ComplianceChecklistEntry, WeeklyPortfolioValue, EquityMonthlyValue,
        Contract, ContractProject, IRMonthlyRevenue, IRJob,
        BondFeeRatePeriod, BondFeeConfig, BondMonthlyData, BondInterestConfig, Bond,
        ReferenceRateComponent, ReferenceRateMonthlyValue, ReferenceRate,
    ]:
        db.query(model).delete()
    db.query(AuditLog).delete()
    record_create(db, user_id=user_id, module="system_reset", record_id="all", snapshot={"reset_at": datetime.now(timezone.utc).isoformat()})


# --------------------------------------------------------------------------- #
# Duplicate detection (prompt §27) — bonds, keyed by normalized code
# --------------------------------------------------------------------------- #


def _normalize_key(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).upper()


def find_duplicate_bonds(db: Session) -> list[dict]:
    bonds = db.query(Bond).filter(Bond.is_deleted.is_(False)).all()
    groups: dict[str, list[Bond]] = {}
    for b in bonds:
        groups.setdefault(_normalize_key(b.code), []).append(b)
    return [
        {"normalized_key": key, "bond_ids": [b.id for b in members], "codes": [b.code for b in members]}
        for key, members in groups.items()
        if len(members) > 1
    ]
