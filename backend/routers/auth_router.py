"""
Auth router — login, user management
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models
from auth import (hash_password, verify_password, create_access_token, get_current_user,
                 ROLE_ACCESS, create_refresh_token, verify_refresh_token, revoke_refresh_token)
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])


def _access_for(db: Session, role: str) -> list:
    """Capabilities come from the DB `roles` table (single source of truth),
    with the seed constant as a fallback."""
    try:
        from platform_models import Role
        row = db.query(Role).filter_by(name=role).first()
        if row and row.capabilities:
            return list(row.capabilities)
    except Exception:
        pass
    return list(ROLE_ACCESS.get(role, []))


def _token_for(user) -> str:
    return create_access_token({
        "sub": user.username,
        "role": user.role,
        "uid": user.id,
        "cid": user.company_id,
        "demo": bool(getattr(user, "is_demo", False)),
        "padmin": bool(getattr(user, "is_platform_admin", False)),
    })


ROLES = [
    "admin","project_manager","site_engineer","designer","finance","foreman","client","worker",
    "engineer","site_manager","safety_officer","quality_engineer","accountant"
]

# ── Pydantic schemas ────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    full_name: str
    email: Optional[str] = None
    role: str = "site_engineer"
    country: str = "India"
    language: str = "en"
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str]
    role: str
    country: Optional[str] = "India"
    language: Optional[str] = "en"
    is_active: bool
    class Config:
        from_attributes = True

# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/login")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account disabled. Contact admin.")
    ip = getattr(getattr(request, "client", None), "host", None)
    return {
        "access_token": _token_for(user),
        "refresh_token": create_refresh_token(db, user, ip),
        "token_type": "bearer",
        "user": _user_public(db, user),
    }


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(data: RefreshIn, request: Request, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a fresh access token (with rotation),
    so a browser reload never logs the user out."""
    rt = verify_refresh_token(db, data.refresh_token)
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.query(models.User).filter(models.User.id == rt.user_id,
                                        models.User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    # Rotate: revoke the presented token, issue a new one.
    rt.is_revoked = True
    db.commit()
    ip = getattr(getattr(request, "client", None), "host", None)
    return {
        "access_token": _token_for(user),
        "refresh_token": create_refresh_token(db, user, ip),
        "token_type": "bearer",
        "user": _user_public(db, user),
    }


@router.post("/logout")
def logout(data: RefreshIn, db: Session = Depends(get_db)):
    revoke_refresh_token(db, data.refresh_token)
    return {"ok": True}


def _user_public(db: Session, user) -> dict:
    country = user.country or (user.company.country if user.company else None) or "India"
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "country": country,
        "language": user.language or "en",
        "company_id": user.company_id,
        "is_demo": bool(getattr(user, "is_demo", False)),
        "is_platform_admin": bool(getattr(user, "is_platform_admin", False)),
        "access": _access_for(db, user.role),
    }


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    return _user_public(db, current_user)


class MePrefs(BaseModel):
    language: Optional[str] = None
    country: Optional[str] = None


@router.put("/me")
def update_me(data: MePrefs,
              current_user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Self-service profile prefs — lets any signed-in user persist the language
    they picked so it follows them on every device/session (validated against
    the DB's enabled locales)."""
    if data.language is not None:
        try:
            from platform_models import Locale
            valid = {l.code for l in db.query(Locale).filter_by(enabled=True).all()}
        except Exception:
            valid = {"en"}
        if valid and data.language not in valid:
            raise HTTPException(status_code=400, detail="Unsupported language")
        current_user.language = data.language
    if data.country is not None:
        current_user.country = data.country
    db.commit(); db.refresh(current_user)
    return _user_public(db, current_user)

@router.get("/users", response_model=List[UserOut])
def list_users(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    q = db.query(models.User)
    # Company admins only see their own tenant's users; platform admins see all.
    if not getattr(current_user, "is_platform_admin", False):
        q = q.filter(models.User.company_id == current_user.company_id)
    return q.order_by(models.User.id).all()

@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if data.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose: {', '.join(ROLES)}")
    user = models.User(
        company_id=current_user.company_id,
        username=data.username,
        full_name=data.full_name,
        email=data.email,
        role=data.role,
        country=data.country or current_user.country or "India",
        language=data.language,
        hashed_password=hash_password(data.password),
        is_active=True,
    )
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.full_name is not None: user.full_name = data.full_name
    if data.email is not None: user.email = data.email
    if data.role is not None: user.role = data.role
    if data.country is not None: user.country = data.country
    if data.language is not None: user.language = data.language
    if data.is_active is not None: user.is_active = data.is_active
    if data.password: user.hashed_password = hash_password(data.password)
    db.commit(); db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user); db.commit()
    return {"message": "User deleted"}

@router.get("/roles")
def get_roles():
    return [{"role": r, "access": ROLE_ACCESS.get(r, [])} for r in ROLES]
