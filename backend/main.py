"""
NagaForge — Integrated Construction Management Platform
Phases 0-8: Foundation, ERP, Commercial, Planning, Site Ops, Quality, Safety, Engineering
Backend: FastAPI + SQLAlchemy + SQLite/PostgreSQL
"""

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date
import os

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

from database import engine, get_db, Base, SessionLocal
from config import settings
import models

# Routers — Phase 0-1
from routers import auth_router
from routers import company

# Routers — Phase 1-2 (ERP + Commercial)
from routers import projects, workers, finance, clients, documents, inventory
from routers import commercial
from routers import controls

# Routers — Phase 3 (Planning/Scheduling)
from routers import scheduling

# Routers — Phase 4 (Site Operations)
from routers import site_ops

# Routers — Phase 5 (Quality)
from routers import quality

# Routers — Phase 6 (Safety)
from routers import safety

# Routers — Phase 7-8 (Engineering)
from routers import structural
from routers import intl_structural
from routers import steel          # Phase 9
from routers import calculations   # Engineering calculation history
from routers import bim            # Phase 10
from routers import saas           # Phase 13
from routers import reports        # Phase 14 — PDF Reports
from routers import nbc_canada     # NBC Canada — Canadian structural code calculators
from routers import i18n_router     # DB-driven i18n + country code packs
from routers import demo_router     # Demo data load/reset (demo account only)
from routers import notifications   # Phase 3 — in-app notifications
from routers import library         # Phase 3 — section reference library

from auth import hash_password, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt

# Platform + tenancy layer
import platform_models                                 # noqa: F401 (registers tables)
import policy
from tenancy import install_tenant_isolation, set_tenant, reset_tenant, TenantContext

# Fail fast on insecure production config (no-op in DEBUG).
settings.validate()

# Attach row-level tenant isolation to the ORM before any query runs.
install_tenant_isolation()

# Create all tables + run idempotent platform migration/seed.
Base.metadata.create_all(bind=engine)
try:
    import migrate_platform
    migrate_platform.run()
except Exception as _mig_err:  # never let a migration hiccup hard-crash boot in dev
    import logging
    logging.getLogger("nagaforge").warning("platform migration skipped: %s", _mig_err)

