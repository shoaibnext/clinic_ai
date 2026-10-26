from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.database.models import Clinic


def resolve_clinic(request: Request, db: Session) -> Clinic:
    """Tenant resolution (multi-tenant architecture, build plan section 7):
    1. `Authorization: Bearer <jwt>` -> clinic_id from the token
    2. `X-API-Key: <clinic api key>` -> clinic by its api_key
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
            ) from exc
        clinic = db.get(Clinic, int(payload.get("clinic_id", 0)))
        if clinic is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Clinic not found"
            )
        return clinic

    api_key = request.headers.get("X-API-Key") or ""
    if api_key:
        clinic = db.query(Clinic).filter(Clinic.api_key == api_key).first()
        if clinic is not None:
            return clinic
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
    )


def get_current_clinic(request: Request, db: Session = Depends(get_db)) -> Clinic:
    return resolve_clinic(request, db)