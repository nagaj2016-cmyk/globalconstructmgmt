"""
Demo data router — LOAD and DELETE demo data.

Hard rules:
- Only the demo account (is_demo flag, or username == settings.DEMO_USERNAME) may
  call these endpoints. Everyone else gets 403.
- All demo rows live in the dedicated demo company and are flagged is_demo=True,
  so no other tenant can ever see them (enforced by tenancy.py) and reset only
  ever removes demo rows.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from config import settings
from tenancy import TenantScoped
import models

router = APIRouter(prefix="/demo-data", tags=["Demo"])


def require_demo_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    is_demo = bool(getattr(current_user, "is_demo", False)) or \
        current_user.username == settings.DEMO_USERNAME
    if not is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demo data controls are only available to the demo account.",
        )
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="Demo account has no workspace assigned.")
    return current_user


def _tenant_models():
    for cls in models.Base.registry._class_registry.values():
        if isinstance(cls, type) and issubclass(cls, TenantScoped) and hasattr(cls, "__table__"):
            yield cls


@router.get("/status")
def demo_status(user: models.User = Depends(require_demo_user), db: Session = Depends(get_db)):
    n = db.query(models.Project).count()  # already tenant-filtered to demo
    return {"loaded": n > 0, "projects": n, "company_id": user.company_id}


@router.post("/reset")
def reset_demo(user: models.User = Depends(require_demo_user), db: Session = Depends(get_db)):
    """Delete ALL demo rows for the demo company only.

    Deletes in REVERSE foreign-key dependency order (children before parents) so
    PostgreSQL's FK constraints are satisfied — SQLite doesn't enforce them, but
    Postgres does, and arbitrary order raises a foreign-key violation."""
    cid = user.company_id
    removed = 0
    tenant_by_table = {cls.__tablename__: cls for cls in _tenant_models()}
    for table in reversed(models.Base.metadata.sorted_tables):
        cls = tenant_by_table.get(table.name)
        if cls is None:
            continue
        removed += (db.query(cls).filter(cls.company_id == cid)
                    .execution_options(skip_tenant=True)
                    .delete(synchronize_session=False))
    db.commit()
    return {"ok": True, "deleted_rows": removed}


@router.post("/load")
def load_demo(user: models.User = Depends(require_demo_user), db: Session = Depends(get_db)):
    """Populate the demo workspace with a coherent multi-module dataset.

    company_id + is_demo are stamped automatically by the tenancy layer, but we
    also set them explicitly here for clarity and safety."""
    cid = user.company_id
    if db.query(models.Project).count() > 0:
        return {"ok": True, "message": "Demo data already loaded.", "reloaded": False}

    def demo(obj):
        obj.company_id = cid
        obj.is_demo = True
        db.add(obj)
        return obj

    today = date.today()

    # Clients
    c1 = demo(models.Client(name="Skyline Developments", company="Skyline Developments Ltd",
                            email="contact@skyline.demo", phone="+1 555 0100",
                            city="Toronto", country="Canada"))
    c2 = demo(models.Client(name="Harbour Industrial", company="Harbour Industrial Inc",
                            email="ops@harbour.demo", phone="+1 555 0200",
                            city="Vancouver", country="Canada"))
    db.flush()

    # Projects
    p1 = demo(models.Project(name="Riverside Tower — 18 Storey", project_code="DEMO-RT-01",
                             description="Reinforced-concrete residential tower.",
                             client_id=c1.id, status="active", start_date=today - timedelta(days=120),
                             end_date=today + timedelta(days=300), budget=42_000_000, spent=15_800_000,
                             contracted_value=45_000_000, location="Toronto, ON", country="Canada",
                             design_code="CSA A23.3", project_type="Residential", progress=38))
    p2 = demo(models.Project(name="Harbour Logistics Hub", project_code="DEMO-HL-02",
                             description="Steel-framed distribution warehouse.",
                             client_id=c2.id, status="active", start_date=today - timedelta(days=60),
                             end_date=today + timedelta(days=210), budget=27_500_000, spent=6_200_000,
                             contracted_value=29_000_000, location="Vancouver, BC", country="Canada",
                             design_code="CSA S16", project_type="Industrial", progress=21))
    db.flush()

    # Workers
    roles = ["engineer", "site_manager", "foreman", "safety_officer", "mason", "electrician"]
    for i, (fn, ln) in enumerate([("Amara", "Okafor"), ("David", "Chen"), ("Priya", "Nair"),
                                  ("Liam", "Murphy"), ("Sofia", "Rossi"), ("Omar", "Haddad")]):
        demo(models.Worker(first_name=fn, last_name=ln, employee_id=f"DEMO-W{i+1:02d}",
                           role=roles[i], status="active", daily_rate=280 + i * 20,
                           phone=f"+1 555 03{i:02d}", nationality="Canada"))

    # Tasks
    for pid, title, st, pr in [
        (p1.id, "Column schedule — Level 5", "in_progress", "high"),
        (p1.id, "Formwork inspection — core wall", "todo", "high"),
        (p1.id, "Concrete pour sign-off — L4 slab", "review", "medium"),
        (p2.id, "Steel connection shop drawings", "in_progress", "high"),
        (p2.id, "Foundation bolt layout QA", "todo", "medium"),
    ]:
        demo(models.Task(project_id=pid, title=title, status=st, priority=pr,
                        due_date=today + timedelta(days=14)))

    # Invoices
    demo(models.Invoice(invoice_no="DEMO-INV-1001", client_id=c1.id, project_id=p1.id,
                        status="sent", issue_date=today - timedelta(days=20),
                        due_date=today + timedelta(days=10), subtotal=2_400_000, tax_rate=13,
                        tax_amount=312_000, total=2_712_000, paid_amount=0, currency="CAD"))
    demo(models.Invoice(invoice_no="DEMO-INV-1002", client_id=c2.id, project_id=p2.id,
                        status="paid", issue_date=today - timedelta(days=45),
                        due_date=today - timedelta(days=15), subtotal=1_100_000, tax_rate=13,
                        tax_amount=143_000, total=1_243_000, paid_amount=1_243_000, currency="CAD"))

    # Expenses
    for pid, cat, desc, amt in [
        (p1.id, "Materials", "Ready-mix concrete — L4", 186_000),
        (p1.id, "Labour", "Rebar fixing crew", 92_000),
        (p2.id, "Equipment", "Crawler crane rental", 74_000),
    ]:
        demo(models.Expense(project_id=pid, category=cat, description=desc, amount=amt,
                          date=today - timedelta(days=7), approved=True))

    # Inventory
    for name, cat, qty, unit, cost in [
        ("Rebar 16mm Fe500", "Steel", 42, "tonne", 950),
        ("Portland Cement OPC-53", "Cement", 1800, "bag", 9.5),
        ("Plywood shuttering 18mm", "Formwork", 260, "sheet", 38),
    ]:
        demo(models.InventoryItem(name=name, category=cat, quantity=qty, unit=unit, unit_cost=cost))

    # Documents
    demo(models.Document(project_id=p1.id, title="Structural GA — Tower core", doc_type="Drawing",
                        approval_status="approved", version="B"))
    demo(models.Document(project_id=p2.id, title="Steel design basis report", doc_type="Report",
                        approval_status="pending", version="A"))

    # Safety + QC
    demo(models.SafetyIncident(project_id=p1.id, incident_no="DEMO-SI-01",
                              title="Near-miss: falling formwork clamp", severity="medium",
                              incident_date=today - timedelta(days=9), resolved=True,
                              corrective_action="Toolbox talk + exclusion zone reinforced."))
    demo(models.QCInspection(project_id=p1.id, inspection_no="DEMO-QC-01",
                            inspection_type="Concrete", element="L4 Slab", result="pass",
                            inspection_date=today - timedelta(days=5),
                            inspector_name="Priya Nair"))

    # Site diary
    demo(models.SiteDiary(project_id=p1.id, report_date=today - timedelta(days=1)))

    db.commit()
    return {"ok": True, "message": "Demo data loaded into the demo workspace.",
            "reloaded": True, "projects": 2}