app = FastAPI(
    title="NagaForge",
    description="Integrated Construction Management — Phases 0-8 (ERP, Commercial, Planning, Site Ops, QC, Safety, Structural)",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_PATHS = {
    "/",
    "/landing.html",
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/saas/onboard",
    "/saas/plans",
}
PUBLIC_PREFIXES = (
    "/uploads/",
    "/demo.html",
    "/demo/",
    "/walkthrough",
    "/linkedin",
    "/linkedin-demo",
    "/showcase",
    "/manifest",
    "/sw.js",
    "/favicon",
    "/i18n",          # translation bundles must load on the login screen
)
PROTECTED_API_PREFIXES = (
    "/dashboard",
    "/seed",
    "/company",
    "/projects",
    "/workers",
    "/finance",
    "/invoices",      # finance router mounts these at root (no /finance prefix)
    "/expenses",
    "/clients",
    "/documents",
    "/inventory",
    "/commercial",
    "/controls",
    "/scheduling",
    "/site-ops",
    "/site",
    "/siteops",
    "/quality",
    "/safety",
    "/structural",
    "/intl",
    "/steel",
    "/calculations",
    "/bim",
    "/reports",
    "/notifications",
    "/library",
    "/nbc",
    "/nbc-canada",
    "/auth/users",
    "/auth/me",
    "/auth/roles",
    "/saas",
    "/demo-data",
    "/docs",
    "/redoc",
    "/openapi.json",
)


@app.middleware("http")
async def require_live_token_for_app_apis(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS":
        return await call_next(request)
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    if path == "/app" or path == "/app/":
        if request.query_params.get("entry") != "landing":
            return RedirectResponse("/", status_code=302)
        return await call_next(request)
    if path == "/index.html":
        return RedirectResponse("/", status_code=302)
    if any(path.startswith(p) for p in PROTECTED_API_PREFIXES):
        auth_header = request.headers.get("authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            return JSONResponse({"detail": "Token expired or invalid"}, status_code=401)

        # ── Resolve the tenant context (from JWT claims, DB fallback) ──────────
        ctx, err = _resolve_tenant_context(payload)
        if err:
            return JSONResponse({"detail": err}, status_code=401)

        # ── Central RBAC: does this role have the capability for this route? ───
        cap = policy.required_capability(path)
        if not (ctx.is_platform_admin or ctx.role == "admin"):
            db = SessionLocal()
            try:
                if not policy.can_access(ctx.role, cap, db):
                    return JSONResponse(
                        {"detail": "Insufficient permissions for this module"},
                        status_code=403,
                    )
            finally:
                db.close()

        # ── Enforce tenant isolation for the whole request ────────────────────
        tok = set_tenant(ctx)
        try:
            return await call_next(request)
        finally:
            reset_tenant(tok)

    return await call_next(request)


def _resolve_tenant_context(payload: dict):
    """Build a TenantContext from JWT claims, falling back to a DB lookup for
    legacy tokens that predate the tenant claims."""
    username = payload.get("sub")
    if not username:
        return None, "Invalid token"
    role = payload.get("role")
    cid = payload.get("cid")
    is_demo = payload.get("demo")
    is_padmin = payload.get("padmin")
    uid = payload.get("uid")

    if cid is None or role is None:
        db = SessionLocal()
        try:
            user = (
                db.query(models.User)
                .filter(models.User.username == username,
                        models.User.is_active == True)  # noqa: E712
                .first()
            )
            if not user:
                return None, "User not found"
            role = user.role
            cid = user.company_id
            is_demo = bool(user.is_demo)
            is_padmin = bool(user.is_platform_admin)
            uid = user.id
        finally:
            db.close()

    return TenantContext(
        user_id=uid, username=username, company_id=cid, role=role,
        is_demo=bool(is_demo), is_platform_admin=bool(is_padmin),
    ), None

# Static files
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ── Register all routers ────────────────────────────────────────────────────

# Auth
app.include_router(auth_router.router)

# Platform: i18n bundles + demo data controls
app.include_router(i18n_router.router)
app.include_router(demo_router.router)
app.include_router(notifications.router)
app.include_router(library.router)

# Organization
app.include_router(company.router)

# Core ERP
app.include_router(projects.router)
app.include_router(workers.router)
app.include_router(finance.router)
app.include_router(clients.router)
app.include_router(documents.router)
app.include_router(inventory.router)

# Commercial
app.include_router(commercial.router)
app.include_router(controls.router)

# Planning & Scheduling
app.include_router(scheduling.router)

# Site Operations
app.include_router(site_ops.router)

# Quality Control
app.include_router(quality.router)

# Safety
app.include_router(safety.router)

# Engineering
app.include_router(structural.router)
app.include_router(intl_structural.router)
app.include_router(steel.router)       # Phase 9
app.include_router(calculations.router)
app.include_router(bim.router)         # Phase 10
app.include_router(saas.router)        # Phase 13
app.include_router(reports.router)     # Phase 14 — PDF Reports
app.include_router(nbc_canada.router)  # NBC Canada — Snow / Wind / Seismic / CSA codes


# ── Startup: seed default admin ─────────────────────────────────────────────

@app.on_event("startup")
def seed_admin():
    # ── Step 1: SQLite column migrations (safe ALTER TABLE ADD COLUMN) ────────
    try:
        import sqlite3 as _sq3
        _db_path = engine.url.database
        if _db_path and not os.path.isabs(_db_path):
            _db_path = os.path.abspath(_db_path)
        if os.path.exists(_db_path):
            _con = _sq3.connect(_db_path)
            _cur = _con.cursor()
            # companies table — add missing columns
            _cur.execute("PRAGMA table_info(companies)")
            _existing = {r[1] for r in _cur.fetchall()}
            _migrations = [
                ("companies", "gst_no",   "TEXT"),
                ("companies", "timezone", "TEXT DEFAULT 'Asia/Kolkata'"),
                ("companies", "city",     "TEXT"),
            ]
            for _tbl, _col, _typ in _migrations:
                if _col not in _existing:
                    _cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}")
                    print(f"✅ Migration: added {_tbl}.{_col}")
            _cur.execute("PRAGMA table_info(users)")
            _existing_users = {r[1] for r in _cur.fetchall()}
            _user_migrations = [
                ("users", "country",  "TEXT DEFAULT 'India'"),
                ("users", "language", "TEXT DEFAULT 'en'"),
            ]
            for _tbl, _col, _typ in _user_migrations:
                if _col not in _existing_users:
                    _cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_typ}")
                    print(f"✅ Migration: added {_tbl}.{_col}")
            _con.commit()
            _con.close()
    except Exception as _me:
        print(f"⚠️  Migration warning (non-fatal): {_me}")

    # ── Step 2: Seed default admin ────────────────────────────────────────────
    from sqlalchemy.orm import Session as S
    db: S = next(get_db())
    try:
        # Seed default company
        if not db.query(models.Company).first():
            company_obj = models.Company(
                name="NagaForge Demo Company",
                short_name="NGF",
                country="India",
                currency="INR",
                email="admin@nagaforge.in",
                plan="enterprise",
            )
            db.add(company_obj)
            db.flush()

        # Seed admin user
        if not db.query(models.User).filter(models.User.username == settings.DEFAULT_ADMIN_USERNAME).first():
            admin = models.User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                full_name="System Administrator",
                email="admin@nagaforge.in",
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                role="admin",
                country=company_obj.country if "company_obj" in locals() else "India",
                language="en",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin created — username: {settings.DEFAULT_ADMIN_USERNAME}  password: {settings.DEFAULT_ADMIN_PASSWORD}")
        else:
            print("✅ Admin exists")
    except Exception as e:
        print(f"⚠️  Startup seed error: {e}")
        db.rollback()
    finally:
        db.close()


# ── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/dashboard", tags=["Dashboard"])
def get_dashboard(db: Session = Depends(get_db)):
    total_projects  = db.query(models.Project).count()
    active_projects = db.query(models.Project).filter(models.Project.status == "active").count()
    total_workers   = db.query(models.Worker).count()
    active_workers  = db.query(models.Worker).filter(models.Worker.status == "active").count()
    total_clients   = db.query(models.Client).count()

    total_revenue = db.query(func.coalesce(func.sum(models.Invoice.total), 0)).filter(
        models.Invoice.status == "paid").scalar() or 0
    total_expenses = db.query(func.coalesce(func.sum(models.Expense.amount), 0)).scalar() or 0
    pending_invoices = db.query(func.coalesce(func.sum(models.Invoice.total), 0)).filter(
        models.Invoice.status.in_(["sent", "draft"])).scalar() or 0

    low_stock = db.query(models.InventoryItem).filter(
        models.InventoryItem.quantity <= models.InventoryItem.min_quantity).count()
    open_incidents = db.query(models.SafetyIncident).filter(
        models.SafetyIncident.resolved == False).count()
    open_ncrs = db.query(models.NCReport).filter(
        models.NCReport.status == "open").count()
    open_ptw = db.query(models.PermitToWork).filter(
        models.PermitToWork.status.in_(["pending", "approved", "active"])).count()

    # Projects by status
    def _ev(x):
        return x.value if hasattr(x, "value") else (x if x is None else str(x))
    status_counts = db.query(models.Project.status, func.count(models.Project.id)
                              ).group_by(models.Project.status).all()
    projects_by_status = {(_ev(s) or "unknown"): c for s, c in status_counts}

    # Monthly expenses (last 6 months)
    monthly = []
    for m in range(6, 0, -1):
        from dateutil.relativedelta import relativedelta
        target = date.today() - relativedelta(months=m - 1)
        total = db.query(func.coalesce(func.sum(models.Expense.amount), 0)).filter(
            extract("year", models.Expense.date) == target.year,
            extract("month", models.Expense.date) == target.month,
        ).scalar() or 0
        monthly.append({"month": target.strftime("%b %Y"), "amount": float(total)})

    # Top projects by budget
    top_projects = db.query(models.Project).order_by(models.Project.budget.desc()).limit(5).all()
    top_projects_data = [
        {"id": p.id, "name": p.name, "budget": p.budget, "spent": p.spent,
         "progress": p.progress, "status": _ev(p.status)}
        for p in top_projects
    ]

    # Recent tasks
    recent_tasks = db.query(models.Task).order_by(models.Task.created_at.desc()).limit(10).all()
    recent_tasks_data = [
        {"id": t.id, "title": t.title, "status": _ev(t.status),
         "priority": _ev(t.priority),
         "due_date": str(t.due_date) if t.due_date else None}
        for t in recent_tasks
    ]

    # Today's attendance
    today_workers = db.query(models.Attendance).filter(
        models.Attendance.date == date.today(),
        models.Attendance.is_present == True).count()

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_workers": total_workers,
        "active_workers": active_workers,
        "total_clients": total_clients,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "pending_invoices": float(pending_invoices),
        "low_stock_items": low_stock,
        "open_incidents": open_incidents,
        "open_ncrs": open_ncrs,
        "open_ptw": open_ptw,
        "today_workers_on_site": today_workers,
        "projects_by_status": projects_by_status,
        "monthly_expenses": monthly,
        "top_projects": top_projects_data,
        "recent_tasks": recent_tasks_data,
    }


