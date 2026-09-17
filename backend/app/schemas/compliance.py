from datetime import date

from pydantic import BaseModel, Field


class ComplianceEntryCreate(BaseModel):
    month_key: str
    text: str = ""
    note: str | None = None
    deadline: date | None = None
    assignee_id: str | None = None


class ComplianceEntryUpdate(BaseModel):
    text: str = ""
    done: bool = False
    note: str | None = None
    deadline: date | None = None
    assignee_id: str | None = None
    version: int


class ComplianceEntryOut(BaseModel):
    id: str
    month_key: str
    text: str
    done: bool
    note: str | None
    deadline: date | None
    assignee_id: str | None
    version: int


class ComplianceItemGroup(BaseModel):
    item_id: str
    group_key: str
    item_key: str
    name: str
    entries: list[ComplianceEntryOut]
    done_count: int
    total_count: int
