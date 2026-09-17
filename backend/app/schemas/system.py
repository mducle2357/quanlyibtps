from pydantic import BaseModel


class TimelineRange(BaseModel):
    start: str  # YYYY-MM
    end: str  # YYYY-MM
