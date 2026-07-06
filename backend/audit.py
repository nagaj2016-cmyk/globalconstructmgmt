"""
NagaForge — Audit trail.

A single, immutable record of who did what, when — the backbone of the
calculation sign-off workflow and a compliance requirement for an engineering
system of record.

`record(...)` writes one AuditLog row, stamped with the current tenant (from the
request context) so an admin can review only their own company's trail. Writes
are best-effort: an audit failure must never break the underlying action, but we
surface it in logs.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

import models
from tenancy import current_tenant

_log = logging.getLogger("nagaforge.audit")


def record(
    db: Session,
    action: str,
    entity_type: str,
    entity_id,
    summary: str = "",
    old: Optional[dict] = None,
    new: Optional[dict] = None,
    user=None,
    request=None,
) -> Optional[models.AuditLog]:
    """Append an immutable audit entry. Returns the row (already added to db)."""
    try:
        ctx = current_tenant()
        username = getattr(user, "username", None) or (ctx.username if ctx else None)
        user_id = getattr(user, "id", None) or (ctx.user_id if ctx else None)
        company_id = getattr(user, "company_id", None) or (ctx.company_id if ctx else None)

        ip = ua = None
        if request is not None:
            ip = getattr(getattr(request, "client", None), "host", None)
            ua = request.headers.get("user-agent") if hasattr(request, "headers") else None

        entry = models.AuditLog(
            company_id=company_id,
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=(summary or "")[:300],
            old_value=old,
            new_value=new,
            ip_address=ip,
            user_agent=(ua or "")[:300] if ua else None,
        )
        db.add(entry)
        db.flush()   # assign id without committing the caller's transaction
        return entry
    except Exception as exc:  # never let auditing break the real action
        _log.warning("audit record failed (%s %s): %s", action, entity_type, exc)
        return None


def list_for_tenant(db: Session, company_id: Optional[int], entity_type: str = None,
                    entity_id=None, limit: int = 100):
    """Read audit entries for a tenant (admin view)."""
    q = db.query(models.AuditLog)
    if company_id is not None:
        q = q.filter(models.AuditLog.company_id == company_id)
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(models.AuditLog.entity_id == str(entity_id))
    return q.order_by(models.AuditLog.timestamp.desc()).limit(min(limit, 500)).all()
