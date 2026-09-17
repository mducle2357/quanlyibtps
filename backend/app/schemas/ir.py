from pydantic import BaseModel, Field


class IRJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class IRJobRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: int


class IRMonthlyValueSet(BaseModel):
    revenue: float
    version: int | None = None


class IRJobOut(BaseModel):
    id: str
    name: str
    sort_order: int
    version: int
    monthly_values: dict[str, dict]
