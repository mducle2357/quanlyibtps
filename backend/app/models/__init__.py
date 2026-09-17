"""Import every model module so Base.metadata is complete for Alembic autogenerate."""

from app.models import (  # noqa: F401
    audit,
    bond,
    compliance,
    contracts,
    ir,
    reference_rate,
    user,
    weekly,
)

__all__ = ["audit", "bond", "compliance", "contracts", "ir", "reference_rate", "user", "weekly"]
