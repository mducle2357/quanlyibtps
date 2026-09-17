from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ReferenceRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    rate_type: str  # manual | calculated
    calc_method: str | None = None  # average | min | max, required if calculated
    component_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_shape(self):
        if self.rate_type not in ("manual", "calculated"):
            raise ValueError("rate_type phải là 'manual' hoặc 'calculated'.")
        if self.rate_type == "calculated":
            if self.calc_method not in ("average", "min", "max"):
                raise ValueError("Calculated Rate cần calc_method là average/min/max.")
            if not self.component_ids:
                raise ValueError("Calculated Rate cần ít nhất một benchmark thành phần.")
        else:
            if self.component_ids:
                raise ValueError("Manual Rate không có benchmark thành phần.")
        return self


class ReferenceRateUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    calc_method: str | None = None
    component_ids: list[str] = Field(default_factory=list)
    version: int


class SetMonthlyValueRequest(BaseModel):
    rate: float
    version: int | None = None  # None = expect the cell to not exist yet


class MonthlyValueOut(BaseModel):
    rate: float
    version: int


class ReferenceRateOut(BaseModel):
    id: str
    name: str
    rate_type: str
    calc_method: str | None
    component_ids: list[str]
    monthly_values: dict[str, MonthlyValueOut]
    version: int
    created_at: datetime
    updated_at: datetime
