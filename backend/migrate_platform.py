"""
NagaForge — Platform migration & seed (idempotent).

Safe to run on every boot. It:
  1. Creates any new tables (roles, locales, locale_strings, countries,
     code_packs, proof_sources).
  2. Adds company_id + is_demo columns to every tenant table, and
     is_platform_admin + is_demo to users (SQLite/Postgres aware).
  3. Seeds roles from the RBAC seed, plus languages / countries / code packs /
     proofs / translation strings.
  4. Ensures the platform admin and the demo tenant + demo user exist.

Run standalone:  python migrate_platform.py
"""
from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from database import engine, SessionLocal, Base
import models            # noqa: F401  (registers tenant tables + mixin columns)
import platform_models   # noqa: F401  (registers platform tables)
from tenancy import TenantScoped
from auth import hash_password, ROLE_ACCESS
from config import settings


def _dialect() -> str:
    return engine.dialect.name  # 'sqlite' | 'postgresql'


def _add_column(conn, table: str, col: str, ddl_type: str):
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns(table)}
    if col in cols:
        return False
    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl_type}'))
    return True


def add_tenant_columns() -> list:
    """Add company_id / is_demo to tenant tables; user flags to users."""
    d = _dialect()
    bool_type = "BOOLEAN DEFAULT FALSE" if d == "postgresql" else "INTEGER DEFAULT 0"
    int_type = "INTEGER"
    changed = []

    tenant_tables = sorted({
        cls.__tablename__ for cls in Base.registry._class_registry.values()
        if isinstance(cls, type) and issubclass(cls, TenantScoped)
        and hasattr(cls, "__tablename__")
    })

    with engine.begin() as conn:
        existing = set(inspect(conn).get_table_names())
        for t in tenant_tables:
            if t not in existing:
                continue
            if _add_column(conn, t, "company_id", int_type):
                changed.append(f"{t}.company_id")
            if _add_column(conn, t, "is_demo", bool_type):
                changed.append(f"{t}.is_demo")
        if "users" in existing:
            if _add_column(conn, "users", "is_platform_admin", bool_type):
                changed.append("users.is_platform_admin")
            if _add_column(conn, "users", "is_demo", bool_type):
                changed.append("users.is_demo")
        # Platform tables: columns added after their first release.
        if "code_packs" in existing:
            if _add_column(conn, "code_packs", "notes", "TEXT"):
                changed.append("code_packs.notes")
        # Firm branding for calc sheets.
        if "companies" in existing:
            if _add_column(conn, "companies", "seal_url", "VARCHAR(500)"):
                changed.append("companies.seal_url")
        # Audit trail extra columns.
        if "audit_logs" in existing:
            for col, typ in [("company_id", int_type), ("summary", "VARCHAR(300)")]:
                if _add_column(conn, "audit_logs", col, typ):
                    changed.append(f"audit_logs.{col}")
        # Calculation sign-off workflow columns.
        if "calculation_records" in existing:
            calc_cols = [
                ("signoff_status", "VARCHAR(20)"), ("revision", int_type),
                ("supersedes_id", int_type), ("locked", bool_type),
                ("title", "VARCHAR(200)"),
                ("prepared_by", "VARCHAR(200)"), ("prepared_at", "TIMESTAMP"),
                ("checked_by", "VARCHAR(200)"), ("checked_at", "TIMESTAMP"),
                ("approved_by", "VARCHAR(200)"), ("approved_at", "TIMESTAMP"),
            ]
            for col, typ in calc_cols:
                if _add_column(conn, "calculation_records", col, typ):
                    changed.append(f"calculation_records.{col}")
    return changed


# Money columns that must be exact fixed-point NUMERIC(15,2) in production.
MONEY_COLUMNS = {
    "invoices": ["subtotal", "tax_amount", "total", "paid_amount"],
    "invoice_items": ["rate", "amount"],
    "expenses": ["amount"],
    "purchase_orders": ["subtotal", "tax_amount", "total"],
    "po_items": ["unit_rate", "amount"],
    "budgets": ["total_budget"],
    "budget_items": ["budgeted_cost", "actual_cost"],
    "project_contracts": ["contract_value", "variation_amount"],
    "change_orders": ["cost_impact"],
    "projects": ["budget", "spent", "contracted_value"],
    "boq_items": ["unit_rate", "amount"],
}


