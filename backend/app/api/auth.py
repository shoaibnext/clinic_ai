import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.services import auth_service, clinic_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    # Optional tenant scoping: when the caller specifies a clinic slug, only
    # that clinic's account may authenticate. A token can never be issued for
    # a different clinic than the one the caller selected.
    clinic = None
    if payload.clinic_slug:
        clinic = clinic_service.get_clinic_by_slug(db, payload.clinic_slug.strip().lower())
        if clinic is None:
            # Generic message: do not reveal which slugs exist.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

    query = db.query(User).filter(User.email == email, User.is_active.is_(True))
    if clinic is not None:
        query = query.filter(User.clinic_id == clinic.id)
    users = query.all()

    # Backward compatibility: a bare email+password login still works when the
    # email belongs to a single active account. When the same email is
    # registered in more than one clinic we refuse to guess which tenant to
    # authenticate against instead of silently issuing a token for the wrong
    # clinic (regression: cross-tenant login collision).
    if clinic is None and len(users) > 1:
        logger.warning(
            "Ambiguous login for %r — email belongs to %d clinics, clinic_slug required",
            email,
            len(users),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "This email belongs to more than one clinic. "
                "Provide 'clinic_slug' to sign in."
            ),
        )

    authenticated = None
    for candidate in users:
        if auth_service.verify_password(payload.password, candidate.hashed_password):
            authenticated = candidate
            break
    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    token = auth_service.issue_token(authenticated)
    return LoginResponse(
        access_token=token,
        clinic_id=authenticated.clinic_id,
        user_id=authenticated.id,
        role=authenticated.role,
    )