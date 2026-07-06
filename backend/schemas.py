from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from models import (
    ProjectStatus, TaskStatus, TaskPriority, WorkerRole,
    WorkerStatus, InvoiceStatus, IncidentSeverity
)


# ── Client ────────────────────────────────────────────────────────────────────

class ClientBase(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "India"
    notes: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    name: Optional[str] = None

class ClientOut(ClientBase):
    id: int
    is_active: bool
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    client_id: Optional[int] = None
    status: Optional[ProjectStatus] = ProjectStatus.planning
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[float] = Field(0.0, ge=0)
    location: Optional[str] = None
    project_type: Optional[str] = None
    progress: Optional[int] = Field(0, ge=0, le=100)

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None

class ProjectOut(ProjectBase):
    id: int
    spent: float
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Worker ────────────────────────────────────────────────────────────────────

class WorkerBase(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: WorkerRole
    status: Optional[WorkerStatus] = WorkerStatus.active
    daily_rate: Optional[float] = 0.0
    skills: Optional[str] = None
    certifications: Optional[str] = None
    hire_date: Optional[date] = None
    emergency_contact: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

class WorkerCreate(WorkerBase):
    pass

class WorkerUpdate(WorkerBase):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[WorkerRole] = None

class WorkerOut(WorkerBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskBase(BaseModel):
    project_id: int
    assignee_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = TaskStatus.todo
    priority: Optional[TaskPriority] = TaskPriority.medium
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = 0.0
    actual_hours: Optional[float] = 0.0

class TaskCreate(TaskBase):
    pass

class TaskUpdate(TaskBase):
    project_id: Optional[int] = None
    title: Optional[str] = None

class TaskOut(TaskBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceBase(BaseModel):
    worker_id: int
    date: date
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    hours_worked: Optional[float] = 0.0
    is_present: Optional[bool] = True
    notes: Optional[str] = None

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceOut(AttendanceBase):
    id: int
    class Config:
        from_attributes = True


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceItemBase(BaseModel):
    description: str
    quantity: float = Field(1.0, ge=0)
    unit: Optional[str] = "unit"
    rate: float = Field(..., ge=0)
    amount: Optional[float] = Field(None, ge=0)

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemOut(InvoiceItemBase):
    id: int
    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    invoice_no: Optional[str] = None
    client_id: Optional[int] = None
    project_id: Optional[int] = None
    status: Optional[InvoiceStatus] = InvoiceStatus.draft
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    tax_rate: Optional[float] = Field(18.0, ge=0, le=100)
    notes: Optional[str] = None

class InvoiceCreate(InvoiceBase):
    line_items: List[InvoiceItemCreate] = []

class InvoiceUpdate(InvoiceBase):
    pass

class InvoiceOut(InvoiceBase):
    id: int
    subtotal: float
    tax_amount: float
    total: float
    paid_amount: float
    created_at: Optional[datetime]
    line_items: List[InvoiceItemOut] = []
    class Config:
        from_attributes = True


# ── Expense ───────────────────────────────────────────────────────────────────

class ExpenseBase(BaseModel):
    project_id: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    amount: float = Field(..., ge=0)
    date: Optional[date] = None
    vendor: Optional[str] = None
    receipt_no: Optional[str] = None
    approved: Optional[bool] = False

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseOut(ExpenseBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Document ──────────────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    project_id: Optional[int] = None
    title: str
    doc_type: Optional[str] = None
    file_name: Optional[str] = None
    version: Optional[str] = "1.0"
    description: Optional[str] = None
    uploaded_by: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentOut(DocumentBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Inventory ─────────────────────────────────────────────────────────────────

class InventoryBase(BaseModel):
    name: str
    category: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = 0.0
    min_quantity: Optional[float] = 0.0
    unit_cost: Optional[float] = 0.0
    supplier: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(InventoryBase):
    name: Optional[str] = None

class InventoryOut(InventoryBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Safety ────────────────────────────────────────────────────────────────────

class IncidentBase(BaseModel):
    project_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    severity: Optional[IncidentSeverity] = IncidentSeverity.low
    incident_date: Optional[date] = None
    location: Optional[str] = None
    involved_workers: Optional[str] = None
    injuries: Optional[bool] = False
    resolved: Optional[bool] = False
    corrective_action: Optional[str] = None
    reported_by: Optional[str] = None

class IncidentCreate(IncidentBase):
    pass

class IncidentOut(IncidentBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True

class InspectionBase(BaseModel):
    project_id: Optional[int] = None
    title: str
    inspector: Optional[str] = None
    inspection_date: Optional[date] = None
    passed: Optional[bool] = True
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    next_inspection: Optional[date] = None

class InspectionCreate(InspectionBase):
    pass

class InspectionOut(InspectionBase):
    id: int
    created_at: Optional[datetime]
    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_projects: int
    active_projects: int
    total_workers: int
    active_workers: int
    total_clients: int
    total_revenue: float
    total_expenses: float
    pending_invoices: float
    low_stock_items: int
    open_incidents: int
    projects_by_status: dict
    monthly_expenses: list
    top_projects: list
