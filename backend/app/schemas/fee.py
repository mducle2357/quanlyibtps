from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class FeeRatePeriodCreate(BaseModel):
    effective_from: date
    effective_to: date | None = None
    fee_rate: float

    @model_validator(mode="after")
    def check_range(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to phải >= effective_from.")
        return self


class FeeRatePeriodOut(BaseModel):
    id: str
    effective_from: date
    effective_to: date | None
    fee_rate: float


class FeeConfigUpdate(BaseModel):
    default_rate: float
    method: str
    recognition_month: str | None = None
    freq_months: int = Field(default=1, gt=0)
    timing: str = "end"
    version: int

    @model_validator(mode="after")
    def check_timing(self):
        if self.timing not in ("begin", "end"):
            raise ValueError("timing phải là 'begin' hoặc 'end'.")
        return self


class FeeConfigOut(BaseModel):
    fee_type_key: str
    name: str
    basis: str
    allowed_methods: list[str]
    default_rate: float
    method: str
    recognition_month: str | None
    freq_months: int
    timing: str
    version: int
    updated_at: datetime
    periods: list[FeeRatePeriodOut]
