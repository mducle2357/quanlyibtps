from sqlalchemy.orm import Session, selectinload

from app.models.reference_rate import ReferenceRate, ReferenceRateComponent, ReferenceRateMonthlyValue
from app.services.calc_engine import ReferenceRateResolver, RefRateDef

RATE_TYPE_MANUAL = "manual"
RATE_TYPE_CALCULATED = "calculated"
CALC_METHODS = ["average", "min", "max"]


def load_all(db: Session) -> list[ReferenceRate]:
    return (
        db.query(ReferenceRate)
        .options(selectinload(ReferenceRate.components), selectinload(ReferenceRate.monthly_values))
        .order_by(ReferenceRate.name)
        .all()
    )


def build_resolver(db: Session, extra_component_ids: dict[str, list[str]] | None = None) -> ReferenceRateResolver:
    """Builds a resolver over every rate currently in the DB. `extra_component_ids`
    lets a caller preview a not-yet-committed component list for one rate id
    (used by the circular-dependency check before the change is saved)."""
    rates = load_all(db)
    defs: dict[str, RefRateDef] = {}
    for r in rates:
        component_ids = [c.component_rate_id for c in r.components]
        if extra_component_ids and r.id in extra_component_ids:
            component_ids = extra_component_ids[r.id]
        defs[r.id] = RefRateDef(
            id=r.id,
            rate_type=r.rate_type,
            calc_method=r.calc_method,
            monthly_values={mv.month_key: float(mv.rate) for mv in r.monthly_values},
            component_ids=component_ids,
        )
    return ReferenceRateResolver(defs)


def validate_no_cycle(db: Session, rate_id: str, component_ids: list[str]) -> str | None:
    resolver = build_resolver(db)
    for cid in component_ids:
        if resolver.would_cycle(rate_id, cid):
            return f"Không thể thêm benchmark thành phần: sẽ tạo vòng lặp phụ thuộc (circular dependency)."
    return None


def is_referenced(db: Session, rate_id: str) -> bool:
    from app.models.bond import BondInterestConfig

    used_as_component = db.query(ReferenceRateComponent).filter(ReferenceRateComponent.component_rate_id == rate_id).first()
    used_by_bond = db.query(BondInterestConfig).filter(BondInterestConfig.reference_rate_id == rate_id).first()
    return bool(used_as_component or used_by_bond)


def to_dict(r: ReferenceRate) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "rate_type": r.rate_type,
        "calc_method": r.calc_method,
        "component_ids": [c.component_rate_id for c in r.components],
        "monthly_values": {mv.month_key: {"rate": float(mv.rate), "version": mv.version} for mv in r.monthly_values},
        "version": r.version,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }
