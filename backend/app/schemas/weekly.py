from pydantic import BaseModel


class WeeklyVolumeSet(BaseModel):
    volume: float
    version: int | None = None


class WeeklyBondRow(BaseModel):
    bond_id: str
    code: str
    par_value: float
    volume: float | None
    volume_version: int | None
    coupon: float | None
    accrual: float | None


class WeeklyResponse(BaseModel):
    week_key: str
    rows: list[WeeklyBondRow]
    total_accrual: float | None
    latest_week_with_data: str | None


class CarryForwardRequest(BaseModel):
    from_week: str
    to_week: str


class WeeklyCell(BaseModel):
    volume: float | None
    version: int | None
    coupon: float | None
    accrual: float | None


class WeeklyGridBondRow(BaseModel):
    bond_id: str
    code: str
    par_value: float
    cells: dict[str, WeeklyCell]


class WeeklyGridResponse(BaseModel):
    weeks: list[str]
    bonds: list[WeeklyGridBondRow]
    totals: dict[str, float | None]
    latest_week_with_data: str | None
