# src/analitiksd/api/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analitiksd.api.deps import get_current_user, get_db
from analitiksd.api.schemas import UserOut
from analitiksd.auth.service import role_names
from analitiksd.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, roles=role_names(db, user.id)
    )
