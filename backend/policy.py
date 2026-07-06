"""
NagaForge — Central RBAC Policy Engine

One place decides "can this role reach this route?" — enforced in middleware for
every request, so all 288 routes are covered without per-route decorators.

- Capabilities live in the DB `roles` table (single source of truth). The
  ROLE_ACCESS constant in auth.py is only the initial seed.
- Route prefixes map to a capability. Admin and platform admins bypass checks.
- Unmapped protected routes still require a valid token (fail-closed on auth,
  fail-open on capability) so nothing silently breaks — but data is still
  tenant-isolated by tenancy.py regardless.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

# Longest-prefix-wins map of URL prefix -> capability key.
# Mirrors the nav capabilities used by ROLE_ACCESS.
ROUTE_CAPABILITY = [
    ("/seed",         "saas"),      # dev/global seeding — admins only
    ("/auth/users",   "users"),
    ("/company",      "company"),
    ("/projects",     "projects"),
    ("/workers",      "workers"),
    ("/finance",      "finance"),
    ("/invoices",     "finance"),
    ("/expenses",     "finance"),
    ("/clients",      "clients"),
    ("/documents",    "documents"),
    ("/inventory",    "inventory"),
    ("/commercial",   "commercial"),
    ("/controls",     "controls"),
    ("/scheduling",   "scheduling"),
    ("/site-ops",     "siteops"),
    ("/siteops",      "siteops"),
    ("/site",         "siteops"),
    ("/quality",      "quality"),
    ("/safety",       "safety"),
    ("/structural",   "structural"),
    ("/calculations", "structural"),
    ("/intl",         "intlcodes"),
    ("/steel",        "steel"),
    ("/nbc-canada",   "nbc"),
    ("/nbc",          "nbc"),
    ("/bim",          "bim"),
    ("/reports",      "reports"),
    ("/saas",         "saas"),
    ("/docs",         "saas"),
    ("/redoc",        "saas"),
    ("/openapi.json", "saas"),
]

# Routes any authenticated user may hit regardless of role.
OPEN_TO_AUTHENTICATED = ("/auth/me", "/auth/roles", "/i18n")


def required_capability(path: str) -> Optional[str]:
    for prefix, cap in ROUTE_CAPABILITY:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix):
            return cap
    return None


# ── DB-backed capability cache ────────────────────────────────────────────────
_lock = threading.RLock()
_cache: Optional[Dict[str, Set[str]]] = None


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def _load(db: Session) -> Dict[str, Set[str]]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        caps: Dict[str, Set[str]] = {}
        try:
            from platform_models import Role
            for r in db.query(Role).all():
                caps[r.name] = set(r.capabilities or [])
        except Exception:
            caps = {}
        if not caps:
            # Fall back to the seed constant if the table isn't populated yet.
            try:
                from auth import ROLE_ACCESS
                caps = {k: set(v) for k, v in ROLE_ACCESS.items()}
            except Exception:
                caps = {}
        _cache = caps
        return caps


def capabilities_for(role: str, db: Session) -> Set[str]:
    if role in ("admin", "platform_admin"):
        # Admins get everything; the '*' is expanded by callers that need a list.
        return {"*"}
    return _load(db).get(role, set())


def can_access(role: str, capability: Optional[str], db: Session) -> bool:
    if role in ("admin", "platform_admin"):
        return True
    if capability is None:
        return True  # authenticated-only route
    return capability in _load(db).get(role, set())
