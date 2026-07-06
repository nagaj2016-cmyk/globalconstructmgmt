"""
NagaForge — Tenant Isolation Engine
====================================

Row-level multi-tenancy that is enforced *centrally* instead of being
hand-written into all 288 routes. Two SQLAlchemy hooks do the work:

1. do_orm_execute  -> every SELECT that touches a tenant table is automatically
   constrained to the current request's company_id (and, for the demo account,
   to demo rows). A user therefore can never read another tenant's data, even on
   an endpoint that forgot to filter.

2. before_flush    -> every INSERT into a tenant table is automatically stamped
   with the current company_id / is_demo, so writes land in the right tenant
   without every create endpoint having to remember.

The "current tenant" travels with the request through a contextvar that the
auth middleware populates from the JWT. Background jobs, migrations and the
login path run with NO context set, so they see everything (no accidental
lock-out during seeding).

Design goals:
- Zero per-route changes required for correctness.
- Fail-closed: if a tenant context is set, tenant tables are always filtered.
- Explicit escape hatch: `.execution_options(skip_tenant=True)` for admin tools.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, event
from sqlalchemy.orm import Session, declared_attr, with_loader_criteria
from sqlalchemy.sql import expression


# ── Per-request tenant context ────────────────────────────────────────────────
@dataclass
class TenantContext:
    user_id: Optional[int] = None
    username: Optional[str] = None
    company_id: Optional[int] = None
    role: Optional[str] = None
    is_demo: bool = False
    # Platform admins (the root operator) bypass tenant filtering for support.
    is_platform_admin: bool = False


_ctx: contextvars.ContextVar[Optional[TenantContext]] = contextvars.ContextVar(
    "nagaforge_tenant_ctx", default=None
)


def set_tenant(ctx: Optional[TenantContext]):
    return _ctx.set(ctx)


def reset_tenant(token) -> None:
    try:
        _ctx.reset(token)
    except (ValueError, LookupError):
        pass


def current_tenant() -> Optional[TenantContext]:
    return _ctx.get()


# ── Mixin applied to every tenant-scoped model ────────────────────────────────
class TenantScoped:
    """Adds company_id + is_demo to a model and marks it for auto-isolation.

    Using a shared superclass lets a single `with_loader_criteria(TenantScoped,...)`
    constrain *all* tenant tables at once."""

    @declared_attr
    def company_id(cls):
        return Column(
            Integer,
            ForeignKey("companies.id", ondelete="CASCADE"),
            index=True,
            nullable=True,
        )

    @declared_attr
    def is_demo(cls):
        return Column(
            Boolean,
            nullable=False,
            index=True,
            default=False,
            server_default=expression.false(),
        )


# ── The two enforcement hooks ─────────────────────────────────────────────────
def _install(session_class=Session) -> None:
    @event.listens_for(session_class, "do_orm_execute")
    def _apply_tenant_filter(execute_state):
        # Only constrain reads; writes are handled by before_flush stamping.
        if not execute_state.is_select:
            return
        if execute_state.execution_options.get("skip_tenant", False):
            return
        ctx = current_tenant()
        if ctx is None or ctx.is_platform_admin:
            return
        cid = ctx.company_id
        # Bool on the RIGHT of `==` so it becomes a cacheable bound parameter.
        # Demo accounts see only demo rows; real tenants never see demo rows.
        demo_val = bool(ctx.is_demo)

        def _crit(cls):
            return (cls.company_id == cid) & (cls.is_demo == demo_val)

        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(TenantScoped, _crit, include_aliases=True)
        )

    @event.listens_for(session_class, "before_flush")
    def _stamp_tenant(session, flush_context, instances):
        ctx = current_tenant()
        if ctx is None or ctx.company_id is None:
            return
        for obj in session.new:
            if isinstance(obj, TenantScoped):
                if getattr(obj, "company_id", None) is None:
                    obj.company_id = ctx.company_id
                # Only auto-mark demo rows for the demo tenant.
                if getattr(obj, "is_demo", None) in (None, False) and ctx.is_demo:
                    obj.is_demo = True


_INSTALLED = False


def install_tenant_isolation() -> None:
    """Idempotently attach the tenant hooks. Call once at startup."""
    global _INSTALLED
    if _INSTALLED:
        return
    _install(Session)
    _INSTALLED = True
