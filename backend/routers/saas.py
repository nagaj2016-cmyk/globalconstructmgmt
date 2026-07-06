"""
Phase 13 — Multi-tenant SaaS Router
Subscription plans, tenant management, usage tracking, white-label config,
onboarding flow, tenant admin dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from database import get_db
from auth import get_current_user
from models import (
    SubscriptionPlan, TenantSubscription, TenantUsage, TenantConfig,
    Company, User, Project, Worker, Client, Task, Expense, Invoice,
    SafetyIncident, InventoryItem,
    BIMModel, BIMElement,
    MaterialTest, QCInspection, QCChecklistItem, NCReport,
    SiteDiary, Equipment, FuelLog, MaterialConsumption,
    ToolboxTalk, PermitToWork, RiskAssessment, SafetyInspection,
    Document, Attendance, ChangeOrder, RFI, DrawingRegister,
)
import random
from datetime import date, timedelta

router = APIRouter(prefix="/saas", tags=["SaaS / Multi-tenant"])


def require_saas_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user

# ── Default plans ─────────────────────────────────────────────────────────────
DEFAULT_PLANS = [
    {
        "name": "free",
        "display_name": "Free",
        "price_monthly": 0.0,
        "price_annual": 0.0,
        "max_users": 3,
        "max_projects": 2,
        "max_storage_gb": 0.5,
        "features": ["projects", "workers", "documents"],
        "is_active": True,
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "price_monthly": 2.5,
        "price_annual": 30.0,
        "max_users": 10,
        "max_projects": 10,
        "max_storage_gb": 5.0,
        "features": [
            "projects", "workers", "documents", "scheduling", "quality",
            "safety", "commercial", "site_ops",
        ],
        "is_active": True,
    },
    {
        "name": "professional",
        "display_name": "Professional",
        "price_monthly": 99.0,
        "price_annual": 990.0,
        "max_users": 50,
        "max_projects": 50,
        "max_storage_gb": 50.0,
        "features": [
            "projects", "workers", "documents", "scheduling", "quality",
            "safety", "commercial", "site_ops", "structural_is", "structural_intl",
            "steel_design", "bim", "analytics", "api_access",
        ],
        "is_active": True,
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise",
        "price_monthly": 299.0,
        "price_annual": 2990.0,
        "max_users": -1,          # unlimited
        "max_projects": -1,
        "max_storage_gb": 1000.0,
        "features": [
            "projects", "workers", "documents", "scheduling", "quality",
            "safety", "commercial", "site_ops", "structural_is", "structural_intl",
            "steel_design", "bim", "analytics", "api_access",
            "white_label", "sso", "dedicated_support", "custom_integrations",
        ],
        "is_active": True,
    },
]


def _seed_plans(db: Session):
    """Create or refresh default launch plans."""
    for p in DEFAULT_PLANS:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == p["name"]).first()
        if existing:
            for k, v in p.items():
                setattr(existing, k, v)
        else:
            db.add(SubscriptionPlan(**p))
    db.commit()


# ── Schemas ────────────────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    name: str
    display_name: str
    price_monthly: float = 0.0
    price_annual: float = 0.0
    max_users: int = 5
    max_projects: int = 5
    max_storage_gb: float = 1.0
    features: List[str] = []

class TenantOnboardReq(BaseModel):
    company_name: str
    admin_email: str
    admin_name: str
    admin_password: str
    admin_username: Optional[str] = None
    plan_name: str = "free"
    country: str = "India"
    country_code: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None

class SubscribeReq(BaseModel):
    company_id: int
    plan_name: str
    billing_cycle: str = "monthly"   # monthly | annual

class TenantConfigUpdate(BaseModel):
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    logo_url: Optional[str] = None
    app_name: Optional[str] = None
    feature_flags: Optional[Dict[str, Any]] = None
    custom_domain: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    currency: Optional[str] = None


def _plan_to_dict(p: SubscriptionPlan) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "display_name": p.display_name,
        "price_monthly": p.price_monthly,
        "price_annual": p.price_annual,
        "max_users": p.max_users,
        "max_projects": p.max_projects,
        "max_storage_gb": p.max_storage_gb,
        "features": p.features or [],
        "is_active": p.is_active,
    }


def _sub_to_dict(s: TenantSubscription) -> dict:
    return {
        "id": s.id,
        "company_id": s.company_id,
        "plan": _plan_to_dict(s.plan) if s.plan else None,
        "status": s.status,
        "trial_ends": str(s.trial_ends) if s.trial_ends else None,
        "current_period_start": str(s.current_period_start),
        "current_period_end": str(s.current_period_end) if s.current_period_end else None,
        "stripe_customer_id": s.stripe_customer_id,
    }


COUNTRY_DEMO = {
    "India": {
        "currency": "INR", "timezone": "Asia/Kolkata", "city": "Mumbai", "phone": "+91",
        "client_company": "Demo Holdings Pvt Ltd",
        "project1": "Demo Residential Tower",
        "project1_desc": "G+7 RCC framed residential tower. IS 456 / IS 13920 seismic design.",
        "project2": "Demo Commercial Complex",
        "project2_desc": "G+3 steel-framed commercial complex. IS 800:2007 design.",
        "design_code": "IS", "budget1": 45_000_000, "spent1": 12_000_000, "budget2": 28_000_000,
        "workers": [("Rajesh","Kumar"),("Priya","Sharma"),("Mohan","Das"),("Sunita","Patel"),("Vikram","Singh"),("Anita","Iyer")],
        "materials": [("Portland Cement 53 Grade", 380),("TMT Bars 12mm Fe415",65),("20mm Aggregates",1400),("Sand - Zone II",1200),("Plywood 12mm shuttering",850),("Safety Helmets",450)],
    },
    "Canada": {
        "currency": "CAD", "timezone": "America/Toronto", "city": "Toronto", "phone": "+1",
        "client_company": "Demo Developments Canada Ltd",
        "project1": "Demo Mid-Rise Concrete Residence",
        "project1_desc": "8-storey reinforced concrete residential building. NBC Canada / CSA A23.3 workflow.",
        "project2": "Demo Steel Office Building",
        "project2_desc": "Low-rise steel office building. CSA S16 and NBC wind/snow/seismic checks.",
        "design_code": "NBCC", "budget1": 8_200_000, "spent1": 2_150_000, "budget2": 5_400_000,
        "workers": [("Liam","Martin"),("Olivia","Chen"),("Noah","Singh"),("Ava","Brown"),("Ethan","Wilson"),("Mia","Patel")],
        "materials": [("CSA Type GU Cement", 12),("Rebar 15M Grade 400W",1.15),("20mm Crushed Aggregate",55),("Concrete Sand",42),("Formwork Plywood",58),("Hard Hats",22)],
    },
    "United States": {
        "currency": "USD", "timezone": "America/New_York", "city": "New York", "phone": "+1",
        "client_company": "Demo Properties LLC",
        "project1": "Demo Concrete Apartment Building",
        "project1_desc": "Multi-family concrete building. ASCE 7 / ACI 318 workflow.",
        "project2": "Demo Structural Steel Retail Shell",
        "project2_desc": "Steel retail shell. AISC 360 and ASCE 7 load checks.",
        "design_code": "ASCE", "budget1": 6_500_000, "spent1": 1_700_000, "budget2": 4_200_000,
        "workers": [("James","Miller"),("Emma","Davis"),("Lucas","Garcia"),("Sophia","Johnson"),("Mason","Lee"),("Isabella","Clark")],
        "materials": [("Portland Cement Type I/II", 14),("ASTM A615 Rebar #5",1.05),("3/4 in Aggregate",48),("Concrete Sand",38),("Form Plywood",52),("Hard Hats",18)],
    },
    "Europe": {
        "currency": "EUR", "timezone": "Europe/Berlin", "city": "Berlin", "phone": "+49",
        "client_company": "Demo Euro Developments GmbH",
        "project1": "Demo Eurocode Concrete Apartments",
        "project1_desc": "Residential concrete frame using Eurocode 2 and National Annex assumptions.",
        "project2": "Demo Eurocode Steel Hall",
        "project2_desc": "Steel hall workflow using Eurocode 3 and EN 1991 actions.",
        "design_code": "EC", "budget1": 5_900_000, "spent1": 1_450_000, "budget2": 3_800_000,
        "workers": [("Jonas","Weber"),("Anna","Schmidt"),("Luca","Meyer"),("Sofia","Fischer"),("Leon","Wagner"),("Mila","Hoffmann")],
        "materials": [("CEM II Cement", 11),("B500B Reinforcement",1.0),("20mm Aggregate",46),("Concrete Sand",36),("Formwork Panels",50),("Safety Helmets",20)],
    },
}


def _country_demo(country: str) -> dict:
    aliases = {
        "Australia": ("AUD", "Australia/Sydney", "Sydney", "+61", "AS / NZS"),
        "United Arab Emirates": ("AED", "Asia/Dubai", "Dubai", "+971", "UAE / IBC"),
        "Saudi Arabia": ("SAR", "Asia/Riyadh", "Riyadh", "+966", "SBC"),
        "United Kingdom": ("GBP", "Europe/London", "London", "+44", "UK Eurocode"),
        "Singapore": ("SGD", "Asia/Singapore", "Singapore", "+65", "Singapore Eurocode"),
    }
    if country in COUNTRY_DEMO:
        return COUNTRY_DEMO[country]
    if country in aliases:
        currency, timezone, city, phone, code = aliases[country]
        return {
            "currency": currency, "timezone": timezone, "city": city, "phone": phone,
            "client_company": f"Demo Developments {country} Ltd",
            "project1": f"Demo {country} Concrete Residence",
            "project1_desc": f"Concrete residential workflow using {code} references.",
            "project2": f"Demo {country} Steel Commercial Building",
            "project2_desc": f"Steel commercial workflow using {code} references.",
            "design_code": code, "budget1": 5_500_000, "spent1": 1_250_000, "budget2": 3_600_000,
            "workers": [("Alex","Morgan"),("Sam","Taylor"),("Chris","Lee"),("Maya","Khan"),("Ryan","White"),("Nora","Ali")],
            "materials": [("General Purpose Cement", 12),("Reinforcing Bar",1.05),("20mm Aggregate",48),("Concrete Sand",38),("Formwork Panel",52),("Safety Helmets",18)],
        }
    return COUNTRY_DEMO["India"]


# ── Plans ──────────────────────────────────────────────────────────────────────

@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """All available subscription plans."""
    _seed_plans(db)
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    return [_plan_to_dict(p) for p in plans]


@router.post("/plans")
def create_plan(req: PlanCreate, db: Session = Depends(get_db)):
    if db.query(SubscriptionPlan).filter(SubscriptionPlan.name == req.name).first():
        raise HTTPException(400, f"Plan '{req.name}' already exists")
    p = SubscriptionPlan(**req.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return _plan_to_dict(p)


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, req: PlanCreate, db: Session = Depends(get_db)):
    p = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not p:
        raise HTTPException(404, "Plan not found")
    for k, v in req.model_dump().items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return _plan_to_dict(p)


# ── Tenant Onboarding ──────────────────────────────────────────────────────────

@router.post("/onboard")
def onboard_tenant(req: TenantOnboardReq, db: Session = Depends(get_db)):
    """
    One-shot tenant onboarding:
    1. Create Company
    2. Create admin User
    3. Assign subscription plan
    4. Create TenantConfig with defaults
    Returns company_id + auth hint.
    """
    import bcrypt

    _seed_plans(db)
    demo = _country_demo(req.country)
    currency = req.currency or demo["currency"]
    timezone = req.timezone or demo["timezone"]

    # Validate plan
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == req.plan_name).first()
    if not plan:
        raise HTTPException(400, f"Plan '{req.plan_name}' not found")

    admin_username = (req.admin_username or req.admin_email.split("@")[0]).strip()

    # Check duplicate account
    if db.query(User).filter(User.email == req.admin_email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(User).filter(User.username == admin_username).first():
        raise HTTPException(400, "Username already registered")

    # Create Company
    company = Company(
        name=req.company_name,
        email=req.admin_email,
        country=req.country,
        currency=currency,
        timezone=timezone,
        city=demo["city"],
        is_active=True,
        plan=req.plan_name,
    )
    db.add(company); db.flush()

    # Create admin User
    pwd_hash = bcrypt.hashpw(req.admin_password.encode(), bcrypt.gensalt()).decode()
    user = User(
        username=admin_username,
        email=req.admin_email,
        full_name=req.admin_name,
        hashed_password=pwd_hash,
        role="admin",
        company_id=company.id,
        country=req.country,
        language="en",
        is_active=True,
    )
    db.add(user); db.flush()

    # Create subscription (30-day trial)
    trial_end = datetime.utcnow() + timedelta(days=30)
    sub = TenantSubscription(
        company_id=company.id,
        plan_id=plan.id,
        status="trial",
        trial_ends=trial_end,
        current_period_start=datetime.utcnow(),
        current_period_end=trial_end,
    )
    db.add(sub)

    # Create TenantConfig
    cfg = TenantConfig(
        company_id=company.id,
        app_name=f"NagaForge — {req.company_name}",
        timezone=timezone,
        currency=currency,
    )
    db.add(cfg)
    db.flush()

    db.commit()

    return {
        "message": "Tenant onboarded successfully",
        "company_id": company.id,
        "admin_username": user.username,
        "plan": plan.name,
        "trial_ends": str(trial_end.date()),
        "login_hint": f"Username: {user.username} | Password: (as provided)",
        "demo_data": "Not loaded. The user can click Load Demo Data after login.",
    }


@router.post("/demo-data")
def load_demo_data_for_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Seed a demo workspace based on the logged-in user's country profile."""
    country = current_user.country or (current_user.company.country if current_user.company else "India")
    demo = _country_demo(country)
    currency = demo["currency"]
    timezone = demo["timezone"]

    company = current_user.company
    if not company:
        company = db.query(Company).filter(Company.email == current_user.email).first()
    if not company:
        company = Company(
            name=f"{current_user.full_name} Workspace",
            short_name=(current_user.username[:4] or "DEMO").upper(),
            email=current_user.email,
            country=country,
            currency=currency,
            timezone=timezone,
            city=demo["city"],
            plan="free",
            is_active=True,
        )
        db.add(company)
        db.flush()
    else:
        if not company.country:
            company.country = country
        if not company.currency:
            company.currency = currency
        if not company.timezone:
            company.timezone = timezone
        if not company.city:
            company.city = demo["city"]

    if not current_user.company_id:
        current_user.company_id = company.id
    if not current_user.country:
        current_user.country = country
    db.flush()

    short = (company.short_name or company.name[:4].upper()).lower()
    tenant_code = f"{short.upper()}{company.id or 'X'}"
    project_code = f"{tenant_code}-PRJ-001"
    existing = db.query(Project).filter(Project.project_code == project_code).first()
    if existing:
        db.commit()
        return {
            "message": f"{country} demo data is already loaded for this workspace.",
            "country": country,
            "currency": company.currency or currency,
            "project_id": existing.id,
            "already_loaded": True,
        }

    _seed_demo_data(db, company, company.name, company.currency or currency)
    db.commit()
    return {
        "message": f"{country} demo data loaded.",
        "country": country,
        "currency": company.currency or currency,
        "already_loaded": False,
    }


