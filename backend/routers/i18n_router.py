"""
i18n router — serves languages, translation bundles and country code packs
straight from the database. No language string is hardcoded in the app.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from auth import get_current_user
import models
import i18n_store
from platform_models import LocaleString

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/locales")
def locales(db: Session = Depends(get_db)):
    """Available languages (public — needed on the login screen)."""
    return i18n_store.list_locales(db)


@router.get("/countries")
def countries(db: Session = Depends(get_db)):
    from platform_models import Country
    return [
        {"code": c.code, "name": c.name, "default_locale": c.default_locale,
         "currency": c.currency, "timezone": c.timezone}
        for c in db.query(Country).filter_by(enabled=True).order_by(Country.sort_order).all()
    ]


@router.get("/country/{code}")
def country_pack(code: str, db: Session = Depends(get_db)):
    """Country profile + engineering code packs with official proof sources."""
    data = i18n_store.country_bundle(db, code.upper())
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/{locale}")
def bundle(locale: str, db: Session = Depends(get_db)):
    """Full translation bundle for a locale (public)."""
    return i18n_store.build_bundle(db, locale)


# ── Admin: edit translations at runtime (no redeploy to change wording) ────────
class StringUpsert(BaseModel):
    locale: str
    namespace: str
    key: str
    value: str


@router.post("/strings")
def upsert_string(data: StringUpsert,
                  current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    if current_user.role != "admin" and not current_user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    row = db.query(LocaleString).filter_by(
        locale=data.locale, namespace=data.namespace, skey=data.key).first()
    if row:
        row.value = data.value
    else:
        row = LocaleString(locale=data.locale, namespace=data.namespace,
                           skey=data.key, value=data.value)
        db.add(row)
    db.commit()
    return {"ok": True, "locale": data.locale, "key": data.key}
