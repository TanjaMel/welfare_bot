from __future__ import annotations

from datetime import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user
from app.db.models.password_reset_token import PasswordResetToken
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import TokenResponse, UserLogin, UserRead, UserRegister
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/register", response_model=TokenResponse, status_code=201, summary="Register")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if db.query(User).filter(User.phone_number == payload.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
        language=payload.language,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse, summary="Login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserRead.model_validate(user),
    )


@router.post("/forgot-password", summary="Request password reset")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Always return same message to prevent email enumeration
    generic_response = {
        "message": "If an account with this email exists, a password reset link has been sent."
    }

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return generic_response

    # Generate secure token
    token = secrets.token_urlsafe(32)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=PasswordResetToken.default_expiry(),
        used=False,
    )
    db.add(reset_token)
    db.commit()

    # Send email via SendGrid
    try:
        from app.services.notification_service import send_password_reset_email
        user_name = user.first_name or ""
        sent = send_password_reset_email(
            to_email=user.email,
            reset_token=token,
            user_name=user_name,
        )
        if not sent:
            import logging
            logging.getLogger(__name__).warning(
                "Password reset email could not be sent to %s", user.email
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Password reset email error: %s", e)

    return generic_response


@router.post("/reset-password", summary="Reset password using token")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token)
        .first()
    )

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid reset token.")

    if reset_token.used:
        raise HTTPException(status_code=400, detail="Reset token has already been used.")

    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = hash_password(payload.new_password)
    reset_token.used = True
    db.commit()

    return {"message": "Password has been reset successfully."}


@router.get("/me", response_model=UserRead, summary="Get current user")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user