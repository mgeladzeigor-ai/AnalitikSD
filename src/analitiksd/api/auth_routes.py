# src/analitiksd/api/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from analitiksd.api.deps import COOKIE_NAME, get_current_user, get_db
from analitiksd.api.schemas import LoginRequest, UserOut
from analitiksd.auth.service import authenticate_user, role_names
from analitiksd.auth.tokens import create_access_token
from analitiksd.config import get_settings
from analitiksd.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> dict[str, str]:
    user = authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=get_settings().jwt_expire_minutes * 60,
    )
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name, roles=role_names(db, user.id)
    )
