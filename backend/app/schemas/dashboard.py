from pydantic import BaseModel


class BondPortfolioRow(BaseModel):
    bond_id: str
    code: str
    volume: float
    value: float


class DashboardResponse(BaseModel):
    month_key: str
    equity: float | None
    limit: float | None
    holding_value: float
    remaining_capacity: float | None
    usage_ratio: float | None
    invested_bonds: list[BondPortfolioRow]
    advised_bonds: list[BondPortfolioRow]
    advised_volume_total: float
    fee_total: float
    coupon_revenue: float
    ir_revenue: float
    total_revenue: float
    compliance_done: int
    compliance_total: int


class Alert(BaseModel):
    kind: str  # 'd' danger | 'w' warning | 'i' info
    category: str
    title: str
    detail: str


class EquityValueSet(BaseModel):
    value: float
    version: int | None = None