# ── Frontend ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Frontend"])
def serve_landing():
    """Landing / marketing page — served at root URL"""
    lp = os.path.join(FRONTEND_DIR, "landing.html")
    if os.path.exists(lp):
        return FileResponse(lp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/app", tags=["Frontend"])
@app.get("/app/", tags=["Frontend"])
def serve_app():
    """Main application"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/index.html", tags=["Frontend"])
def serve_frontend_explicit():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/landing.html", tags=["Frontend"])
def serve_landing_explicit():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))

@app.get("/demo", tags=["Frontend"])
@app.get("/demo.html", tags=["Frontend"])
def serve_demo():
    """Interactive product demo page — no login required"""
    dp = os.path.join(FRONTEND_DIR, "demo.html")
    if os.path.exists(dp):
        return FileResponse(dp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/walkthrough", tags=["Frontend"])
@app.get("/walkthrough.html", tags=["Frontend"])
def serve_walkthrough():
    """Auto-playing product walkthrough — no login required"""
    wp = os.path.join(FRONTEND_DIR, "walkthrough.html")
    if os.path.exists(wp):
        return FileResponse(wp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/linkedin", tags=["Frontend"])
@app.get("/linkedin-demo", tags=["Frontend"])
@app.get("/showcase", tags=["Frontend"])
def serve_linkedin_demo():
    """Cinematic product showcase — shareable / screen-recordable for LinkedIn"""
    lp = os.path.join(FRONTEND_DIR, "linkedin-demo.html")
    if os.path.exists(lp):
        return FileResponse(lp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/api/info", tags=["System"])
def api_info():
    return {
        "app": "NagaForge",
        "version": settings.VERSION,
        "docs": "/docs",
        "modules": [
            "Auth (JWT + RBAC)", "Company/Branch/Department",
            "Projects/Tasks/Workers", "Clients/Contractors/Consultants",
            "Finance (Invoices/Expenses)", "Documents (versioned)",
            "Inventory", "BOQ/Procurement/Vendors/Contracts/Budget",
            "Scheduling (CPM/EVM/Gantt)", "Site Operations (Diary/Equipment/Fuel)",
            "Quality Control (Cube Tests/NCR/Punch List)",
            "Safety (PTW/Risk/Toolbox Talks)",
            "Structural Engineering (IS/NBCC/ASCE/Eurocode)",
        ]
    }


# ── Demo seed ─────────────────────────────────────────────────────────────────

@app.post("/seed", tags=["Dev"])
def seed_demo_data(db: Session = Depends(get_db)):
    """Populate with demo data for testing."""
    if db.query(models.Client).count() > 0:
        return {"message": "Already seeded"}

    clients_data = [
        models.Client(name="Ravi Sharma", company="Sharma Realty Pvt Ltd",
                      email="ravi@sharmagroup.com", phone="9876543210", city="Mumbai"),
        models.Client(name="Anita Patel", company="GreenBuild Developers",
                      email="anita@greenbuild.in", phone="9123456789", city="Ahmedabad"),
        models.Client(name="Vikram Singh", company="Metro Infra Corp",
                      email="vikram@metroinfra.com", phone="9988776655", city="Delhi"),
    ]
    db.add_all(clients_data); db.flush()

    workers_data = [
        models.Worker(first_name="Arjun", last_name="Nair", email="arjun@nagaforge.in",
                      role="architect", daily_rate=3500, skills="AutoCAD,Revit,SketchUp", status="active"),
        models.Worker(first_name="Priya", last_name="Menon", email="priya@nagaforge.in",
                      role="designer", daily_rate=2800, skills="3ds Max,V-Ray", status="active"),
        models.Worker(first_name="Rajesh", last_name="Kumar", email="rajesh@nagaforge.in",
                      role="site_manager", daily_rate=2500, status="active"),
        models.Worker(first_name="Sunita", last_name="Devi", email="sunita@nagaforge.in",
                      role="engineer", daily_rate=3000, status="active"),
        models.Worker(first_name="Mohammed", last_name="Ali", email="mali@nagaforge.in",
                      role="foreman", daily_rate=1800, status="active"),
        models.Worker(first_name="Lakshmi", last_name="Iyer", email="lakshmi@nagaforge.in",
                      role="safety_officer", daily_rate=2200, status="active"),
        models.Worker(first_name="Ramesh", last_name="Yadav", email="ramesh@nagaforge.in",
                      role="mason", daily_rate=900, status="active"),
    ]
    db.add_all(workers_data); db.flush()

    from datetime import timedelta
    projects_data = [
        models.Project(name="Skyline Residential Tower - Phase 1", project_code="PRJ-001",
            description="25-floor luxury residential tower in Mumbai suburbs",
            client_id=clients_data[0].id, status="active",
            start_date=date(2025, 1, 15), end_date=date(2026, 12, 31),
            budget=45000000, spent=12500000, location="Thane, Mumbai",
            project_type="residential", progress=28),
        models.Project(name="GreenBuild Commercial Complex", project_code="PRJ-002",
            description="Eco-friendly 6-floor commercial building",
            client_id=clients_data[1].id, status="active",
            start_date=date(2025, 6, 1), end_date=date(2026, 8, 31),
            budget=18000000, spent=3200000, location="Ahmedabad",
            project_type="commercial", progress=18),
        models.Project(name="Metro Station Renovation", project_code="PRJ-003",
            client_id=clients_data[2].id, status="planning",
            start_date=date(2026, 2, 1), end_date=date(2026, 10, 31),
            budget=9500000, spent=0, location="Delhi NCR",
            project_type="infrastructure", progress=0),
    ]
    db.add_all(projects_data); db.flush()

    # Tasks
    db.add_all([
        models.Task(project_id=projects_data[0].id, assignee_id=workers_data[0].id,
                    title="Finalize structural drawings", status="in_progress",
                    priority="high", due_date=date.today() + timedelta(days=7)),
        models.Task(project_id=projects_data[0].id, assignee_id=workers_data[2].id,
                    title="Concrete pouring - 8th floor", status="todo",
                    priority="urgent", due_date=date.today() + timedelta(days=3)),
        models.Task(project_id=projects_data[1].id, assignee_id=workers_data[1].id,
                    title="Interior design mockups", status="in_progress",
                    priority="medium", due_date=date.today() + timedelta(days=10)),
    ])

    # Expenses
    db.add_all([
        models.Expense(project_id=projects_data[0].id, category="material",
                       description="Cement - 500 bags", amount=350000,
                       date=date(2026, 1, 10), vendor="UltraTech Cement"),
        models.Expense(project_id=projects_data[0].id, category="labor",
                       description="Labour wages - Jan", amount=1200000,
                       date=date(2026, 1, 31), vendor="Internal"),
        models.Expense(project_id=projects_data[0].id, category="equipment",
                       description="Tower crane rental", amount=450000,
                       date=date(2026, 2, 5), vendor="Maxcrane Ltd"),
    ])

    # Invoices
    db.add_all([
        models.Invoice(invoice_no="INV-2026-0001", client_id=clients_data[0].id,
                       project_id=projects_data[0].id, status="paid",
                       issue_date=date(2026, 1, 1), due_date=date(2026, 1, 31),
                       subtotal=5000000, tax_rate=18, tax_amount=900000,
                       total=5900000, paid_amount=5900000),
        models.Invoice(invoice_no="INV-2026-0002", client_id=clients_data[1].id,
                       project_id=projects_data[1].id, status="sent",
                       issue_date=date(2026, 3, 1), due_date=date(2026, 3, 31),
                       subtotal=2000000, tax_rate=18, tax_amount=360000,
                       total=2360000, paid_amount=0),
    ])

    # Inventory
    db.add_all([
        models.InventoryItem(name="Portland Cement", category="material",
                             sku="CEM-001", unit="bags", quantity=250,
                             min_quantity=100, unit_cost=380, supplier="UltraTech"),
        models.InventoryItem(name="TMT Steel Bars 12mm", category="material",
                             sku="STL-012", unit="kg", quantity=8500,
                             min_quantity=2000, unit_cost=65, supplier="TATA Steel"),
        models.InventoryItem(name="Safety Helmets", category="tool",
                             sku="SAF-001", unit="pcs", quantity=45,
                             min_quantity=20, unit_cost=450, supplier="Karam"),
        models.InventoryItem(name="Bricks (Red)", category="material",
                             sku="BRK-001", unit="pcs", quantity=5000,
                             min_quantity=10000, unit_cost=8, supplier="Local"),
    ])

    # Safety incident
    db.add(models.SafetyIncident(
        project_id=projects_data[0].id,
        title="Worker minor cut — hand injury",
        severity="low", incident_date=date(2026, 2, 14),
        location="Floor 6", injuries=True, resolved=True,
        reported_by="Rajesh Kumar", corrective_action="First aid provided. Safety gloves mandatory.",
        incident_type="incident"
    ))

    # Safety inspection
    db.add(models.SafetyInspection(
        project_id=projects_data[0].id,
        title="Monthly safety inspection - Mar",
        inspector="Lakshmi Iyer", inspection_date=date(2026, 3, 1),
        passed=True, findings="PPE compliance 92%. Minor housekeeping issues.",
        next_inspection=date(2026, 4, 1)
    ))

    # Documents
    db.add_all([
        models.Document(project_id=projects_data[0].id,
                        title="Structural Drawing - Tower A", doc_type="blueprint",
                        file_name="structural_tower_a_v2.pdf", version="2.0",
                        uploaded_by="Arjun Nair"),
        models.Document(project_id=projects_data[0].id,
                        title="Building Permit - Mumbai MCGM", doc_type="permit",
                        file_name="permit_mcgm_2025.pdf", version="1.0",
                        uploaded_by="Admin"),
    ])

    # Vendor
    db.add(models.Vendor(
        name="UltraTech Cement Ltd", category="material",
        contact_person="Sales Manager", email="sales@ultratech.in",
        phone="1800-209-9090", city="Mumbai", country="India",
        tax_id="27AAACU0792H1ZY", approved=True
    ))

    # Site diary
    db.add(models.SiteDiary(
        project_id=projects_data[0].id,
        report_date=date(2026, 3, 20),
        prepared_by="Rajesh Kumar",
        weather_morning="sunny", weather_afternoon="partly_cloudy",
        temperature_c=32.0, humidity_pct=65,
        total_workers=45, total_engineers=5,
        work_done="Concrete pouring completed on 8th floor slab. Rebar fixing in progress for 9th floor columns.",
        material_used="40 m3 RMC M25, 2.5 MT TMT bars 16mm",
        equipment_used="Tower crane, concrete pump, 3 vibrators",
        safety_notes="All workers wearing PPE. Toolbox talk conducted at 8:00 AM.",
    ))

    db.commit()
    return {"message": "Demo data seeded", "counts": {
        "clients": 3, "workers": 7, "projects": 3, "invoices": 2
    }}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
