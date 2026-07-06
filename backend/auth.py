"""
JWT Authentication utilities for NagaForge
Uses python-jose for JWT + bcrypt directly for password hashing
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from config import settings
import models

# Single source of truth for signing — env-driven via config.Settings.
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
TOKEN_EXPIRE_HOURS = settings.ACCESS_TOKEN_EXPIRE_HOURS

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# What each role can access (used by frontend for nav gating)
ROLE_ACCESS = {
    "admin":           ["dashboard","company","projects","tasks","workers","clients","finance","documents","inventory","safety","signoff","structural","intlcodes","steel","nbc","scheduling","commercial","controls","siteops","attendance","quality","reports","bim","team_roles","saas","users"],
    "project_manager": ["dashboard","projects","tasks","workers","clients","documents","signoff","structural","intlcodes","steel","nbc","scheduling","safety","inventory","controls","reports"],
    "site_engineer":   ["dashboard","projects","tasks","documents","signoff","structural","intlcodes","steel","nbc","scheduling","safety","inventory","siteops","quality"],
    "designer":        ["dashboard","projects","documents","signoff","structural","intlcodes","steel","nbc","bim"],
    "finance":         ["dashboard","finance","clients","projects"],
    "foreman":         ["dashboard","tasks","safety","inventory","workers"],
    "client":          ["dashboard","projects","documents"],
    "worker":          ["dashboard","tasks"],
    "engineer":        ["dashboard","projects","tasks","documents","signoff","structural","intlcodes","steel","nbc","controls","quality","bim"],
    "site_manager":    ["dashboard","projects","tasks","workers","documents","scheduling","safety","inventory","siteops","attendance","controls","reports"],
    "safety_officer":  ["dashboard","projects","tasks","safety","siteops","controls","reports"],
    "quality_engineer":["dashboard","projects","tasks","quality","documents","controls","reports"],
    "accountant":      ["dashboard","finance","clients","projects","commercial","controls","reports"],
}


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ── Refresh tokens (long-lived, rotated, stored hashed) ───────────────────────
import hashlib
import secrets as _secrets


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user, ip: Optional[str] = None) -> str:
    """Issue a new opaque refresh token; only its hash is stored."""
    raw = _secrets.token_urlsafe(48)
    rt = models.RefreshToken(
        user_id=user.id, token=_hash_token(raw),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False, ip_address=(ip or "")[:50] or None,
    )
    db.add(rt); db.commit()
    return raw


def verify_refresh_token(db: Session, raw: str):
    if not raw:
        return None
    rt = (db.query(models.RefreshToken)
            .filter(models.RefreshToken.token == _hash_token(raw),
                    models.RefreshToken.is_revoked == False)  # noqa: E712
            .first())
    if not rt:
        return None
    if rt.expires_at and rt.expires_at < datetime.utcnow():
        return None
    return rt


def revoke_refresh_token(db: Session, raw: str) -> bool:
    rt = verify_refresh_token(db, raw)
    if rt:
        rt.is_revoked = True
        db.commit()
        return True
    return False


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")

    user = db.query(models.User).filter(
        models.User.username == username,
        models.User.is_active == True
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_roles(*roles):
    """Dependency factory — restricts endpoint to given roles (admin always allowed)."""
    def checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role == "admin":
            return current_user
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker

# Optional auth — returns user or None (for endpoints accessible when logged out)
def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return db.query(models.User).filter(
            models.User.username == username,
            models.User.is_active == True
        ).first()
    except JWTError:
        return None
