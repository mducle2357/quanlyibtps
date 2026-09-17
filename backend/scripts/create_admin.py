"""Bootstrap the first Admin account. Run once after `alembic upgrade head`:

    python scripts/create_admin.py admin@tps.vn "Quản trị viên" 'StrongPass123!'
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import Role, User, UserRole  # noqa: E402


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python scripts/create_admin.py <email> <full_name> <password>")
        sys.exit(1)
    email, full_name, password = sys.argv[1], sys.argv[2], sys.argv[3]

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email.lower()).first():
            print(f"User {email} already exists.")
            return
        admin_role = db.query(Role).filter(Role.name == "Admin").first()
        if not admin_role:
            print("Role 'Admin' not found — run `alembic upgrade head` first.")
            sys.exit(1)
        user = User(email=email.lower(), full_name=full_name, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db.commit()
        print(f"Created Admin user {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