# ── Demo Data Seeder ──────────────────────────────────────────────────────────

def _seed_demo_data(db: Session, company: Company, company_name: str, currency: str = "INR"):
    """
    Auto-populate a new tenant's workspace with full demo data covering all modules:
     - 6 role-based team members | 6 workers | 1 client | 2 projects
     - Tasks, Expenses, Invoice, Inventory
     - BIM model with elements (columns, slabs, beams, walls)
     - QC: MaterialTest, QCInspection with checklist, NCReport
     - Site Ops: SiteDiary, Equipment, FuelLog, MaterialConsumption
     - Safety: SafetyIncident, ToolboxTalk, PermitToWork, RiskAssessment, SafetyInspection
     - Documents (drawings, reports)
     - Attendance records
    """
    import bcrypt
    demo = _country_demo(company.country or "India")
    currency = currency or demo["currency"]
    short = (company.short_name or company_name[:4].upper()).lower()
    tenant_suffix = company.id or "X"
    tenant_slug = f"{short}{tenant_suffix}"
    S = tenant_slug.upper()
    country = company.country or "India"
    design_code = demo["design_code"]

    # ── ROLE-BASED USERS ────────────────────────────────────────────────────
    ROLES = [
        ("pm",         "Project Manager",    "project_manager",
         "Manages project scope, schedule, budget and stakeholder communication."),
        ("struct_eng", "Structural Engineer","engineer",
         f"Performs {design_code} structural design calculations and reviews drawings."),
        ("site_mgr",   "Site Manager",       "site_manager",
         "Oversees daily site operations, attendance, site diary and progress."),
        ("safety",     "Safety Officer",     "safety_officer",
         "Manages HSE compliance, toolbox talks, incident reporting and audits."),
        ("qc",         "QC Engineer",        "quality_engineer",
         "Conducts material tests, approvals, NCR management and local code compliance."),
        ("finance",    "Finance Manager",    "accountant",
         "Handles invoicing, BOQ billing, expense tracking and cash flow reporting."),
    ]
    team = []
    for suffix, full_name, role, _ in ROLES:
        uname = f"{tenant_slug}_{suffix}"
        existing = db.query(User).filter(User.username == uname).first()
        if existing:
            team.append(existing); continue
        pwd_hash = bcrypt.hashpw(b"Demo@123", bcrypt.gensalt()).decode()
        u = User(username=uname, full_name=f"{full_name} ({company_name[:20]})",
                 email=f"{suffix}@{tenant_slug}.nagaforge.demo",
                 hashed_password=pwd_hash, role=role,
                 company_id=company.id, country=country, language="en", is_active=True)
        db.add(u); team.append(u)
    db.flush()

    # ── WORKERS ──────────────────────────────────────────────────────────────
    base_rates = [2800, 3200, 1800, 2200, 3500, 2600] if currency == "INR" else [260, 320, 210, 240, 360, 280]
    worker_roles = ["engineer", "architect", "foreman", "safety_officer", "site_manager", "engineer"]
    WORKER_DATA = [(fn, ln, worker_roles[i], base_rates[i]) for i, (fn, ln) in enumerate(demo["workers"])]
    workers = []
    for i, (fn, ln, role, rate) in enumerate(WORKER_DATA):
        em = f"{fn.lower()}.{ln.lower()}.{tenant_slug}{i}@demo.work"
        emp_id = f"{S}-W{i+1:03d}"
        exists = (
            db.query(Worker).filter(Worker.email == em).first()
            or db.query(Worker).filter(Worker.employee_id == emp_id).first()
        )
        if exists:
            workers.append(exists); continue
        w = Worker(first_name=fn, last_name=ln, employee_id=emp_id, email=em,
                   phone=f"{demo['phone']} {9000000000 + i}", role=role, status="active",
                   daily_rate=rate,
                   hire_date=date.today() - timedelta(days=random.randint(60, 500)))
        db.add(w); workers.append(w)
    db.flush()

    # ── CLIENT ───────────────────────────────────────────────────────────────
    cl_email = f"client@{tenant_slug}.demo"
    client = db.query(Client).filter(Client.email == cl_email).first()
    if not client:
        client = Client(name=f"{company_name[:25]} — Demo Client",
                        company=demo["client_company"], email=cl_email,
                        phone=f"{demo['phone']} 98765 43210",
                        city=company.city or demo["city"],
                        country=country)
        db.add(client); db.flush()

    # ── PROJECTS ─────────────────────────────────────────────────────────────
    today = date.today()
    pc1, pc2 = f"{S}-PRJ-001", f"{S}-PRJ-002"

    p1 = db.query(Project).filter(Project.project_code == pc1).first()
    if not p1:
        p1 = Project(name=f"{demo['project1']} — {company_name[:20]}",
                     project_code=pc1,
                     description=demo["project1_desc"],
                     client_id=client.id, status="active",
                     start_date=today - timedelta(days=90),
                     end_date=today + timedelta(days=365),
                     budget=demo["budget1"], spent=demo["spent1"],
                     location=company.city or demo["city"],
                     country=country, design_code=design_code,
                     project_type="residential", progress=27)
        db.add(p1)

    p2 = db.query(Project).filter(Project.project_code == pc2).first()
    if not p2:
        p2 = Project(name=f"{demo['project2']} — {company_name[:20]}",
                     project_code=pc2,
                     description=demo["project2_desc"],
                     client_id=client.id, status="planning",
                     start_date=today + timedelta(days=30),
                     end_date=today + timedelta(days=548),
                     budget=demo["budget2"], spent=0,
                     location=company.city or demo["city"],
                     country=country, design_code=design_code,
                     project_type="commercial", progress=0)
        db.add(p2)
    db.flush()

    # ── PROJECT CONTROLS ───────────────────────────────────────────────────
    for idx, (subject, question, discipline, priority, status) in enumerate([
        ("Confirm slab opening dimensions", "Please confirm final dimensions for the services opening near Grid B-4.", "structural", "high", "open"),
        ("Clarify facade support detail", "Client requires confirmation of the approved bracket detail and embed plate layout.", "architectural", "medium", "answered"),
    ], start=1):
        rfi_no = f"RFI-{S}-{idx:03d}"
        if p1 and not db.query(RFI).filter(RFI.rfi_number == rfi_no).first():
            db.add(RFI(
                project_id=p1.id,
                rfi_number=rfi_no,
                subject=subject,
                question=question,
                answer="Use latest approved drawing revision." if status == "answered" else None,
                discipline=discipline,
                priority=priority,
                status=status,
                raised_by="Project Manager",
                assigned_to="Structural Engineer",
                due_date=today + timedelta(days=7 + idx),
                answered_by="Consultant" if status == "answered" else None,
                answered_at=datetime.utcnow() if status == "answered" else None,
            ))

    for idx, (title, reason, status, factor, days) in enumerate([
        ("Client-requested lobby finish upgrade", "client_instruction", "submitted", 0.006, 5),
        ("Additional temporary works for excavation", "site_condition", "approved", 0.004, 3),
    ], start=1):
        co_no = f"CO-{S}-{idx:03d}"
        if p1 and not db.query(ChangeOrder).filter(ChangeOrder.co_number == co_no).first():
            cost_impact = round(float(demo["budget1"]) * factor, 2)
            db.add(ChangeOrder(
                project_id=p1.id,
                co_number=co_no,
                title=title,
                description=f"Demo change order in {currency}.",
                reason=reason,
                status=status,
                cost_impact=cost_impact,
                time_impact_days=days,
                requested_by="Client Representative",
                submitted_date=today - timedelta(days=idx * 3),
                approved_by="Project Director" if status == "approved" else None,
                approved_date=today - timedelta(days=1) if status == "approved" else None,
            ))

    for idx, (drawing_no, title, discipline, revision, status) in enumerate([
        (f"STR-{S}-001", "Foundation layout", "structural", "1", "approved"),
        (f"ARC-{S}-101", "Ground floor plan", "architectural", "2", "submitted"),
        (f"MEP-{S}-201", "Services coordination plan", "MEP", "0", "draft"),
    ], start=1):
        if p1 and not db.query(DrawingRegister).filter(DrawingRegister.drawing_no == drawing_no).first():
            db.add(DrawingRegister(
                project_id=p1.id,
                drawing_no=drawing_no,
                title=title,
                discipline=discipline,
                revision=revision,
                status=status,
                issue_date=today - timedelta(days=idx * 4),
                received_date=today - timedelta(days=idx * 4 - 1),
                prepared_by="Design Team",
                checked_by="Lead Engineer",
                approved_by="Consultant" if status == "approved" else None,
                file_name=f"{drawing_no}-Rev{revision}.pdf",
            ))
    db.flush()

    # ── TASKS ────────────────────────────────────────────────────────────────
    w = workers  # alias
    TASKS = [
        (p1,"Structural drawings — Foundation",     "in_progress","high",   w[0] if w else None),
        (p1,f"{design_code} beam design — Typical floor", "in_progress","high",   w[0] if w else None),
        (p1,"RCC Column design — Ground floor",     "todo",       "high",   w[0] if w else None),
        (p1,"Concrete cube test — C30 mix",         "done",       "medium", w[3] if len(w)>3 else None),
        (p1,"Safety audit — Scaffolding",           "in_progress","urgent", w[3] if len(w)>3 else None),
        (p1,"Site diary — Week 12",                 "todo",       "medium", w[4] if len(w)>4 else None),
        (p1,f"Procurement — {demo['materials'][1][0]}", "done",       "high",   w[2] if len(w)>2 else None),
        (p2,"Soil investigation report review",     "todo",       "high",   w[1] if len(w)>1 else None),
        (p2,f"{design_code} steel beam selection",  "todo",       "medium", w[0] if w else None),
        (p2,"BOQ preparation — steel structure",    "todo",       "medium", w[5] if len(w)>5 else None),
    ]
    for proj, title, status, priority, assignee in TASKS:
        if proj:
            db.add(Task(project_id=proj.id,
                        assignee_id=assignee.id if assignee else None,
                        title=title, status=status, priority=priority,
                        due_date=today + timedelta(days=random.randint(5, 60))))

    # ── EXPENSES ─────────────────────────────────────────────────────────────
    material_a, material_b = demo["materials"][0][0], demo["materials"][1][0]
    expense_scale = 1 if currency == "INR" else 0.012
    for proj, cat, desc, amount, vendor in [
        (p1,"material",    f"{material_a} — opening stock",   570_000 * expense_scale, "Demo Materials Supplier"),
        (p1,"material",    f"{material_b} — reinforcement",   130_000 * expense_scale, "Demo Steel Supplier"),
        (p1,"labor",       "Foundation excavation labour",     95_000 * expense_scale, "Local Contractor"),
        (p1,"equipment",   "Tower crane — 30 days",           240_000 * expense_scale, "Demo Equipment Rentals"),
        (p1,"subcontract", "Plumbing rough-in — Basement",    180_000 * expense_scale, "Demo Plumbing Works"),
    ]:
        if proj:
            db.add(Expense(project_id=proj.id, category=cat, description=desc,
                           amount=amount,
                           date=today - timedelta(days=random.randint(5, 60)),
                           vendor=vendor))

    # ── INVOICE ──────────────────────────────────────────────────────────────
    inv_no = f"INV-{S}-0001"
    if not db.query(Invoice).filter(Invoice.invoice_no == inv_no).first():
        sub = float(demo["budget1"]) * 0.11
        db.add(Invoice(invoice_no=inv_no, client_id=client.id,
                       project_id=p1.id if p1 else None, status="sent",
                       issue_date=today - timedelta(days=15),
                       due_date=today + timedelta(days=15),
                       subtotal=sub, tax_rate=18.0,
                       tax_amount=sub * 0.18, total=sub * 1.18,
                       paid_amount=0, currency=currency))

    # ── INVENTORY ────────────────────────────────────────────────────────────
    units = ["bags", "kg", "cum", "cum", "nos", "pcs"]
    skus = [f"CEM-{S}", f"STL-{S}", f"AGG-{S}", f"SND-{S}", f"PLY-{S}", f"SAF-{S}"]
    quantities = [120, 1800, 45, 30, 80, 25]
    min_quantities = [50, 500, 15, 10, 20, 10]
    for i, (mat, cost) in enumerate(demo["materials"]):
        unit, sku, qty, min_qty = units[i], skus[i], quantities[i], min_quantities[i]
        if not db.query(InventoryItem).filter(InventoryItem.sku == sku).first():
            db.add(InventoryItem(name=mat, category="material",
                                 sku=sku, unit=unit, quantity=qty,
                                 min_quantity=min_qty, unit_cost=cost,
                                 supplier="Demo Supplier"))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # BIM — Building Information Model
    # ════════════════════════════════════════════════════════════════════════
    bim_name = f"{S}-BIM-001"
    bim = db.query(BIMModel).filter(BIMModel.name == bim_name).first()
    if not bim and p1:
        bim = BIMModel(
            project_id=p1.id,
            name=bim_name,
            description="G+7 Residential Tower — Full 3D structural model",
            version="1.2",
            file_format="json",
            total_floors=8,
            building_height_m=25.6,
            gross_area_m2=4800.0,
            coordinate_system="WCS",
        )
        db.add(bim); db.flush()

        # BIM Elements — Columns, Slabs, Beams, Walls
        BIM_ELEMENTS = [
            # (type,    name,           level,          floor, material,  x,   y,   z,   L,   W,   H,   vol)
            ("Column",  "C1-GF",        "Ground Floor", 0, "Concrete M30",  0.0, 0.0, 0.0, 0.45,0.45,3.6, 0.73),
            ("Column",  "C2-GF",        "Ground Floor", 0, "Concrete M30",  5.0, 0.0, 0.0, 0.45,0.45,3.6, 0.73),
            ("Column",  "C3-GF",        "Ground Floor", 0, "Concrete M30", 10.0, 0.0, 0.0, 0.45,0.45,3.6, 0.73),
            ("Column",  "C1-1F",        "First Floor",  1, "Concrete M30",  0.0, 0.0, 3.6, 0.45,0.45,3.2, 0.65),
            ("Slab",    "S1-GF",        "Ground Floor", 0, "Concrete M30",  0.0, 0.0, 3.6,12.0, 8.0, 0.15,14.4),
            ("Slab",    "S1-1F",        "First Floor",  1, "Concrete M30",  0.0, 0.0, 6.8,12.0, 8.0, 0.15,14.4),
            ("Beam",    "B1-GF-X",      "Ground Floor", 0, "Concrete M30",  0.0, 0.0, 3.6,12.0, 0.3, 0.6, 2.16),
            ("Beam",    "B1-GF-Y",      "Ground Floor", 0, "Concrete M30",  0.0, 0.0, 3.6, 0.3, 8.0, 0.6, 1.44),
            ("Wall",    "W1-Ext-GF",    "Ground Floor", 0, "Brick 230mm",   0.0, 0.0, 0.0, 12.0,0.23,3.6, 9.94),
            ("Window",  "WIN-01-GF",    "Ground Floor", 0, "UPVC Frame",    2.0, 0.0, 1.0, 1.2, 0.1, 1.5, 0.18),
            ("Door",    "DR-01-GF",     "Ground Floor", 0, "Timber Frame",  0.5, 0.0, 0.0, 0.9, 0.1, 2.1, 0.19),
            ("Staircase","STAIR-1",     "Ground Floor", 0, "Concrete M25",  4.0, 6.0, 0.0, 2.5, 1.2, 3.6, 5.4),
        ]
        for etype, ename, level, flr, mat, x, y, z, l, ww, h, vol in BIM_ELEMENTS:
            db.add(BIMElement(model_id=bim.id, element_type=etype, name=ename,
                              level=level, floor_number=flr, material=mat,
                              pos_x=x, pos_y=y, pos_z=z,
                              length_m=l, width_m=ww, height_m=h, volume_m3=vol))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # QUALITY CONTROL
    # ════════════════════════════════════════════════════════════════════════

    # Material Tests
    MT_DATA = [
        # (test_type,           element,            grade, sample_no, slump, c1_7, c2_7, c3_7, c1_28, c2_28, c3_28, avg_28, fck, result)
        ("cube_compressive", "Column C1-GF Pour-1",  "M30","CUBE-001",80, 285,290,288, 430,435,428, 431, 31.2, "pass"),
        ("cube_compressive", "Slab S1-GF Pour-2",    "M25","CUBE-002",90, 230,235,228, 368,372,365, 368, 26.5, "pass"),
        ("cube_compressive", "Beam B1-GF Pour-3",    "M30","CUBE-003",75, 280,275,282, 415,410,418, 414, 29.8, "pass"),
        ("slump",            "Foundation Raft",       "M35","SLMP-001",95, 0,0,0, 0,0,0, 0, 0,     "pass"),
        ("rebar_tensile",    demo["materials"][1][0], "",  "RBAR-001",0,  0,0,0, 0,0,0, 0, 0,      "pass"),
    ]
    for i, (ttype, elem, grade, sno, slmp, c17,c27,c37,c128,c228,c328,avg,fck,res) in enumerate(MT_DATA):
        if p1:
            db.add(MaterialTest(
                project_id=p1.id,
                test_type=ttype,
                test_date=today - timedelta(days=30 - i*5),
                element=elem,
                pour_reference=f"Pour-{i+1:02d}",
                design_code=design_code,
                grade=grade,
                sample_no=sno,
                cube_size_mm=150,
                slump_mm=float(slmp),
                cube1_7day_kN=float(c17), cube2_7day_kN=float(c27), cube3_7day_kN=float(c37),
                cube1_28day_kN=float(c128), cube2_28day_kN=float(c228), cube3_28day_kN=float(c328),
                avg_28day_kN=float(avg),
                fck_achieved_MPa=float(fck),
                result=res,
                lab_name="Demo Accredited Laboratory",
                tested_by=workers[1].first_name if len(workers)>1 else "QC Engineer",
                certificate_no=f"ATL-{S}-{i+1:03d}",
            ))

    # QC Inspections
    QC_DATA = [
        (f"QCI-{S}-001","rebar",       "Columns at Ground Floor",   "Ground Floor", "pass"),
        (f"QCI-{S}-002","formwork",    "Slab Formwork — 1st Floor", "First Floor",  "pass"),
        (f"QCI-{S}-003","pre_pour",    "Pre-pour check — Slab 1F",  "First Floor",  "pass"),
        (f"QCI-{S}-004","brickwork",   "External brick masonry",    "Ground Floor", "fail"),
    ]
    for insp_no, itype, elem, level, result in QC_DATA:
        if not db.query(QCInspection).filter(QCInspection.inspection_no == insp_no).first() and p1:
            insp = QCInspection(
                project_id=p1.id, inspection_no=insp_no,
                inspection_type=itype, element=elem, floor_level=level,
                inspection_date=today - timedelta(days=random.randint(5, 40)),
                inspector_name=workers[4].first_name if len(workers)>4 else "QC Engineer",
                contractor_rep="Site Foreman",
                consultant_rep="Consultant Rep",
                result=result,
                overall_remarks=f"Inspection completed per {design_code} checklist.",
                next_action="Proceed with pour" if result == "pass" else "Rectify and re-inspect",
            )
            db.add(insp); db.flush()
            # Checklist items
            ITEMS = [
                ("1","Bar size and spacing correct",design_code,"As per drawing","Verified",  "pass"),
                ("2","Cover blocks in place",      design_code,"Required cover provided","Verified",  "pass"),
                ("3","Laps and splices adequate",  design_code,"As per approved drawings","Verified","pass"),
                ("4","Formwork joints sealed",     design_code,"No gaps",      "Sealed",     "pass" if result=="pass" else "fail"),
            ]
            for ino, cp, ref, req, actual, st in ITEMS:
                db.add(QCChecklistItem(inspection_id=insp.id, item_no=ino,
                                       check_point=cp, reference=ref,
                                       requirement=req, actual=actual, status=st))

    # NCR
    ncr_no = f"NCR-{S}-001"
    if not db.query(NCReport).filter(NCReport.ncr_no == ncr_no).first() and p1:
        db.add(NCReport(
            project_id=p1.id, ncr_no=ncr_no,
            title="Brick masonry — incorrect bond pattern",
            description="Running bond used instead of English bond as specified in drawings.",
            element="External Wall — Grid A1-A4", floor_level="Ground Floor",
            nc_date=today - timedelta(days=10),
            raised_by="QC Engineer",
            assigned_to="Site Foreman",
            severity="minor",
            root_cause="Workmen not briefed on specification requirement.",
            immediate_action="Stop work on affected bay. Issue non-conformance notice.",
            corrective_action="Demolish and rebuild with correct English bond pattern.",
            preventive_action="Conduct toolbox talk on masonry specifications.",
            due_date=today + timedelta(days=5),
        ))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # SITE OPERATIONS
    # ════════════════════════════════════════════════════════════════════════

    # Equipment
    equip_no = f"EQ-{S}-001"
    equip = db.query(Equipment).filter(Equipment.equipment_no == equip_no).first()
    if not equip:
        equip = Equipment(
            name="Tower Crane TC-5013",
            equipment_no=equip_no,
            category="crane",
            make="Liebherr", model="TC-5013",
            year=2022, ownership="hired",
            vendor="SunTech Equipment Rentals",
            daily_hire_rate=8000.0,
            fuel_type="electric",
            capacity="5T @ 13m radius",
            last_service_date=today - timedelta(days=30),
            next_service_date=today + timedelta(days=60),
            is_active=True,
        )
        db.add(equip)

    equip_no2 = f"EQ-{S}-002"
    equip2 = db.query(Equipment).filter(Equipment.equipment_no == equip_no2).first()
    if not equip2:
        equip2 = Equipment(
            name="Concrete Pump CP-36",
            equipment_no=equip_no2,
            category="pump",
            make="Putzmeister", model="BSF 36",
            year=2021, ownership="hired",
            vendor="Demo Pump Rentals",
            daily_hire_rate=12000.0 if currency == "INR" else 420.0,
            fuel_type="diesel",
            capacity="36m boom, 100m3/hr",
            last_service_date=today - timedelta(days=14),
            next_service_date=today + timedelta(days=16),
            is_active=True,
        )
        db.add(equip2)
    db.flush()

    # Fuel logs
    if equip2 and p1:
        for d in range(3):
            db.add(FuelLog(
                equipment_id=equip2.id,
                project_id=p1.id,
                log_date=today - timedelta(days=d),
                fuel_type="diesel",
                liters=float(random.randint(80, 120)),
                rate_per_ltr=97.5,
                cost=float(random.randint(80, 120)) * 97.5,
                meter_reading=float(1200 + d * 8),
                hours_worked=float(random.randint(6, 10)),
                filled_by="Site Store Keeper",
            ))

    # Site Diaries
    if p1:
        for d in range(5):
            work_done = [
                "Foundation concreting — Column C1-C6 completed. Samples taken.",
                f"Reinforcement fixing — Ground floor columns. {design_code} cover requirements followed.",
                "Formwork striking — Basement slab soffit. Props retained.",
                "RCC column pouring — Grid A. Cube tests dispatched to lab.",
                "Brickwork — External walls Ground floor. QC inspection conducted.",
            ][d]
            db.add(SiteDiary(
                project_id=p1.id,
                report_date=today - timedelta(days=d),
                prepared_by=workers[4].first_name if len(workers)>4 else "Site Manager",
                weather_morning=["sunny","sunny","cloudy","cloudy","sunny"][d],
                weather_afternoon=["sunny","cloudy","sunny","rainy","sunny"][d],
                temperature_c=float(random.randint(28, 38)),
                humidity_pct=float(random.randint(55, 80)),
                total_workers=random.randint(35, 55),
                total_engineers=random.randint(4, 8),
                work_done=work_done,
                material_used=f"{demo['materials'][0][0]}: 20 units | {demo['materials'][1][0]}: 400kg | Aggregate: 3cum",
                equipment_used="Tower Crane: 1No | Vibrator: 2No | Mixer: 1No",
                visitors="Client representative — site visit" if d == 2 else "",
                instructions="Maintain curing for 14 days post-pour",
            ))

    # Material Consumption
    if p1:
        for d in range(3):
            db.add(MaterialConsumption(
                project_id=p1.id,
                log_date=today - timedelta(days=d),
                material=demo["materials"][0][0],
                quantity=float(random.randint(15, 30)),
                unit="bags",
                location_used="Ground Floor Columns",
                purpose="Column concreting M30",
                issued_by="Store Keeper",
            ))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # SAFETY MODULE
    # ════════════════════════════════════════════════════════════════════════

    # Safety Incident
    if p1:
        db.add(SafetyIncident(
            project_id=p1.id,
            title="Near miss — Material dropped from 3rd floor slab",
            incident_type="near_miss", severity="medium",
            incident_date=today - timedelta(days=7),
            location="3rd Floor — Grid C-4", injuries=False, resolved=False,
            reported_by=workers[3].first_name if len(workers)>3 else "Safety Officer",
            corrective_action="Barricading installed. Toolbox talk conducted for all workers.",
        ))

    # Toolbox Talks
    TBT_DATA = [
        ("Working at Height — Fall Prevention",
         "PFAS usage, anchor points, permit for height work above 2m, rescue plan."),
        ("Concrete Pouring Safety",
         "PPE: safety boots, gloves, goggles. Vibrator cable safety. Formwork inspection."),
        ("Crane Safety & Exclusion Zones",
         "Exclusion zone radius, hand signals, load chart, outrigger setup."),
        ("Housekeeping & Fire Prevention",
         "Clear walkways, material stacking, fire extinguisher locations, hot work permit."),
    ]
    if p1:
        for d, (topic, key_pts) in enumerate(TBT_DATA):
            db.add(ToolboxTalk(
                project_id=p1.id, topic=topic,
                talk_date=today - timedelta(days=d*7 + 2),
                conducted_by=workers[3].first_name if len(workers)>3 else "Safety Officer",
                location="Site Entrance Canteen",
                duration_min=20,
                attendees_count=random.randint(30, 50),
                attendees="All site workers",
                key_points=key_pts,
            ))

    # Permits to Work
    PTW_DATA = [
        (f"PTW-{S}-001","height_work", "Working at Height — Column Shuttering Level 3",
         "Column grid A1-A6, Level 3", "approved"),
        (f"PTW-{S}-002","hot_work",    "Welding — Steel column base plates",
         "Basement Level, Grid C", "closed"),
        (f"PTW-{S}-003","excavation",  "Excavation for external utility trench",
         "Site boundary — North side", "pending"),
    ]
    if p1:
        for pno, ptype, title, loc, status in PTW_DATA:
            if not db.query(PermitToWork).filter(PermitToWork.permit_no == pno).first():
                db.add(PermitToWork(
                    project_id=p1.id, permit_no=pno,
                    permit_type=ptype, title=title, location=loc,
                    scope_of_work=f"Demo permit for {title}",
                    requested_by="Site Supervisor",
                    contractor="Main Contractor",
                    workers_involved="5 workers",
                    precautions="Full PPE, barricading, spotter required",
                    ppe_required="Helmet, harness, safety boots, gloves",
                    issued_by=workers[3].first_name if len(workers)>3 else "Safety Officer",
                    approved_by="Project Manager",
                    status=status,
                ))

    # Risk Assessments
    RISKS = [
        ("Working at Height", "Fall from height", "Workers at >2m elevation — column/slab work",
         4, 5, 20, "high",  "PFAS mandatory, permit required, exclusion zone"),
        ("Concrete Pouring",  "Formwork failure", "Wet concrete load causing form collapse",
         3, 5, 15, "high",  "Formwork design check, propping schedule, pre-pour inspection"),
        ("Crane Operations",  "Load drop / swing", "Load dropping on workers below",
         2, 5, 10, "medium","Exclusion zone, load chart compliance, certified operator"),
        ("Excavation",        "Cave-in",          "Trench collapse during excavation",
         2, 4,  8, "medium","Shoring, 45° angle of repose, edge protection"),
        ("Electrical",        "Electrocution",    "Temporary power supply — extension leads",
         2, 4,  8, "medium","RCD protection, cable management, qualified electrician"),
    ]
    if p1:
        for act, haz, risk_desc, like, sev, score, level, controls in RISKS:
            db.add(RiskAssessment(
                project_id=p1.id, activity=act, hazard=haz,
                risk_description=risk_desc,
                likelihood=like, severity_score=sev, risk_score=score,
                risk_level=level,
                control_measures=controls,
                residual_risk=max(2, score // 4),
                responsible=workers[3].first_name if len(workers)>3 else "Safety Officer",
                review_date=today + timedelta(days=30),
                status="open",
            ))

    # Safety Inspection
    if p1:
        db.add(SafetyInspection(
            project_id=p1.id,
            title=f"Monthly HSE Site Inspection — {today.strftime('%b %Y')}",
            inspector=workers[3].first_name if len(workers)>3 else "Safety Officer",
            inspection_date=today - timedelta(days=3),
            passed=True,
            findings="1. PPE compliance: 92% — improve helmet usage near crane area.\n"
                     "2. Housekeeping: material stacking at grid C needs attention.\n"
                     "3. Fire extinguishers: all charged and accessible.",
            recommendations="Conduct targeted toolbox talk on PPE. "
                            "Assign daily housekeeping responsibility per zone.",
            next_inspection=today + timedelta(days=27),
        ))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # DOCUMENTS
    # ════════════════════════════════════════════════════════════════════════
    DOC_DATA = [
        ("Structural Design Report — Foundation",    "design_report",  "STRUC-001-Rev0.pdf",  "approved"),
        ("Architectural Drawing — Ground Floor Plan","drawing",         "ARCH-GF-Rev2.dwg",   "approved"),
        ("Structural Drawing — Column Layout",       "drawing",         "STRUC-COL-Rev1.dwg", "pending"),
        (f"{design_code} Concrete Mix Design Report M30", "test_report", "MIXDES-M30-001.pdf", "approved"),
        ("Safety Management Plan",                   "safety_document", "SMP-Rev1.pdf",       "approved"),
        ("Project Quality Plan",                     "quality_plan",    "PQP-Rev0.pdf",       "pending"),
        ("BOQ — Civil Works",                        "commercial",      "BOQ-Civil-Rev2.xlsx","approved"),
        ("Contract Agreement — Main Contractor",     "contract",        "CONTRACT-001.pdf",   "approved"),
    ]
    if p1:
        for title, dtype, fname, status in DOC_DATA:
            db.add(Document(
                project_id=p1.id, title=title, doc_type=dtype,
                file_name=fname, file_path=f"/documents/{fname}",
                version="1.0", revision=0,
                description=f"Demo document: {title}",
                uploaded_by=workers[0].first_name if workers else "Project Manager",
                approval_status=status,
                approved_by="Project Manager" if status == "approved" else None,
                tags=dtype.replace("_", ","),
                file_size_kb=random.randint(200, 4000),
            ))
    db.flush()

    # ════════════════════════════════════════════════════════════════════════
    # ATTENDANCE
    # ════════════════════════════════════════════════════════════════════════
    if p1 and workers:
        for d in range(7):          # last 7 days
            att_date = today - timedelta(days=d)
            for wkr in workers[:4]:  # first 4 workers
                present = random.random() > 0.1  # 90% attendance
                check_in  = "08:00" if present else None
                check_out = f"{random.choice([16,17,18])}:30" if present else None
                hrs = float(random.randint(7, 10)) if present else 0.0
                db.add(Attendance(
                    worker_id=wkr.id, project_id=p1.id,
                    date=att_date, check_in=check_in, check_out=check_out,
                    hours_worked=hrs, is_present=present,
                    overtime_hours=max(0.0, hrs - 8.0),
                ))
    db.flush()


# ── Subscriptions ──────────────────────────────────────────────────────────────

@router.post("/subscribe")
def subscribe(req: SubscribeReq, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    """Assign / change a tenant's subscription plan."""
    _seed_plans(db)
    company = db.query(Company).filter(Company.id == req.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == req.plan_name).first()
    if not plan:
        raise HTTPException(400, f"Plan '{req.plan_name}' not found")

    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == req.company_id).first()
    now = datetime.utcnow()
    if sub:
        sub.plan_id = plan.id
        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = now + (timedelta(days=365) if req.billing_cycle == "annual" else timedelta(days=30))
    else:
        sub = TenantSubscription(
            company_id=req.company_id,
            plan_id=plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + (timedelta(days=365) if req.billing_cycle == "annual" else timedelta(days=30)),
        )
        db.add(sub)
    db.commit(); db.refresh(sub)
    return _sub_to_dict(sub)


@router.get("/subscriptions/{company_id}")
def get_subscription(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == company_id).first()
    if not sub:
        raise HTTPException(404, "No subscription for this company")
    return _sub_to_dict(sub)


# ── Tenant Config (White-label) ────────────────────────────────────────────────

@router.get("/config/{company_id}")
def get_config(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    cfg = db.query(TenantConfig).filter(TenantConfig.company_id == company_id).first()
    if not cfg:
        raise HTTPException(404, "No config for this company")
    return {
        "company_id": cfg.company_id,
        "primary_color": cfg.primary_color,
        "secondary_color": cfg.secondary_color,
        "logo_url": cfg.logo_url,
        "app_name": cfg.app_name,
        "feature_flags": cfg.feature_flags or {},
        "custom_domain": cfg.custom_domain,
        "timezone": cfg.timezone,
        "locale": cfg.locale,
        "currency": cfg.currency,
    }


@router.put("/config/{company_id}")
def update_config(company_id: int, req: TenantConfigUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    cfg = db.query(TenantConfig).filter(TenantConfig.company_id == company_id).first()
    if not cfg:
        # create on demand
        cfg = TenantConfig(company_id=company_id)
        db.add(cfg)
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    db.commit(); db.refresh(cfg)
    return {"message": "Config updated", "company_id": company_id}


# ── Usage Tracking ─────────────────────────────────────────────────────────────

@router.get("/usage/{company_id}")
def get_usage(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    """Current period usage vs plan limits."""
    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == company_id).first()
    plan = sub.plan if sub else None

    # Live counts
    user_count    = db.query(User).filter(User.company_id == company_id).count()
    project_count = db.query(Project).filter(Project.company_id == company_id).count() \
                    if hasattr(Project, "company_id") else db.query(Project).count()

    period = datetime.utcnow().strftime("%Y-%m")
    usage = db.query(TenantUsage).filter(
        TenantUsage.company_id == company_id,
        TenantUsage.period_month == period
    ).first()

    result = {
        "company_id": company_id,
        "period": period,
        "current": {
            "users": user_count,
            "projects": project_count,
            "storage_gb": usage.storage_used_gb if usage else 0.0,
            "api_calls": usage.api_calls if usage else 0,
        },
        "limits": {
            "users": plan.max_users if plan else 3,
            "projects": plan.max_projects if plan else 2,
            "storage_gb": plan.max_storage_gb if plan else 0.5,
            "api_calls": "unlimited",
        },
        "plan": plan.name if plan else "free",
        "subscription_status": sub.status if sub else "none",
    }
    if plan:
        result["utilization"] = {
            "users":    round(user_count    / max(plan.max_users,    1) * 100, 1) if plan.max_users    > 0 else 0,
            "projects": round(project_count / max(plan.max_projects, 1) * 100, 1) if plan.max_projects > 0 else 0,
        }
    return result


@router.post("/usage/{company_id}/record")
def record_usage(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    """Update this month's usage snapshot."""
    period = datetime.utcnow().strftime("%Y-%m")
    usage = db.query(TenantUsage).filter(
        TenantUsage.company_id == company_id,
        TenantUsage.period_month == period
    ).first()
    users    = db.query(User).filter(User.company_id == company_id).count()
    projects = db.query(Project).count()

    if usage:
        usage.active_users  = users
        usage.project_count = projects
        usage.api_calls     = (usage.api_calls or 0) + 1
    else:
        usage = TenantUsage(
            company_id=company_id,
            period_month=period,
            active_users=users,
            project_count=projects,
            api_calls=1,
        )
        db.add(usage)
    db.commit()
    return {"message": "Usage recorded", "period": period}


# ── Admin Dashboard ────────────────────────────────────────────────────────────

@router.get("/admin/dashboard")
def saas_admin_dashboard(db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    """Platform-wide SaaS metrics for super-admin."""
    _seed_plans(db)
    companies = db.query(Company).all()
    subs = db.query(TenantSubscription).all()

    plan_dist: Dict[str, int] = {}
    for s in subs:
        plan_name = s.plan.name if s.plan else "none"
        plan_dist[plan_name] = plan_dist.get(plan_name, 0) + 1

    active    = sum(1 for s in subs if s.status == "active")
    trial     = sum(1 for s in subs if s.status == "trial")
    cancelled = sum(1 for s in subs if s.status == "cancelled")

    # MRR
    mrr = sum(
        s.plan.price_monthly
        for s in subs
        if s.status in ("active", "trial") and s.plan
    )

    return {
        "total_tenants": len(companies),
        "subscribed_tenants": len(subs),
        "status": {"active": active, "trial": trial, "cancelled": cancelled},
        "plan_distribution": plan_dist,
        "mrr_usd": round(mrr, 2),
        "arr_usd": round(mrr * 12, 2),
        "plans": [_plan_to_dict(p) for p in db.query(SubscriptionPlan).all()],
    }


@router.get("/admin/tenants")
def list_tenants(db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    """All tenants with subscription status."""
    companies = db.query(Company).all()
    result = []
    for c in companies:
        sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == c.id).first()
        cfg = db.query(TenantConfig).filter(TenantConfig.company_id == c.id).first()
        user_count = db.query(User).filter(User.company_id == c.id).count()
        result.append({
            "company_id": c.id,
            "company_name": c.name,
            "is_active": c.is_active,
            "user_count": user_count,
            "plan": sub.plan.name if sub and sub.plan else "free",
            "subscription_status": sub.status if sub else "none",
            "trial_ends": str(sub.trial_ends.date()) if sub and sub.trial_ends else None,
            "app_name": cfg.app_name if cfg else "NagaForge",
            "primary_color": cfg.primary_color if cfg else "#2563eb",
        })
    return result


@router.put("/admin/tenants/{company_id}/suspend")
def suspend_tenant(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == company_id).first()
    if sub:
        sub.status = "suspended"
        db.commit()
    co = db.query(Company).filter(Company.id == company_id).first()
    if co:
        co.is_active = False
        db.commit()
    return {"message": f"Tenant {company_id} suspended"}


@router.put("/admin/tenants/{company_id}/activate")
def activate_tenant(company_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_saas_admin)):
    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == company_id).first()
    if sub:
        sub.status = "active"
        db.commit()
    co = db.query(Company).filter(Company.id == company_id).first()
    if co:
        co.is_active = True
        db.commit()
    return {"message": f"Tenant {company_id} activated"}


# ── Team Roles & Responsibilities ──────────────────────────────────────────────

ROLE_REGISTRY = [
    {
        "role": "admin",
        "display": "Administrator",
        "icon": "fa-user-shield",
        "color": "#2563eb",
        "responsibilities": [
            "Full platform access — all modules",
            "Create and manage users and roles",
            "Company settings and white-label config",
            "Subscription and billing management",
            "View all reports and analytics",
        ],
        "modules": ["All Modules"],
        "default_password": "Admin@123",
    },
    {
        "role": "project_manager",
        "display": "Project Manager",
        "icon": "fa-diagram-project",
        "color": "#16a34a",
        "responsibilities": [
            "Create and manage projects (scope, budget, timeline)",
            "Assign tasks to team members and track progress",
            "Review EVM — Earned Value vs Planned Value",
            "Approve expenses and purchase orders",
            "Generate project progress PDF reports",
            "Manage project scheduling (CPM / Gantt)",
        ],
        "modules": ["Projects","Task Board","Scheduling","Commercial","Finance","Reports"],
        "default_password": "Demo@123",
    },
    {
        "role": "engineer",
        "display": "Structural Engineer",
        "icon": "fa-drafting-compass",
        "color": "#ea580c",
        "responsibilities": [
            "Perform IS 800 steel beam / column / weld / bolt design",
            "Perform IS 456 RCC beam, slab, column, footing design",
            "Run AISC 360, Eurocode 2/3, NBCC design checks",
            "Review BIM models and raise structural issues",
            "Generate and download PDF calculation sheets",
            "Prepare BBS (Bar Bending Schedule) and mix design",
        ],
        "modules": ["Structural Engineering","BIM","Documents","Reports"],
        "default_password": "Demo@123",
    },
    {
        "role": "site_manager",
        "display": "Site Manager",
        "icon": "fa-hard-hat",
        "color": "#0891b2",
        "responsibilities": [
            "Record daily site diary (progress, weather, issues)",
            "Mark worker attendance and overtime",
            "Log equipment usage and fuel consumption",
            "Issue material gate passes",
            "Update task status and field progress %",
            "Coordinate with QC engineer on cube tests",
        ],
        "modules": ["Site Operations","Task Board","Workforce","Inventory"],
        "default_password": "Demo@123",
    },
    {
        "role": "safety_officer",
        "display": "Safety Officer (HSE)",
        "icon": "fa-shield-alt",
        "color": "#dc2626",
        "responsibilities": [
            "Log and investigate safety incidents and near-misses",
            "Conduct and record toolbox talks",
            "Perform safety inspections and audits",
            "Track corrective actions to closure",
            "Monitor HSE KPIs (LTI rate, near-miss ratio)",
            "Generate safety incident PDF reports",
        ],
        "modules": ["Safety & HSE","Site Operations","Reports"],
        "default_password": "Demo@123",
    },
    {
        "role": "quality_engineer",
        "display": "QC Engineer",
        "icon": "fa-flask",
        "color": "#7c3aed",
        "responsibilities": [
            "Record and evaluate concrete cube test results (IS 516)",
            "Issue pass / fail verdicts with auto IS 516 compliance check",
            "Log material test reports (steel, cement, aggregates)",
            "Raise and track Non-Conformance Reports (NCRs)",
            "Conduct QC inspections with checklist sign-off",
            "Download and submit QC PDF certificates",
        ],
        "modules": ["Quality Control","Documents","Reports"],
        "default_password": "Demo@123",
    },
    {
        "role": "accountant",
        "display": "Finance Manager",
        "icon": "fa-file-invoice-dollar",
        "color": "#854d0e",
        "responsibilities": [
            "Create GST-compliant invoices and send to clients",
            "Track and categorise project expenses",
            "Manage vendor purchase orders",
            "Monitor budget vs actual spend per project",
            "Prepare cash flow reports and aging analysis",
            "Process payroll and worker salary statements",
        ],
        "modules": ["Finance","Commercial","Clients & CRM","Reports"],
        "default_password": "Demo@123",
    },
]

@router.get("/team-roles")
def get_team_roles():
    """Return all platform roles with responsibilities — used for onboarding welcome screen."""
    return ROLE_REGISTRY


@router.get("/team/{company_id}")
def get_company_team(company_id: int, db: Session = Depends(get_db)):
    """Return all users for a company with their role details."""
    users = db.query(User).filter(User.company_id == company_id, User.is_active == True).all()
    result = []
    for u in users:
        role_info = next((r for r in ROLE_REGISTRY if r["role"] == u.role), {})
        result.append({
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "display_role": role_info.get("display", u.role.replace("_"," ").title()),
            "icon": role_info.get("icon", "fa-user"),
            "color": role_info.get("color", "#64748b"),
            "responsibilities": role_info.get("responsibilities", []),
            "modules": role_info.get("modules", []),
        })
    return result


# ── Feature Flag Check ─────────────────────────────────────────────────────────

@router.get("/check-feature/{company_id}/{feature}")
def check_feature(company_id: int, feature: str, db: Session = Depends(get_db)):
    """Returns whether a feature is enabled for the tenant's plan."""
    sub = db.query(TenantSubscription).filter(TenantSubscription.company_id == company_id).first()
    if not sub or not sub.plan:
        return {"company_id": company_id, "feature": feature, "allowed": False, "reason": "No subscription"}
    allowed = feature in (sub.plan.features or [])
    return {
        "company_id": company_id,
        "feature": feature,
        "allowed": allowed,
        "plan": sub.plan.name,
        "status": sub.status,
    }
