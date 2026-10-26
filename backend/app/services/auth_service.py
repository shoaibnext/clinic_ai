from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database.models import User


def create_user(
    db: Session,
    *,
    clinic_id: int,
    email: str,
    password: str,
    full_name: str,
    role: str = "admin",
) -> User:
    user = User(
        clinic_id=clinic_id,
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: Session, clinic_id: int, email: str) -> User | None:
    return (
        db.query(User)
        .filter(User.clinic_id == clinic_id, User.email == email.lower().strip())
        .first()
    )


def authenticate_user(db: Session, clinic_id: int, email: str, password: str) -> User | None:
    user = get_user_by_email(db, clinic_id, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_token(user: User) -> str:
    return create_access_token(user.clinic_id, user.id, role=user.role)