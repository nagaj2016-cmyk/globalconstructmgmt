"""
NagaForge — All Database Models
Phases 0-8: Foundation, ERP, Commercial, Planning, Site Ops, Quality, Safety, Engineering
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text,
    ForeignKey, Enum, Date, JSON, BigInteger, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, expression
import enum
from database import Base
from tenancy import TenantScoped

# Fixed-point money: exact NUMERIC(15,2) storage (Postgres), returned as
# float so existing arithmetic keeps working without Decimal/float clashes.
Money = Numeric(15, 2, asdecimal=False)


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class ProjectStatus(str, enum.Enum):
    planning    = "planning"
    active      = "active"
    on_hold     = "on_hold"
    completed   = "completed"
    cancelled   = "cancelled"

class TaskStatus(str, enum.Enum):
    todo        = "todo"
    in_progress = "in_progress"
    review      = "review"
    done        = "done"

class TaskPriority(str, enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"
    urgent = "urgent"

class WorkerRole(str, enum.Enum):
    architect      = "architect"
    engineer       = "engineer"
    designer       = "designer"
    site_manager   = "site_manager"
    foreman        = "foreman"
    electrician    = "electrician"
    plumber        = "plumber"
    mason          = "mason"
    carpenter      = "carpenter"
    laborer        = "laborer"
    safety_officer = "safety_officer"
    admin          = "admin"

class WorkerStatus(str, enum.Enum):
    active     = "active"
    inactive   = "inactive"
    on_leave   = "on_leave"

class InvoiceStatus(str, enum.Enum):
    draft    = "draft"
    sent     = "sent"
    paid     = "paid"
    overdue  = "overdue"
    cancelled= "cancelled"

class IncidentSeverity(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"

class ApprovalStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"
    revision = "revision"

class POStatus(str, enum.Enum):
    draft     = "draft"
    sent      = "sent"
    confirmed = "confirmed"
    partial   = "partial"
    received  = "received"
    cancelled = "cancelled"

class TestResult(str, enum.Enum):
    pass_   = "pass"
    fail    = "fail"
    pending = "pending"

class RiskLevel(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 0 — FOUNDATION
# ══════════════════════════════════════════════════════════════════════════════

class Company(Base):
    """Multi-tenant anchor — each company is an isolated tenant."""
    __tablename__ = "companies"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(300), nullable=False)
    short_name   = Column(String(50))
    registration_no = Column(String(100))
    gst_no       = Column(String(50), nullable=True)
    country      = Column(String(100), default="India")
    currency     = Column(String(10), default="INR")
    timezone     = Column(String(100), default="Asia/Kolkata")
    city         = Column(String(100), nullable=True)
    address      = Column(Text)
    phone        = Column(String(50))
    email        = Column(String(200))
    website      = Column(String(200))
    logo_url     = Column(String(500))
    seal_url     = Column(String(500))   # engineer's stamp/seal for calc sheets
    is_active    = Column(Boolean, default=True)
    plan         = Column(String(50), default="starter")   # starter, professional, enterprise
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    branches     = relationship("Branch", back_populates="company", cascade="all, delete")
    departments  = relationship("Department", back_populates="company", cascade="all, delete")
    users        = relationship("User", back_populates="company")


class Branch(Base):
    __tablename__ = "branches"

    id           = Column(Integer, primary_key=True, index=True)
    company_id   = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    name         = Column(String(200), nullable=False)
    city         = Column(String(100))
    country      = Column(String(100))
    address      = Column(Text)
    phone        = Column(String(50))
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    company      = relationship("Company", back_populates="branches")


class Department(Base):
    __tablename__ = "departments"

    id           = Column(Integer, primary_key=True, index=True)
    company_id   = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    name         = Column(String(200), nullable=False)
    code         = Column(String(20))
    head_name    = Column(String(200))
    description  = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    company      = relationship("Company", back_populates="departments")


class AuditLog(Base):
    """Immutable audit trail — every create/update/delete/sign-off action.

    Not TenantScoped (the auto-filter must never hide or block audit writes);
    tenant scoping is done explicitly via company_id on reads."""
    __tablename__ = "audit_logs"

    id           = Column(Integer, primary_key=True, index=True)
    company_id   = Column(Integer, index=True, nullable=True)   # tenant scope for reads
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    username     = Column(String(100))
    action       = Column(String(50))   # CREATE, UPDATE, DELETE, SUBMIT, CHECK, APPROVE, LOGIN
    entity_type  = Column(String(100))  # Project, Invoice, CalculationRecord...
    entity_id    = Column(String(50))   # PK of the entity
    summary      = Column(String(300))  # human-readable one-liner
    old_value    = Column(JSON)
    new_value    = Column(JSON)
    ip_address   = Column(String(50))
    user_agent   = Column(String(300))
    timestamp    = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token        = Column(String(500), unique=True, index=True)
    expires_at   = Column(DateTime(timezone=True))
    is_revoked   = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    ip_address   = Column(String(50))


class Notification(Base):
    __tablename__ = "notifications"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title        = Column(String(300))
    message      = Column(Text)
    type         = Column(String(50), default="info")   # info, warning, alert, success
    entity_type  = Column(String(100))
    entity_id    = Column(Integer)
    is_read      = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — CORE ERP
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    company_id      = Column(Integer, ForeignKey("companies.id"), nullable=True)
    username        = Column(String(100), unique=True, index=True, nullable=False)
    full_name       = Column(String(200), nullable=False)
    email           = Column(String(200), unique=True, nullable=True)
    phone           = Column(String(50))
    hashed_password = Column(String(300), nullable=False)
    role            = Column(String(50), default="site_engineer")
    country         = Column(String(100), default="India")
    language        = Column(String(20), default="en")
    department_id   = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active       = Column(Boolean, default=True)
    # Platform admins bypass tenant isolation (operator/support). Demo accounts
    # are the only ones allowed to load/reset demo data and see demo rows.
    is_platform_admin = Column(Boolean, default=False, nullable=False, server_default=expression.false())
    is_demo         = Column(Boolean, default=False, nullable=False, server_default=expression.false())
    avatar_url      = Column(String(500))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_login      = Column(DateTime(timezone=True), nullable=True)

    company         = relationship("Company", back_populates="users")
    refresh_tokens  = relationship("RefreshToken", cascade="all, delete")
    notifications   = relationship("Notification", cascade="all, delete")


class Client(TenantScoped, Base):
    __tablename__ = "clients"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(200), nullable=False)
    company      = Column(String(200))
    email        = Column(String(200), unique=True, index=True)
    phone        = Column(String(50))
    address      = Column(Text)
    city         = Column(String(100))
    country      = Column(String(100), default="India")
    tax_id       = Column(String(100))      # GST/TRN/EIN etc
    credit_limit = Column(Money, default=0.0)
    payment_terms= Column(Integer, default=30)   # days
    notes        = Column(Text)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    projects     = relationship("Project", back_populates="client")
    invoices     = relationship("Invoice", back_populates="client")


class Contractor(TenantScoped, Base):
    __tablename__ = "contractors"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=False)
    company_name    = Column(String(200))
    trade           = Column(String(100))   # civil, electrical, plumbing, HVAC, MEP
    license_no      = Column(String(100))
    email           = Column(String(200))
    phone           = Column(String(50))
    address         = Column(Text)
    country         = Column(String(100))
    rating          = Column(Float, default=0.0)   # 1-5
    experience_years= Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    contracts       = relationship("ProjectContract", back_populates="contractor")


class Consultant(TenantScoped, Base):
    __tablename__ = "consultants"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=False)
    firm            = Column(String(200))
    specialization  = Column(String(100))   # structural, MEP, soil, geotechnical, QS
    license_no      = Column(String(100))
    email           = Column(String(200))
    phone           = Column(String(50))
    address         = Column(Text)
    country         = Column(String(100))
    fee_type        = Column(String(50))    # fixed, hourly, % of project
    is_active       = Column(Boolean, default=True)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class Project(TenantScoped, Base):
    __tablename__ = "projects"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(300), nullable=False)
    project_code   = Column(String(50), unique=True)
    description    = Column(Text)
    client_id      = Column(Integer, ForeignKey("clients.id"), nullable=True)
    contractor_id  = Column(Integer, ForeignKey("contractors.id"), nullable=True)
    consultant_id  = Column(Integer, ForeignKey("consultants.id"), nullable=True)
    status         = Column(Enum(ProjectStatus), default=ProjectStatus.planning)
    start_date     = Column(Date)
    end_date       = Column(Date)
    actual_start   = Column(Date)
    actual_end     = Column(Date)
    budget         = Column(Money, default=0.0)
    spent          = Column(Money, default=0.0)
    contracted_value= Column(Money, default=0.0)
    location       = Column(String(300))
    country        = Column(String(100), default="India")
    design_code    = Column(String(20), default="IS")  # IS, NBCC, ASCE, EC
    project_type   = Column(String(100))
    progress       = Column(Integer, default=0)
    latitude       = Column(Float)
    longitude      = Column(Float)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    client         = relationship("Client", back_populates="projects")
    contractor     = relationship("Contractor")
    consultant     = relationship("Consultant")
    tasks          = relationship("Task", back_populates="project", cascade="all, delete")
    documents      = relationship("Document", back_populates="project", cascade="all, delete")
    invoices       = relationship("Invoice", back_populates="project")
    assignments    = relationship("ProjectWorker", back_populates="project", cascade="all, delete")
    expenses       = relationship("Expense", back_populates="project", cascade="all, delete")
    boq_items      = relationship("BOQItem", back_populates="project", cascade="all, delete")
    budgets        = relationship("Budget", back_populates="project", cascade="all, delete")
    contracts      = relationship("ProjectContract", back_populates="project", cascade="all, delete")
    change_orders  = relationship("ChangeOrder", back_populates="project", cascade="all, delete")
    rfis           = relationship("RFI", back_populates="project", cascade="all, delete")
    drawings       = relationship("DrawingRegister", back_populates="project", cascade="all, delete")
    calculations   = relationship("CalculationRecord", back_populates="project", cascade="all, delete")
    site_diaries   = relationship("SiteDiary", back_populates="project", cascade="all, delete")
    material_tests = relationship("MaterialTest", back_populates="project", cascade="all, delete")
    qc_inspections = relationship("QCInspection", back_populates="project", cascade="all, delete")
    ncrs           = relationship("NCReport", back_populates="project", cascade="all, delete")
    toolbox_talks  = relationship("ToolboxTalk", back_populates="project", cascade="all, delete")
    permits        = relationship("PermitToWork", back_populates="project", cascade="all, delete")
    risk_assessments= relationship("RiskAssessment", back_populates="project", cascade="all, delete")


class CalculationRecord(TenantScoped, Base):
    """Saved engineering calculation with source proof and audit-ready inputs."""
    __tablename__ = "calculation_records"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id"), nullable=True)
    calculator      = Column(String(150), nullable=False)
    country         = Column(String(100))
    code_basis      = Column(String(150))
    design_code     = Column(String(50))
    status          = Column(String(50))
    inputs          = Column(JSON, default=dict)
    result          = Column(JSON, default=dict)
    proof           = Column(JSON, default=dict)
    pdf_url         = Column(String(500))
    created_by      = Column(String(200))
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # ── Sign-off workflow (prepared → checked → approved), audit-grade ────────
    # State machine enforced in the router; an approved record is immutable.
    signoff_status  = Column(String(20), default="draft", index=True)  # draft/prepared/checked/approved/superseded
    revision        = Column(Integer, default=1)
    supersedes_id   = Column(Integer, nullable=True)     # previous revision this replaces
    locked          = Column(Boolean, default=False, nullable=False, server_default=expression.false())
    title           = Column(String(200))                # e.g. "Beam B12 — L3 slab"
    prepared_by     = Column(String(200))
    prepared_at     = Column(DateTime(timezone=True), nullable=True)
    checked_by      = Column(String(200))
    checked_at      = Column(DateTime(timezone=True), nullable=True)
    approved_by     = Column(String(200))
    approved_at     = Column(DateTime(timezone=True), nullable=True)

    project         = relationship("Project", back_populates="calculations")


class CalcComment(TenantScoped, Base):
    """Threaded review comments on a calculation — the collaboration layer."""
    __tablename__ = "calc_comments"

    id             = Column(Integer, primary_key=True, index=True)
    calculation_id = Column(Integer, ForeignKey("calculation_records.id", ondelete="CASCADE"), index=True)
    author         = Column(String(200))
    author_id      = Column(Integer, nullable=True)
    body           = Column(Text, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())


class Document(TenantScoped, Base):
    __tablename__ = "documents"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    title        = Column(String(300), nullable=False)
    doc_type     = Column(String(100))
    file_name    = Column(String(300))
    file_path    = Column(String(500))
    version      = Column(String(20), default="1.0")
    revision     = Column(Integer, default=0)
    description  = Column(Text)
    uploaded_by  = Column(String(200))
    approval_status = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending)
    approved_by  = Column(String(200))
    approved_at  = Column(DateTime(timezone=True))
    tags         = Column(String(500))   # comma-separated
    file_size_kb = Column(Integer, default=0)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    project      = relationship("Project", back_populates="documents")
    revisions    = relationship("DocumentRevision", back_populates="document", cascade="all, delete")


class DocumentRevision(TenantScoped, Base):
    __tablename__ = "document_revisions"

    id           = Column(Integer, primary_key=True, index=True)
    document_id  = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    version      = Column(String(20))
    file_name    = Column(String(300))
    file_path    = Column(String(500))
    change_notes = Column(Text)
    uploaded_by  = Column(String(200))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    document     = relationship("Document", back_populates="revisions")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — COMMERCIAL
# ══════════════════════════════════════════════════════════════════════════════

class BOQItem(TenantScoped, Base):
    """Bill of Quantities line item."""
    __tablename__ = "boq_items"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    item_no      = Column(String(20))      # 1.1, 1.2, 2.1...
    description  = Column(String(500), nullable=False)
    unit         = Column(String(50))      # m3, m2, kg, rft, nos, ls
    quantity     = Column(Float, default=0.0)
    unit_rate    = Column(Money, default=0.0)
    amount       = Column(Money, default=0.0)
    category     = Column(String(100))     # earthwork, concrete, masonry, finishes...
    specification= Column(Text)
    remarks      = Column(Text)
    is_provisional= Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    project      = relationship("Project", back_populates="boq_items")


class RateAnalysis(TenantScoped, Base):
    """Rate analysis for BOQ items."""
    __tablename__ = "rate_analysis"

    id           = Column(Integer, primary_key=True, index=True)
    item_code    = Column(String(50), unique=True)
    description  = Column(String(500), nullable=False)
    unit         = Column(String(50))
    labour_cost  = Column(Float, default=0.0)
    material_cost= Column(Float, default=0.0)
    equipment_cost= Column(Float, default=0.0)
    overhead_pct = Column(Float, default=15.0)  # overhead %
    profit_pct   = Column(Float, default=10.0)  # profit %
    total_rate   = Column(Float, default=0.0)
    country      = Column(String(50), default="IN")  # country-specific rates
    state        = Column(String(100))   # state schedule of rates
    year         = Column(Integer)
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class Vendor(TenantScoped, Base):
    __tablename__ = "vendors"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=False)
    category        = Column(String(100))   # material, equipment, services
    contact_person  = Column(String(200))
    email           = Column(String(200))
    phone           = Column(String(50))
    address         = Column(Text)
    city            = Column(String(100))
    country         = Column(String(100))
    tax_id          = Column(String(100))   # GST/TRN/EIN
    payment_terms   = Column(Integer, default=30)
    rating          = Column(Float, default=0.0)
    approved        = Column(Boolean, default=False)
    bank_name       = Column(String(200))
    bank_account    = Column(String(100))
    notes           = Column(Text)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")


class PurchaseOrder(TenantScoped, Base):
    __tablename__ = "purchase_orders"

    id           = Column(Integer, primary_key=True, index=True)
    po_number    = Column(String(50), unique=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    vendor_id    = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    status       = Column(Enum(POStatus), default=POStatus.draft)
    po_date      = Column(Date)
    delivery_date= Column(Date)
    delivery_address = Column(Text)
    subtotal     = Column(Money, default=0.0)
    tax_amount   = Column(Money, default=0.0)
    total        = Column(Money, default=0.0)
    terms        = Column(Text)
    notes        = Column(Text)
    approved_by  = Column(String(200))
    approved_at  = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    vendor       = relationship("Vendor", back_populates="purchase_orders")
    items        = relationship("POItem", back_populates="po", cascade="all, delete")


class POItem(TenantScoped, Base):
    __tablename__ = "po_items"

    id           = Column(Integer, primary_key=True, index=True)
    po_id        = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    description  = Column(String(500))
    unit         = Column(String(50))
    quantity     = Column(Float, default=0.0)
    unit_rate    = Column(Money, default=0.0)
    amount       = Column(Money, default=0.0)
    received_qty = Column(Float, default=0.0)
    remarks      = Column(String(300))

    po           = relationship("PurchaseOrder", back_populates="items")


class ProjectContract(TenantScoped, Base):
    """Contract between project owner and contractor/consultant."""
    __tablename__ = "project_contracts"

    id               = Column(Integer, primary_key=True, index=True)
    project_id       = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    contractor_id    = Column(Integer, ForeignKey("contractors.id"), nullable=True)
    consultant_id    = Column(Integer, ForeignKey("consultants.id"), nullable=True)
    contract_no      = Column(String(100), unique=True)
    contract_type    = Column(String(50))   # lump_sum, item_rate, cost_plus, epc
    scope            = Column(Text)
    contract_value   = Column(Money, default=0.0)
    retention_pct    = Column(Float, default=5.0)
    start_date       = Column(Date)
    end_date         = Column(Date)
    signed_date      = Column(Date)
    status           = Column(String(50), default="draft")
    payment_schedule = Column(JSON)   # list of milestone payments
    variation_amount = Column(Money, default=0.0)
    notes            = Column(Text)
    document_path    = Column(String(500))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    project          = relationship("Project", back_populates="contracts")
    contractor       = relationship("Contractor", back_populates="contracts")
    consultant       = relationship("Consultant")
    change_orders    = relationship("ChangeOrder", back_populates="contract")


class ChangeOrder(TenantScoped, Base):
    """Contract variation/change order with cost and time impact."""
    __tablename__ = "change_orders"

    id               = Column(Integer, primary_key=True, index=True)
    project_id       = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    contract_id      = Column(Integer, ForeignKey("project_contracts.id"), nullable=True)
    co_number        = Column(String(100), unique=True, index=True)
    title            = Column(String(300), nullable=False)
    description      = Column(Text)
    reason           = Column(String(200))
    status           = Column(String(50), default="draft")  # draft, submitted, approved, rejected, implemented
    cost_impact      = Column(Money, default=0.0)
    time_impact_days = Column(Integer, default=0)
    requested_by     = Column(String(200))
    submitted_date   = Column(Date)
    approved_by      = Column(String(200))
    approved_date    = Column(Date)
    notes            = Column(Text)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    project          = relationship("Project", back_populates="change_orders")
    contract         = relationship("ProjectContract", back_populates="change_orders")


class RFI(TenantScoped, Base):
    """Request for Information register for project clarifications."""
    __tablename__ = "rfis"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    rfi_number  = Column(String(100), unique=True, index=True)
    subject     = Column(String(300), nullable=False)
    question    = Column(Text, nullable=False)
    answer      = Column(Text)
    discipline  = Column(String(100))      # structural, architectural, MEP, commercial
    priority    = Column(String(50), default="medium")
    status      = Column(String(50), default="open")  # open, answered, closed, void
    raised_by   = Column(String(200))
    assigned_to = Column(String(200))
    due_date    = Column(Date)
    answered_by = Column(String(200))
    answered_at = Column(DateTime(timezone=True))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    project     = relationship("Project", back_populates="rfis")


class DrawingRegister(TenantScoped, Base):
    """Drawing issue/revision register."""
    __tablename__ = "drawing_register"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    drawing_no   = Column(String(100), index=True)
    title        = Column(String(300), nullable=False)
    discipline   = Column(String(100))
    revision     = Column(String(30), default="0")
    status       = Column(String(50), default="draft")  # draft, submitted, approved, superseded
    issue_date   = Column(Date)
    received_date= Column(Date)
    prepared_by  = Column(String(200))
    checked_by   = Column(String(200))
    approved_by  = Column(String(200))
    file_name    = Column(String(300))
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    project      = relationship("Project", back_populates="drawings")


class Budget(TenantScoped, Base):
    __tablename__ = "budgets"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name         = Column(String(200))
    total_budget = Column(Money, default=0.0)
    approved     = Column(Boolean, default=False)
    approved_by  = Column(String(200))
    approved_at  = Column(DateTime(timezone=True))
    revision     = Column(Integer, default=0)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    project      = relationship("Project", back_populates="budgets")
    items        = relationship("BudgetItem", back_populates="budget", cascade="all, delete")


class BudgetItem(TenantScoped, Base):
    __tablename__ = "budget_items"

    id           = Column(Integer, primary_key=True, index=True)
    budget_id    = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"))
    category     = Column(String(100))   # materials, labor, equipment, overhead, contingency
    description  = Column(String(300))
    budgeted_cost= Column(Money, default=0.0)
    actual_cost  = Column(Money, default=0.0)
    committed    = Column(Float, default=0.0)   # PO raised but not paid
    variance     = Column(Float, default=0.0)

    budget       = relationship("Budget", back_populates="items")


# ══════════════════════════════════════════════════════════════════════════════
# WORKERS / HR
# ══════════════════════════════════════════════════════════════════════════════

class Worker(TenantScoped, Base):
    __tablename__ = "workers"

    id              = Column(Integer, primary_key=True, index=True)
    first_name      = Column(String(100), nullable=False)
    last_name       = Column(String(100), nullable=False)
    employee_id     = Column(String(50), unique=True)
    email           = Column(String(200), unique=True, index=True)
    phone           = Column(String(50))
    role            = Column(Enum(WorkerRole), nullable=False)
    status          = Column(Enum(WorkerStatus), default=WorkerStatus.active)
    daily_rate      = Column(Float, default=0.0)
    monthly_salary  = Column(Float, default=0.0)
    skills          = Column(Text)
    certifications  = Column(Text)
    hire_date       = Column(Date)
    nationality     = Column(String(100))
    id_type         = Column(String(50))    # aadhar, passport, emiratesid
    id_number       = Column(String(100))
    visa_expiry     = Column(Date)
    blood_group     = Column(String(10))
    emergency_contact = Column(String(200))
    address         = Column(Text)
    notes           = Column(Text)
    photo_url       = Column(String(500))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    assignments     = relationship("ProjectWorker", back_populates="worker")
    attendance      = relationship("Attendance", back_populates="worker", cascade="all, delete")
    tasks           = relationship("Task", back_populates="assignee")


class ProjectWorker(TenantScoped, Base):
    __tablename__ = "project_workers"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    worker_id  = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"))
    role       = Column(String(100))
    start_date = Column(Date)
    end_date   = Column(Date)

    project    = relationship("Project", back_populates="assignments")
    worker     = relationship("Worker", back_populates="assignments")


class Task(TenantScoped, Base):
    __tablename__ = "tasks"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    assignee_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    title       = Column(String(300), nullable=False)
    description = Column(Text)
    status      = Column(Enum(TaskStatus), default=TaskStatus.todo)
    priority    = Column(Enum(TaskPriority), default=TaskPriority.medium)
    due_date    = Column(Date)
    estimated_hours = Column(Float, default=0.0)
    actual_hours    = Column(Float, default=0.0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    project     = relationship("Project", back_populates="tasks")
    assignee    = relationship("Worker", back_populates="tasks")


class Attendance(TenantScoped, Base):
    __tablename__ = "attendance"

    id          = Column(Integer, primary_key=True, index=True)
    worker_id   = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"))
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=True)
    date        = Column(Date, nullable=False)
    check_in    = Column(String(10))
    check_out   = Column(String(10))
    hours_worked= Column(Float, default=0.0)
    is_present  = Column(Boolean, default=True)
    overtime_hours = Column(Float, default=0.0)
    notes       = Column(String(300))
    gps_lat     = Column(Float)      # GPS check-in location
    gps_lng     = Column(Float)

    worker      = relationship("Worker", back_populates="attendance")


# ══════════════════════════════════════════════════════════════════════════════
# FINANCE
# ══════════════════════════════════════════════════════════════════════════════

class Invoice(TenantScoped, Base):
    __tablename__ = "invoices"

    id           = Column(Integer, primary_key=True, index=True)
    invoice_no   = Column(String(50), unique=True, index=True)
    client_id    = Column(Integer, ForeignKey("clients.id"), nullable=True)
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    status       = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft)
    issue_date   = Column(Date)
    due_date     = Column(Date)
    subtotal     = Column(Money, default=0.0)
    tax_rate     = Column(Float, default=18.0)
    tax_amount   = Column(Money, default=0.0)
    total        = Column(Money, default=0.0)
    paid_amount  = Column(Money, default=0.0)
    currency     = Column(String(10), default="INR")
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    client       = relationship("Client", back_populates="invoices")
    project      = relationship("Project", back_populates="invoices")
    line_items   = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete")


class InvoiceItem(TenantScoped, Base):
    __tablename__ = "invoice_items"

    id          = Column(Integer, primary_key=True, index=True)
    invoice_id  = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"))
    description = Column(String(500), nullable=False)
    quantity    = Column(Float, default=1.0)
    unit        = Column(String(50), default="unit")
    rate        = Column(Money, default=0.0)
    amount      = Column(Money, default=0.0)

    invoice     = relationship("Invoice", back_populates="line_items")


class Expense(TenantScoped, Base):
    __tablename__ = "expenses"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    category    = Column(String(100))
    description = Column(String(500))
    amount      = Column(Money, default=0.0)
    date        = Column(Date)
    vendor      = Column(String(200))
    receipt_no  = Column(String(100))
    payment_mode= Column(String(50))    # cash, cheque, bank_transfer, card
    approved    = Column(Boolean, default=False)
    approved_by = Column(String(200))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    project     = relationship("Project", back_populates="expenses")


class InventoryItem(TenantScoped, Base):
    __tablename__ = "inventory"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(300), nullable=False)
    category     = Column(String(100))
    sku          = Column(String(100), unique=True)
    unit         = Column(String(50))
    quantity     = Column(Float, default=0.0)
    min_quantity = Column(Float, default=0.0)
    unit_cost    = Column(Money, default=0.0)
    supplier     = Column(String(200))
    location     = Column(String(200))
    notes        = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — SITE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

class SiteDiary(TenantScoped, Base):
    """Daily site diary / site report."""
    __tablename__ = "site_diaries"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    report_date     = Column(Date, nullable=False)
    prepared_by     = Column(String(200))
    weather_morning = Column(String(50))    # sunny, cloudy, rainy, windy
    weather_afternoon= Column(String(50))
    temperature_c   = Column(Float)
    humidity_pct    = Column(Float)
    total_workers   = Column(Integer, default=0)
    total_engineers = Column(Integer, default=0)
    work_done       = Column(Text)          # narrative of work done today
    material_used   = Column(Text)          # materials consumed today
    equipment_used  = Column(Text)          # plant & equipment on site
    visitors        = Column(Text)          # client/consultant/inspector visits
    instructions    = Column(Text)          # verbal/written instructions received
    delays          = Column(Text)          # delays encountered
    safety_notes    = Column(Text)
    remarks         = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="site_diaries")
    photos          = relationship("SitePhoto", back_populates="diary", cascade="all, delete")


class SitePhoto(TenantScoped, Base):
    __tablename__ = "site_photos"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    diary_id     = Column(Integer, ForeignKey("site_diaries.id", ondelete="CASCADE"), nullable=True)
    file_name    = Column(String(300))
    file_path    = Column(String(500))
    caption      = Column(String(500))
    location_tag = Column(String(200))   # Floor 5, Axis A-B
    gps_lat      = Column(Float)
    gps_lng      = Column(Float)
    photo_date   = Column(Date)
    taken_by     = Column(String(200))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    project      = relationship("Project")
    diary        = relationship("SiteDiary", back_populates="photos")


class Equipment(TenantScoped, Base):
    __tablename__ = "equipment"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(200), nullable=False)
    equipment_no    = Column(String(100), unique=True)
    category        = Column(String(100))    # crane, excavator, mixer, pump, generator, vehicle
    make            = Column(String(100))
    model           = Column(String(100))
    year            = Column(Integer)
    ownership       = Column(String(50))     # owned, hired, leased
    vendor          = Column(String(200))
    daily_hire_rate = Column(Float, default=0.0)
    fuel_type       = Column(String(50))     # diesel, petrol, electric
    capacity        = Column(String(100))
    last_service_date= Column(Date)
    next_service_date= Column(Date)
    insurance_expiry = Column(Date)
    is_active       = Column(Boolean, default=True)
    project_id      = Column(Integer, ForeignKey("projects.id"), nullable=True)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    fuel_logs       = relationship("FuelLog", back_populates="equipment", cascade="all, delete")


class FuelLog(TenantScoped, Base):
    __tablename__ = "fuel_logs"

    id           = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"))
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    log_date     = Column(Date, nullable=False)
    fuel_type    = Column(String(50))
    liters       = Column(Float, default=0.0)
    rate_per_ltr = Column(Float, default=0.0)
    cost         = Column(Float, default=0.0)
    meter_reading= Column(Float, default=0.0)
    hours_worked = Column(Float, default=0.0)
    filled_by    = Column(String(200))
    notes        = Column(String(300))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    equipment    = relationship("Equipment", back_populates="fuel_logs")


class MaterialConsumption(TenantScoped, Base):
    __tablename__ = "material_consumption"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    item_id      = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    log_date     = Column(Date, nullable=False)
    material     = Column(String(200))
    quantity     = Column(Float, default=0.0)
    unit         = Column(String(50))
    location_used= Column(String(200))   # Floor/axis/element
    purpose      = Column(String(300))
    issued_by    = Column(String(200))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — QUALITY CONTROL
# ══════════════════════════════════════════════════════════════════════════════

class MaterialTest(TenantScoped, Base):
    """Concrete cube, slump, rebar tensile, aggregate tests."""
    __tablename__ = "material_tests"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    test_type       = Column(String(50))    # cube_compressive, slump, rebar_tensile, aggregate_gradation, water_absorption
    test_date       = Column(Date, nullable=False)
    element         = Column(String(200))   # Column C1, Slab Floor 3...
    pour_reference  = Column(String(100))   # Pour Pour-23, Batch B-12
    design_code     = Column(String(20), default="IS")
    # Concrete cube test (IS 516 / EN 12390 / ASTM C39)
    grade           = Column(String(20))    # M25, C25, fc'=25MPa
    sample_no       = Column(String(50))
    cube_size_mm    = Column(Integer, default=150)  # 150 or 100mm
    water_cement_ratio = Column(Float)
    slump_mm        = Column(Float)         # slump at pour
    # Cube strengths (3 cubes typically)
    cube1_7day_kN   = Column(Float)
    cube2_7day_kN   = Column(Float)
    cube3_7day_kN   = Column(Float)
    avg_7day_kN     = Column(Float)
    cube1_28day_kN  = Column(Float)
    cube2_28day_kN  = Column(Float)
    cube3_28day_kN  = Column(Float)
    avg_28day_kN    = Column(Float)
    fck_achieved_MPa= Column(Float)
    result          = Column(Enum(TestResult), default=TestResult.pending)
    # Rebar test (IS 1786 / ASTM A615)
    rebar_dia_mm    = Column(Integer)
    yield_strength_MPa = Column(Float)
    uts_MPa         = Column(Float)
    elongation_pct  = Column(Float)
    # Lab info
    lab_name        = Column(String(200))
    tested_by       = Column(String(200))
    witnessed_by    = Column(String(200))
    certificate_no  = Column(String(100))
    remarks         = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="material_tests")


class QCInspection(TenantScoped, Base):
    """Quality inspection with checklist."""
    __tablename__ = "qc_inspections"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    inspection_no   = Column(String(50), unique=True)
    inspection_type = Column(String(100))   # RFI, ITP, pre-pour, rebar, formwork, concrete_finish, brickwork
    element         = Column(String(200))
    floor_level     = Column(String(100))
    inspection_date = Column(Date)
    inspector_name  = Column(String(200))
    contractor_rep  = Column(String(200))
    consultant_rep  = Column(String(200))
    result          = Column(Enum(TestResult), default=TestResult.pending)
    overall_remarks = Column(Text)
    next_action     = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="qc_inspections")
    checklist_items = relationship("QCChecklistItem", back_populates="inspection", cascade="all, delete")


class QCChecklistItem(TenantScoped, Base):
    __tablename__ = "qc_checklist_items"

    id              = Column(Integer, primary_key=True, index=True)
    inspection_id   = Column(Integer, ForeignKey("qc_inspections.id", ondelete="CASCADE"))
    item_no         = Column(String(10))
    check_point     = Column(String(500))
    reference       = Column(String(100))   # IS 456 Cl. 12.1 / ACI 318 Sec 7
    requirement     = Column(String(300))
    actual          = Column(String(300))
    status          = Column(String(20), default="pending")  # pass, fail, na, pending
    remarks         = Column(String(300))

    inspection      = relationship("QCInspection", back_populates="checklist_items")


class NCReport(TenantScoped, Base):
    """Non-Conformance Report."""
    __tablename__ = "nc_reports"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    ncr_no          = Column(String(50), unique=True)
    title           = Column(String(300), nullable=False)
    description     = Column(Text)
    element         = Column(String(200))
    floor_level     = Column(String(100))
    nc_date         = Column(Date)
    raised_by       = Column(String(200))
    assigned_to     = Column(String(200))
    severity        = Column(Enum(IncidentSeverity), default=IncidentSeverity.medium)
    root_cause      = Column(Text)
    immediate_action= Column(Text)
    corrective_action= Column(Text)   # CAPA
    preventive_action= Column(Text)
    due_date        = Column(Date)
    closed_date     = Column(Date)
    status          = Column(String(50), default="open")   # open, under_review, closed, rejected
    cost_of_nc      = Column(Float, default=0.0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="ncrs")


class PunchListItem(TenantScoped, Base):
    """Snag list / punch list item."""
    __tablename__ = "punch_list"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    item_no      = Column(String(20))
    description  = Column(String(500), nullable=False)
    location     = Column(String(200))
    raised_by    = Column(String(200))
    assigned_to  = Column(String(200))
    raised_date  = Column(Date)
    due_date     = Column(Date)
    closed_date  = Column(Date)
    status       = Column(String(50), default="open")  # open, in_progress, closed
    priority     = Column(Enum(TaskPriority), default=TaskPriority.medium)
    photo_path   = Column(String(500))
    remarks      = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — SAFETY (enhanced)
# ══════════════════════════════════════════════════════════════════════════════

class SafetyIncident(TenantScoped, Base):
    __tablename__ = "safety_incidents"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    incident_no  = Column(String(50))
    title        = Column(String(300), nullable=False)
    description  = Column(Text)
    incident_type= Column(String(100), default="incident")   # incident, near_miss, unsafe_act, unsafe_condition
    severity     = Column(Enum(IncidentSeverity), default=IncidentSeverity.low)
    incident_date= Column(Date)
    time_of_incident = Column(String(10))
    location     = Column(String(300))
    involved_workers = Column(Text)
    injuries     = Column(Boolean, default=False)
    injury_details = Column(Text)
    lost_time_days = Column(Float, default=0.0)
    resolved     = Column(Boolean, default=False)
    corrective_action = Column(Text)
    reported_by  = Column(String(200))
    investigated_by = Column(String(200))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class SafetyInspection(TenantScoped, Base):
    __tablename__ = "safety_inspections"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title        = Column(String(300), nullable=False)
    inspector    = Column(String(200))
    inspection_date = Column(Date)
    passed       = Column(Boolean, default=True)
    findings     = Column(Text)
    recommendations = Column(Text)
    next_inspection = Column(Date)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class ToolboxTalk(TenantScoped, Base):
    __tablename__ = "toolbox_talks"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    topic        = Column(String(300), nullable=False)
    talk_date    = Column(Date, nullable=False)
    conducted_by = Column(String(200))
    location     = Column(String(200))
    duration_min = Column(Integer, default=15)
    attendees_count = Column(Integer, default=0)
    attendees    = Column(Text)      # comma-separated names or JSON
    key_points   = Column(Text)
    remarks      = Column(Text)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    project      = relationship("Project", back_populates="toolbox_talks")


class PermitToWork(TenantScoped, Base):
    """Permit to Work (PTW) — hot work, confined space, height work, excavation."""
    __tablename__ = "permits_to_work"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    permit_no       = Column(String(50), unique=True)
    permit_type     = Column(String(100))    # hot_work, confined_space, height_work, excavation, electrical, radiography
    title           = Column(String(300))
    location        = Column(String(200))
    scope_of_work   = Column(Text)
    requested_by    = Column(String(200))
    contractor      = Column(String(200))
    workers_involved = Column(Text)
    start_datetime  = Column(DateTime(timezone=True))
    end_datetime    = Column(DateTime(timezone=True))
    precautions     = Column(Text)
    equipment_required = Column(Text)
    ppe_required    = Column(Text)
    issued_by       = Column(String(200))
    approved_by     = Column(String(200))
    status          = Column(String(50), default="pending")   # pending, approved, active, closed, cancelled
    closed_by       = Column(String(200))
    closed_at       = Column(DateTime(timezone=True))
    remarks         = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="permits")


class RiskAssessment(TenantScoped, Base):
    __tablename__ = "risk_assessments"

    id              = Column(Integer, primary_key=True, index=True)
    project_id      = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    activity        = Column(String(300), nullable=False)
    hazard          = Column(String(300))
    risk_description= Column(Text)
    likelihood      = Column(Integer, default=3)    # 1-5
    severity_score  = Column(Integer, default=3)    # 1-5
    risk_score      = Column(Integer, default=9)    # likelihood × severity
    risk_level      = Column(Enum(RiskLevel), default=RiskLevel.medium)
    control_measures= Column(Text)
    residual_risk   = Column(Integer, default=4)
    responsible     = Column(String(200))
    review_date     = Column(Date)
    status          = Column(String(50), default="open")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    project         = relationship("Project", back_populates="risk_assessments")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — SCHEDULING (CPM / EVM)
# ══════════════════════════════════════════════════════════════════════════════

class Activity(TenantScoped, Base):
    __tablename__ = "activities"

    id               = Column(Integer, primary_key=True, index=True)
    project_id       = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name             = Column(String(300), nullable=False)
    description      = Column(Text)
    wbs_code         = Column(String(50))
    duration_days    = Column(Float, default=1.0)
    cost_budget      = Column(Float, default=0.0)
    predecessors     = Column(JSON, default=list)
    early_start      = Column(Float, default=0.0)
    early_finish     = Column(Float, default=0.0)
    late_start       = Column(Float, default=0.0)
    late_finish      = Column(Float, default=0.0)
    total_float      = Column(Float, default=0.0)
    free_float       = Column(Float, default=0.0)
    is_critical      = Column(Boolean, default=False)
    actual_start     = Column(Date, nullable=True)
    actual_finish    = Column(Date, nullable=True)
    percent_complete = Column(Float, default=0.0)
    actual_cost      = Column(Money, default=0.0)
    resource_id      = Column(Integer, ForeignKey("workers.id"), nullable=True)
    baseline_start   = Column(Float)
    baseline_finish  = Column(Float)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    project          = relationship("Project")


class EVMSnapshot(TenantScoped, Base):
    __tablename__ = "evm_snapshots"

    id            = Column(Integer, primary_key=True, index=True)
    project_id    = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    bac           = Column(Float, default=0.0)
    pv            = Column(Float, default=0.0)
    ev            = Column(Float, default=0.0)
    ac            = Column(Float, default=0.0)
    notes         = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    project       = relationship("Project")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10 — BIM (Building Information Modelling)
# ══════════════════════════════════════════════════════════════════════════════

class BIMModel(TenantScoped, Base):
    """Represents an uploaded / created building model."""
    __tablename__ = "bim_models"

    id           = Column(Integer, primary_key=True, index=True)
    project_id   = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name         = Column(String(300), nullable=False)
    description  = Column(Text)
    version      = Column(String(20), default="1.0")
    file_path    = Column(String(500))
    file_format  = Column(String(20), default="json")   # json | ifc
    total_floors = Column(Integer, default=1)
    building_height_m = Column(Float, default=0.0)
    gross_area_m2     = Column(Float, default=0.0)
    coordinate_system = Column(String(50), default="WCS")
    created_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    project      = relationship("Project")
    elements     = relationship("BIMElement", back_populates="model", cascade="all, delete-orphan")


class BIMElement(TenantScoped, Base):
    """Individual building element (Wall, Slab, Column, Beam, Door, Window...)."""
    __tablename__ = "bim_elements"

    id           = Column(Integer, primary_key=True, index=True)
    model_id     = Column(Integer, ForeignKey("bim_models.id", ondelete="CASCADE"), nullable=False)
    ifc_guid     = Column(String(50), index=True)
    element_type = Column(String(50), nullable=False)
    name         = Column(String(200))
    level        = Column(String(100), default="Ground Floor")
    floor_number = Column(Integer, default=0)
    material     = Column(String(100))
    pos_x        = Column(Float, default=0.0)
    pos_y        = Column(Float, default=0.0)
    pos_z        = Column(Float, default=0.0)
    length_m     = Column(Float, default=0.0)
    width_m      = Column(Float, default=0.0)
    height_m     = Column(Float, default=0.0)
    rotation_deg = Column(Float, default=0.0)
    volume_m3    = Column(Float, default=0.0)
    area_m2      = Column(Float, default=0.0)
    omniclass    = Column(String(50))
    mark         = Column(String(100))
    properties   = Column(JSON, default=dict)
    status       = Column(String(30), default="design")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    model        = relationship("BIMModel", back_populates="elements")


class ClashDetection(TenantScoped, Base):
    """Clash between two BIM elements."""
    __tablename__ = "bim_clashes"

    id           = Column(Integer, primary_key=True, index=True)
    model_id     = Column(Integer, ForeignKey("bim_models.id", ondelete="CASCADE"), nullable=False)
    element_a_id = Column(Integer, ForeignKey("bim_elements.id"), nullable=False)
    element_b_id = Column(Integer, ForeignKey("bim_elements.id"), nullable=False)
    clash_type   = Column(String(30), default="hard")
    severity     = Column(String(20), default="major")
    status       = Column(String(20), default="open")
    description  = Column(Text)
    detected_at  = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at  = Column(DateTime(timezone=True), nullable=True)
    resolved_by  = Column(Integer, ForeignKey("users.id"), nullable=True)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 13 — MULTI-TENANT SaaS
# ══════════════════════════════════════════════════════════════════════════════

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), unique=True, nullable=False)
    display_name    = Column(String(200))
    price_monthly   = Column(Float, default=0.0)
    price_annual    = Column(Float, default=0.0)
    max_users       = Column(Integer, default=5)
    max_projects    = Column(Integer, default=3)
    max_storage_gb  = Column(Float, default=1.0)
    features        = Column(JSON, default=list)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    tenants         = relationship("TenantSubscription", back_populates="plan")


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id              = Column(Integer, primary_key=True, index=True)
    company_id      = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id         = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    status          = Column(String(30), default="trial")
    trial_ends      = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), server_default=func.now())
    current_period_end   = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id   = Column(String(200), nullable=True)
    stripe_subscription_id = Column(String(200), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    plan            = relationship("SubscriptionPlan", back_populates="tenants")


class TenantUsage(Base):
    __tablename__ = "tenant_usage"

    id              = Column(Integer, primary_key=True, index=True)
    company_id      = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    period_month    = Column(String(7), nullable=False)
    active_users    = Column(Integer, default=0)
    project_count   = Column(Integer, default=0)
    storage_used_gb = Column(Float, default=0.0)
    api_calls       = Column(BigInteger, default=0)
    documents_count = Column(Integer, default=0)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    id              = Column(Integer, primary_key=True, index=True)
    company_id      = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_color   = Column(String(20), default="#2563eb")
    secondary_color = Column(String(20), default="#1e40af")
    logo_url        = Column(String(500), nullable=True)
    app_name        = Column(String(200), default="NagaForge")
    feature_flags   = Column(JSON, default=dict)
    custom_domain   = Column(String(300), nullable=True)
    timezone        = Column(String(100), default="Asia/Kolkata")
    locale          = Column(String(20), default="en-IN")
    currency        = Column(String(10), default="INR")
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
