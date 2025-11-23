"""Database initialization helpers."""

from sqlalchemy import text
from sqlmodel import SQLModel, Session, select

from app.db.base import SQLModel as BaseModel  # noqa
from app.db.session import engine
from app.models.user import User

ADMIN_EMAIL = "admin@saral"
ADMIN_PASSWORD = "Admin!23"


def init_db() -> None:
    """Create database tables and seed default data."""
    SQLModel.metadata.create_all(bind=engine)
    _ensure_kyc_columns()
    _seed_admin_user()


def _seed_admin_user() -> None:
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == ADMIN_EMAIL)).first()
        if existing:
            return
        admin = User(email=ADMIN_EMAIL, full_name="Saral Admin", is_admin=True)
        admin.set_password(ADMIN_PASSWORD)
        session.add(admin)
        session.commit()


def _ensure_kyc_columns() -> None:
    """Ensure new KYC columns exist for legacy SQLite databases."""
    if engine.url.get_backend_name() != "sqlite":
        return

    columns_to_add = [
        ("kyc_application", "parent_name", "TEXT"),
        ("kyc_application", "contact_number", "TEXT"),
        ("kyc_application", "nationality", "TEXT"),
        ("kyc_application", "address_line", "TEXT"),
        ("kyc_application", "pincode", "TEXT"),
        ("kyc_application", "user_id", "INTEGER"),
        ("kyc_application", "completed_at", "DATETIME"),
    ]

    with engine.begin() as connection:
        for table, column, ddl in columns_to_add:
            result = connection.execute(text(f"PRAGMA table_info('{table}')"))
            existing_columns = {row[1] for row in result}
            if column not in existing_columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

