from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION SERVICE
#
# This module handles two core security functions:
#   1. Password hashing and verification — using bcrypt
#   2. JWT token creation and decoding — for stateless authentication
#
# Used by:
#   - auth.py endpoint (login, register)
#   - deps_auth.py (verifying tokens on every protected request)
# ─────────────────────────────────────────────────────────────────────────────

settings = get_settings()

# bcrypt password hashing context.
# bcrypt is the industry standard for password hashing —
# it is slow by design to make brute force attacks impractical.
# deprecated="auto" automatically upgrades old hashes if the scheme changes.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT signing algorithm — HS256 (HMAC with SHA-256) is the standard choice
# for symmetric signing where the same secret key is used to sign and verify.
ALGORITHM = "HS256"

# Token expiry — 7 days means users stay logged in for a week.
# Short enough to limit exposure if a token is stolen,
# long enough that users do not need to log in every day.
ACCESS_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    """
    Hashes a plain text password using bcrypt.

    The hash is unique every time even for the same password
    because bcrypt automatically generates a random salt.
    The resulting hash is safe to store in the database.

    Never store plain text passwords.
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies a plain text password against a stored bcrypt hash.

    Used during login — the user provides their password,
    we hash it and compare against what is stored in the database.

    Returns True if they match, False otherwise.
    bcrypt handles the salt extraction internally.
    """
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, role: str) -> str:
    """
    Creates a signed JWT access token for an authenticated user.

    The token payload contains:
        sub  — subject (user ID as string) — identifies who the token belongs to
        role — user role ("user" or "admin") — used for access control
        exp  — expiry timestamp — token is invalid after this time

    The token is signed with the application's secret key so it cannot
    be forged or tampered with without knowing the secret.

    The client stores this token and sends it in the Authorization header
    as "Bearer <token>" on every subsequent request.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodes and verifies a JWT token.

    Raises jwt.ExpiredSignatureError if the token has expired.
    Raises jwt.InvalidTokenError if the token is malformed or tampered with.

    Used by deps_auth.py to authenticate every incoming API request.
    The returned dict contains the payload: {"sub": user_id, "role": role, "exp": ...}
    """
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])