from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class BondCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)


class BondBasicInfoUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    issue_date: date | None = None
    maturity_date: date | None = None
    first_fee_date: date | None = None
    pay_freq_months: int = Field(gt=0)
    xhtn: str | None = None
    par_value: float = Field(gt=0)
    version: int

    @model_validator(mode="after")
    def check_dates(self):
        if self.issue_date and self.maturity_date and self.maturity_date < self.issue_date:
            raise ValueError("Ngày đáo hạn phải >= Ngày phát hành.")
        return self


class InterestConfigUpdate(BaseModel):
    rate_type: str  # fixed | floating | combined | conditional
    fixed_rate: float | None = None
    spread: float | None = None
    reference_rate_id: str | None = None
    first4_rate: float | None = None
    floor_rate: float | None = None
    cap_rate: float | None = None
    version: int

    @model_validator(mode="after")
    def check_shape(self):
        if self.rate_type not in ("fixed", "floating", "combined", "conditional"):
            raise ValueError("rate_type không hợp lệ.")
        if self.rate_type == "fixed" and self.fixed_rate is None:
            raise ValueError("LS cố định cần Lãi suất các kỳ.")
        if self.rate_type == "floating" and (self.spread is None or not self.reference_rate_id):
            raise ValueError("LS thả nổi cần Biên độ và Lãi suất tham chiếu.")
        if self.rate_type in ("combined", "conditional"):
            if self.first4_rate is None or self.spread is None or not self.reference_rate_id:
                raise ValueError("Cần Lãi suất 4 kỳ đầu, Biên độ và Lãi suất tham chiếu.")
        if self.rate_type == "conditional" and self.floor_rate is not None and self.cap_rate is not None:
            if self.floor_rate > self.cap_rate:
                raise ValueError("Không dưới (Floor) không được lớn hơn Không quá (Cap).")
        return self


class MonthlyVolumeUpdate(BaseModel):
    advised_volume: float | None = None
    buyback_volume: float | None = None
    invested_volume: float | None = None
    sold_volume: float | None = None
    hold_start_override: date | None = None
    hold_end_override: date | None = None
    version: int | None = None  # None = expect no row yet for this bond/month

    @model_validator(mode="after")
    def check_holding_period(self):
        if self.hold_start_override and self.hold_end_override and self.hold_start_override > self.hold_end_override:
            raise ValueError("Ngày bắt đầu nắm giữ phải <= Ngày kết thúc.")
        return self


class BondListItem(BaseModel):
    id: str
    code: str
    issue_date: date | None
    maturity_date: date | None
    par_value: float
    status_key: str
    status_label: str
    version: int


class BondDetail(BaseModel):
    id: str
    code: str
    issue_date: date | None
    maturity_date: date | None
    first_fee_date: date | None
    pay_freq_months: int
    xhtn: str | None
    par_value: float
    status_key: str
    status_label: str
    is_deleted: bool
    version: int
    created_at: datetime
    updated_at: datetime
    interest_config: dict
    monthly_data: dict[str, dict]
    fee_configs: list[dict]


class BondMonthComputed(BaseModel):
    month_key: str
    active: bool
    advised: float | None
    buyback: float | None
    outstanding: float | None
    invested: float | None
    sold: float | None
    holding: float | None
    coupon: float | None
    reference_value: float | None
    fees: dict[str, float]
    fee_total: float
    hold_start: date | None
    hold_end: date | None
    hold_days: int | None
    hold_error: bool
    coupon_revenue: float
    total_revenue: float