def convert_money_columns_pg() -> list:
    """On PostgreSQL only, convert legacy float money columns to NUMERIC(15,2).
    No-op on SQLite (dynamic typing) and on fresh installs (already NUMERIC)."""
    if _dialect() != "postgresql":
        return []
    changed = []
    with engine.begin() as conn:
        insp = inspect(conn)
        existing = set(insp.get_table_names())
        for table, cols in MONEY_COLUMNS.items():
            if table not in existing:
                continue
            present = {c["name"]: c for c in insp.get_columns(table)}
            for col in cols:
                info = present.get(col)
                if not info:
                    continue
                if "NUMERIC" in str(info["type"]).upper():
                    continue
                conn.execute(text(
                    f'ALTER TABLE {table} ALTER COLUMN {col} '
                    f'TYPE NUMERIC(15,2) USING {col}::numeric(15,2)'
                ))
                changed.append(f"{table}.{col}")
    return changed


def seed_roles(db) -> int:
    from platform_models import Role
    n = 0
    labels = {
        "admin": "Administrator", "project_manager": "Project Manager",
        "site_engineer": "Site Engineer", "designer": "Designer", "finance": "Finance",
        "foreman": "Foreman", "client": "Client", "worker": "Worker",
        "engineer": "Engineer", "site_manager": "Site Manager",
        "safety_officer": "Safety Officer", "quality_engineer": "Quality Engineer",
        "accountant": "Accountant",
    }
    for role, caps in ROLE_ACCESS.items():
        existing = db.query(Role).filter_by(name=role).first()
        if existing:
            # keep capabilities in sync with the seed on each migration
            existing.capabilities = list(caps)
            existing.label = labels.get(role, role.title())
            existing.is_system = True
        else:
            db.add(Role(name=role, label=labels.get(role, role.title()),
                        capabilities=list(caps), is_system=True))
            n += 1
    db.commit()
    return n


def ensure_platform_admin(db) -> None:
    admin = db.query(models.User).filter_by(username=settings.DEFAULT_ADMIN_USERNAME).first()
    if admin:
        admin.is_platform_admin = True
    else:
        db.add(models.User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            full_name="Platform Administrator",
            role="admin",
            hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            is_active=True, is_platform_admin=True, is_demo=False,
            country=settings.DEFAULT_COUNTRY, language=settings.DEFAULT_LOCALE,
        ))
    db.commit()


def ensure_demo_tenant(db) -> dict:
    """Create the isolated demo company + demo user (empty until 'Load demo data')."""
    company = db.query(models.Company).filter_by(short_name="DEMO").first()
    if not company:
        company = models.Company(
            name="NagaForge Demo Workspace", short_name="DEMO",
            country="Canada", currency="CAD", timezone="America/Toronto",
            city="Toronto", plan="professional", is_active=True,
        )
        db.add(company); db.commit(); db.refresh(company)

    user = db.query(models.User).filter_by(username=settings.DEMO_USERNAME).first()
    if not user:
        user = models.User(
            company_id=company.id, username=settings.DEMO_USERNAME,
            full_name="Demo User", role="admin",
            hashed_password=hash_password(settings.DEMO_PASSWORD),
            is_active=True, is_platform_admin=False, is_demo=True,
            country="Canada", language="en",
        )
        db.add(user)
    else:
        # The demo account is a throwaway: keep it usable every boot by
        # re-syncing its password to DEMO_PASSWORD and (re)activating it.
        user.is_demo = True
        user.company_id = company.id
        user.is_platform_admin = False
        user.is_active = True
        user.role = user.role or "admin"
        user.hashed_password = hash_password(settings.DEMO_PASSWORD)
    db.commit()
    return {"company_id": company.id, "demo_user": settings.DEMO_USERNAME}


def run() -> dict:
    # 1. new tables
    Base.metadata.create_all(bind=engine)
    # 2. new columns on existing tables
    changed = add_tenant_columns()
    # 2b. money columns -> NUMERIC(15,2) on PostgreSQL
    changed += convert_money_columns_pg()
    # 3+4. seed
    db = SessionLocal()
    try:
        import i18n_store
        roles_added = seed_roles(db)
        i18n_counts = i18n_store.seed_platform_i18n(db)
        ensure_platform_admin(db)
        demo = ensure_demo_tenant(db)
    finally:
        db.close()
    # bust the RBAC cache so new roles are visible
    try:
        import policy
        policy.invalidate_cache()
    except Exception:
        pass
    return {"columns_added": changed, "roles_added": roles_added,
            "i18n": i18n_counts, "demo": demo}


if __name__ == "__main__":
    result = run()
    print("Migration complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    sys.exit(0)
