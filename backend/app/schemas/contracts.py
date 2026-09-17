from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.contracts import CONTRACT_STATUSES


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: int


class ContractCreate(BaseModel):
    contract_date: date | None = None
    title: str = ""
    contract_number: str | None = None
    status: str = "Dự thảo"
    parties: str | None = None

    @model_validator(mode="after")
    def check_status(self):
        if self.status not in CONTRACT_STATUSES:
            raise ValueError(f"status phải là một trong {CONTRACT_STATUSES}")
        return self


class ContractUpdate(ContractCreate):
    version: int


class ContractOut(BaseModel):
    id: str
    contract_date: date | None
    title: str
    contract_number: str | None
    status: str
    parties: str | None
    sort_order: int
    version: int


class ProjectOut(BaseModel):
    id: str
    roman_index: int
    name: str
    sort_order: int
    version: int
    contracts: list[ContractOut]
