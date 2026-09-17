"""Integration-test harness: every test runs inside one DB transaction that is
rolled back at teardown, so tests never leave data behind or depend on order.
Uses the same Postgres instance as local dev (DATABASE_URL) — no separate test
DB is spun up, since this environment doesn't have one and the point is to
exercise the real driver/constraints, not mock them away.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, engine, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import ALL_ROLES, Role, User, UserRole


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    Base.metadata.create_all(bind=engine)  # no-op if Alembic already applied it
    yield


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    # join_transaction_mode="create_savepoint": route handlers call db.commit(),
    # which would otherwise end `transaction` early. This mode makes commit()
    # only release a SAVEPOINT and immediately open a new one, so the outer
    # transaction (and therefore the final rollback below, undoing everything
    # the test did) survives every commit a route performs.
    TestSession = sessionmaker(
        bind=connection, autoflush=False, autocommit=False, future=True, join_transaction_mode="create_savepoint"
    )
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def make_user(db_session, email: str, role_name: str = "Admin") -> User:
    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    user = User(email=email, full_name=email, password_hash=hash_password("Password123!"))
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.flush()
    return user


@pytest.fixture()
def admin_user(db_session):
    return make_user(db_session, "admin-test@tps.vn", "Admin")


@pytest.fixture()
def staff_user(db_session):
    return make_user(db_session, "staff-test@tps.vn", "Staff")


def auth_headers(user: User) -> dict:
    token = create_access_token(user.id, user.role_names())
    return {"Authorization": f"Bearer {token}"}
