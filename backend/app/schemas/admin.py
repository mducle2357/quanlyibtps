from datetime import datetime

from pydantic import BaseModel


class BackupOut(BaseModel):
    id: str
    filename: str
    created_at: datetime
    size_bytes: int
    status: str


class ResetRequest(BaseModel):
    password: str
    confirm_word: str


class ImportReport(BaseModel):
    created: dict[str, int]
    skipped: dict[str, int]
    errors: list[str]


class DuplicateGroup(BaseModel):
    normalized_key: str
    bond_ids: list[str]
    codes: list[str]
