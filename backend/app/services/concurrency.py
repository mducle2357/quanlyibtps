from app.core.errors import ConflictError


def check_version(entity_version: int, expected_version: int) -> None:
    """Immediate, friendly 409 when the client's copy is stale (prompt §3).

    This is a fast-path check; the actual guarantee against a race between two
    concurrent requests is the SQLAlchemy `version_id_col` on the model, which
    raises StaleDataError at flush and is translated to the same 409 by the
    global exception handler in app.main.
    """
    if entity_version != expected_version:
        raise ConflictError(current_version=entity_version)
