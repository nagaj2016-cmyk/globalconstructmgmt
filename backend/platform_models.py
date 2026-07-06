"""
NagaForge — Platform / configuration tables (NOT tenant-scoped)

These hold cross-tenant configuration that must live in the database so nothing
is hardcoded in the app or the frontend:

- Role            : role -> capability list (the single source of truth for RBAC)
- Locale          : available languages (code, native name, direction)
- LocaleString    : every UI/engineering string, per locale (i18n bundle rows)
- Country         : supported countries -> default locale, currency, timezone
- CodePack        : per-country engineering code packs + clause labels
- ProofSource     : official / government proof links per code pack

All strings the user sees — UI chrome and engineering terminology alike — are
served from LocaleString + CodePack + ProofSource, so language is a data
concern, never a code concern.
"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database import Base


class Role(Base):
    __tablename__ = "roles"
    id            = Column(Integer, primary_key=True)
    name          = Column(String(50), unique=True, nullable=False, index=True)
    label         = Column(String(120))
    capabilities  = Column(JSON, default=list)   # ["dashboard","projects",...]
    is_system     = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


class Locale(Base):
    __tablename__ = "locales"
    id           = Column(Integer, primary_key=True)
    code         = Column(String(12), unique=True, nullable=False, index=True)  # en, fr, hi, ar
    name         = Column(String(80), nullable=False)        # "English"
    native_name  = Column(String(80))                        # "हिन्दी"
    direction    = Column(String(3), default="ltr")          # ltr / rtl
    enabled      = Column(Boolean, default=True)
    sort_order   = Column(Integer, default=100)


class LocaleString(Base):
    __tablename__ = "locale_strings"
    __table_args__ = (
        UniqueConstraint("locale", "namespace", "skey", name="uq_locale_ns_key"),
    )
    id         = Column(Integer, primary_key=True)
    locale     = Column(String(12), nullable=False, index=True)   # en, fr, ...
    namespace  = Column(String(60), nullable=False, index=True)   # nav, common, structural, ...
    skey       = Column(String(120), nullable=False)              # "nav.projects"
    value      = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Country(Base):
    __tablename__ = "countries"
    id             = Column(Integer, primary_key=True)
    code           = Column(String(3), unique=True, nullable=False, index=True)  # IN, CA, US, AE, GB, AU
    name           = Column(String(120), nullable=False)
    default_locale = Column(String(12), default="en")
    currency       = Column(String(8), default="USD")
    timezone       = Column(String(64), default="UTC")
    enabled        = Column(Boolean, default=True)
    sort_order     = Column(Integer, default=100)


class CodePack(Base):
    """A country's engineering code family for a discipline (concrete, steel, loads...)."""
    __tablename__ = "code_packs"
    __table_args__ = (
        UniqueConstraint("country_code", "discipline", "code_name", name="uq_codepack"),
    )
    id            = Column(Integer, primary_key=True)
    country_code  = Column(String(3), nullable=False, index=True)   # IN, CA, ...
    discipline    = Column(String(40), nullable=False)              # concrete, steel, loads, wind, seismic
    code_name     = Column(String(80), nullable=False)             # "IS 456", "CSA A23.3"
    edition       = Column(String(40))                             # "2000", ":19"
    title         = Column(String(200))
    maturity      = Column(String(20), default="draft")            # draft / verified / production
    clause_labels = Column(JSON, default=dict)                     # {"flexure":"Cl. 38", ...}
    proof_keys    = Column(JSON, default=list)                     # ["india_bis","india_nbc"]
    notes         = Column(Text)                                   # current edition / amendment facts
    enabled       = Column(Boolean, default=True)


class ProofSource(Base):
    """Official evidence links. Government/regulator/standards-publisher only."""
    __tablename__ = "proof_sources"
    id           = Column(Integer, primary_key=True)
    key          = Column(String(60), unique=True, nullable=False, index=True)   # india_bis
    label        = Column(String(200), nullable=False)
    publisher    = Column(String(200))
    authority    = Column(String(120))     # Government / Regulator / Official standards publisher / Local authority
    url          = Column(String(500))
    country_code = Column(String(3), index=True)
    notes        = Column(Text)
