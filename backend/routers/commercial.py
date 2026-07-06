"""
Commercial Module — Phase 2
BOQ, Rate Analysis, Vendors, Purchase Orders, Contracts, Budget
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
from database import get_db
import models

router = APIRouter(prefix="/commercial", tags=["Commercial"])


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class BOQItemCreate(BaseModel):
    project_id: int
    item_no: Optional[str] = None
    description: str
    unit: Optional[str] = None
    quantity: float = 0.0
    unit_rate: float = 0.0
    category: Optional[str] = None
    specification: Optional[str] = None
    remarks: Optional[str] = None
    is_provisional: bool = False

class RateAnalysisCreate(BaseModel):
    item_code: str
    description: str
    unit: Optional[str] = None
    labour_cost: float = 0.0
    material_cost: float = 0.0
    equipment_cost: float = 0.0
    overhead_pct: float = 15.0
    profit_pct: float = 10.0
    country: str = "IN"
    state: Optional[str] = None
    year: Optional[int] = None
    notes: Optional[str] = None

class VendorCreate(BaseModel):
    name: str
    category: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: int = 30
    notes: Optional[str] = None

class POItemCreate(BaseModel):
    description: str
    unit: Optional[str] = None
    quantity: float = 0.0
    unit_rate: float = 0.0
    remarks: Optional[str] = None

class POCreate(BaseModel):
    po_number: str
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    po_date: Optional[date] = None
    delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    terms: Optional[str] = None
    notes: Optional[str] = None
    items: List[POItemCreate] = []

class ContractCreate(BaseModel):
    project_id: int
    contractor_id: Optional[int] = None
    consultant_id: Optional[int] = None
    contract_no: str
    contract_type: str = "lump_sum"
    scope: Optional[str] = None
    contract_value: float = 0.0
    retention_pct: float = 5.0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class BudgetItemCreate(BaseModel):
    category: str
    description: Optional[str] = None
    budgeted_cost: float = 0.0

class BudgetCreate(BaseModel):
    project_id: int
    name: str
    items: List[BudgetItemCreate] = []


# ══════════════════════════════════════════════════════════════════════════════
# BOQ
# ══════════════════════════════════════════════════════════════════════════════

def _boq_dict(b):
    return {"id": b.id, "project_id": b.project_id, "item_no": b.item_no,
            "description": b.description, "unit": b.unit, "quantity": b.quantity,
            "unit_rate": b.unit_rate, "amount": b.amount, "category": b.category,
            "specification": b.specification, "remarks": b.remarks,
            "is_provisional": b.is_provisional}

@router.get("/boq/{project_id}")
def get_boq(project_id: int, db: Session = Depends(get_db)):
    items = db.query(models.BOQItem).filter(
        models.BOQItem.project_id == project_id
    ).order_by(models.BOQItem.item_no).all()
    total = sum(i.amount for i in items)
    return {"items": [_boq_dict(i) for i in items], "total": total,
            "count": len(items)}

@router.post("/boq", status_code=201)
def create_boq_item(data: BOQItemCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    d["amount"] = d["quantity"] * d["unit_rate"]
    item = models.BOQItem(**d)
    db.add(item); db.commit(); db.refresh(item)
    return _boq_dict(item)

@router.put("/boq/{item_id}")
def update_boq_item(item_id: int, data: BOQItemCreate, db: Session = Depends(get_db)):
    item = db.query(models.BOQItem).filter(models.BOQItem.id == item_id).first()
    if not item: raise HTTPException(404, "Not found")
    d = data.model_dump(exclude_none=True)
    d["amount"] = d.get("quantity", item.quantity) * d.get("unit_rate", item.unit_rate)
    for k, v in d.items(): setattr(item, k, v)
    db.commit(); return _boq_dict(item)

@router.delete("/boq/{item_id}")
def delete_boq_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.BOQItem).filter(models.BOQItem.id == item_id).first()
    if not item: raise HTTPException(404, "Not found")
    db.delete(item); db.commit(); return {"message": "Deleted"}

@router.get("/boq/{project_id}/summary")
def boq_summary(project_id: int, db: Session = Depends(get_db)):
    """BOQ summary grouped by category with subtotals."""
    items = db.query(models.BOQItem).filter(models.BOQItem.project_id == project_id).all()
    summary = {}
    for item in items:
        cat = item.category or "General"
        if cat not in summary:
            summary[cat] = {"category": cat, "items": 0, "amount": 0.0}
        summary[cat]["items"] += 1
        summary[cat]["amount"] += item.amount
    return {
        "categories": list(summary.values()),
        "total": sum(i.amount for i in items),
        "provisional": sum(i.amount for i in items if i.is_provisional),
        "firm": sum(i.amount for i in items if not i.is_provisional),
    }


# ══════════════════════════════════════════════════════════════════════════════
# RATE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _calc_rate(r):
    direct = r.labour_cost + r.material_cost + r.equipment_cost
    overhead = direct * r.overhead_pct / 100
    profit = (direct + overhead) * r.profit_pct / 100
    return round(direct + overhead + profit, 2)

@router.get("/rates")
def list_rates(country: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.RateAnalysis)
    if country: q = q.filter(models.RateAnalysis.country == country)
    return [{"id": r.id, "item_code": r.item_code, "description": r.description,
             "unit": r.unit, "labour_cost": r.labour_cost, "material_cost": r.material_cost,
             "equipment_cost": r.equipment_cost, "overhead_pct": r.overhead_pct,
             "profit_pct": r.profit_pct, "total_rate": r.total_rate,
             "country": r.country, "state": r.state, "year": r.year}
            for r in q.all()]

@router.post("/rates", status_code=201)
def create_rate(data: RateAnalysisCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    direct = d["labour_cost"] + d["material_cost"] + d["equipment_cost"]
    overhead = direct * d["overhead_pct"] / 100
    profit = (direct + overhead) * d["profit_pct"] / 100
    d["total_rate"] = round(direct + overhead + profit, 2)
    r = models.RateAnalysis(**d)
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "item_code": r.item_code, "total_rate": r.total_rate}

@router.delete("/rates/{rid}")
def delete_rate(rid: int, db: Session = Depends(get_db)):
    r = db.query(models.RateAnalysis).filter(models.RateAnalysis.id == rid).first()
    if not r: raise HTTPException(404, "Not found")
    db.delete(r); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# VENDORS
# ══════════════════════════════════════════════════════════════════════════════

def _vendor_dict(v):
    return {"id": v.id, "name": v.name, "category": v.category,
            "contact_person": v.contact_person, "email": v.email,
            "phone": v.phone, "city": v.city, "country": v.country,
            "tax_id": v.tax_id, "payment_terms": v.payment_terms,
            "rating": v.rating, "approved": v.approved, "is_active": v.is_active}

@router.get("/vendors")
def list_vendors(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Vendor)
    if category: q = q.filter(models.Vendor.category == category)
    return [_vendor_dict(v) for v in q.order_by(models.Vendor.name).all()]

@router.post("/vendors", status_code=201)
def create_vendor(data: VendorCreate, db: Session = Depends(get_db)):
    v = models.Vendor(**data.model_dump())
    db.add(v); db.commit(); db.refresh(v)
    return _vendor_dict(v)

@router.put("/vendors/{vid}")
def update_vendor(vid: int, data: VendorCreate, db: Session = Depends(get_db)):
    v = db.query(models.Vendor).filter(models.Vendor.id == vid).first()
    if not v: raise HTTPException(404, "Not found")
    for k, val in data.model_dump(exclude_none=True).items(): setattr(v, k, val)
    db.commit(); return _vendor_dict(v)

@router.post("/vendors/{vid}/approve")
def approve_vendor(vid: int, db: Session = Depends(get_db)):
    v = db.query(models.Vendor).filter(models.Vendor.id == vid).first()
    if not v: raise HTTPException(404, "Not found")
    v.approved = True; db.commit()
    return {"message": "Vendor approved"}

@router.delete("/vendors/{vid}")
def delete_vendor(vid: int, db: Session = Depends(get_db)):
    v = db.query(models.Vendor).filter(models.Vendor.id == vid).first()
    if not v: raise HTTPException(404, "Not found")
    db.delete(v); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# PURCHASE ORDERS
# ══════════════════════════════════════════════════════════════════════════════

def _po_dict(po, with_items=True):
    d = {"id": po.id, "po_number": po.po_number, "project_id": po.project_id,
         "vendor_id": po.vendor_id, "status": po.status,
         "po_date": str(po.po_date) if po.po_date else None,
         "delivery_date": str(po.delivery_date) if po.delivery_date else None,
         "subtotal": po.subtotal, "tax_amount": po.tax_amount, "total": po.total,
         "notes": po.notes, "approved_by": po.approved_by}
    if with_items and po.items:
        d["items"] = [{"id": i.id, "description": i.description, "unit": i.unit,
                        "quantity": i.quantity, "unit_rate": i.unit_rate,
                        "amount": i.amount, "received_qty": i.received_qty}
                       for i in po.items]
    return d

@router.get("/po")
def list_pos(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.PurchaseOrder)
    if project_id: q = q.filter(models.PurchaseOrder.project_id == project_id)
    return [_po_dict(p, with_items=False) for p in q.order_by(models.PurchaseOrder.id.desc()).all()]

@router.get("/po/{po_id}")
def get_po(po_id: int, db: Session = Depends(get_db)):
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404, "PO not found")
    return _po_dict(po, with_items=True)

@router.post("/po", status_code=201)
def create_po(data: POCreate, db: Session = Depends(get_db)):
    d = data.model_dump(exclude={"items"})
    po = models.PurchaseOrder(**d)
    db.add(po); db.flush()

    subtotal = 0.0
    for item_data in data.items:
        item = models.POItem(
            po_id=po.id,
            description=item_data.description,
            unit=item_data.unit,
            quantity=item_data.quantity,
            unit_rate=item_data.unit_rate,
            amount=item_data.quantity * item_data.unit_rate,
            remarks=item_data.remarks,
        )
        subtotal += item.amount
        db.add(item)

    po.subtotal = subtotal
    po.tax_amount = round(subtotal * 0.18, 2)    # GST 18% default
    po.total = po.subtotal + po.tax_amount
    db.commit(); db.refresh(po)
    return _po_dict(po)

@router.post("/po/{po_id}/approve")
def approve_po(po_id: int, approved_by: str = "admin", db: Session = Depends(get_db)):
    from datetime import datetime
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404, "Not found")
    po.status = "confirmed"
    po.approved_by = approved_by
    po.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "PO approved", "po_number": po.po_number}

@router.delete("/po/{po_id}")
def delete_po(po_id: int, db: Session = Depends(get_db)):
    po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404, "Not found")
    db.delete(po); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/contracts")
def list_contracts(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.ProjectContract)
    if project_id: q = q.filter(models.ProjectContract.project_id == project_id)
    return [{"id": c.id, "project_id": c.project_id, "contractor_id": c.contractor_id,
             "contract_no": c.contract_no, "contract_type": c.contract_type,
             "contract_value": c.contract_value, "retention_pct": c.retention_pct,
             "start_date": str(c.start_date) if c.start_date else None,
             "end_date": str(c.end_date) if c.end_date else None,
             "status": c.status, "scope": c.scope} for c in q.all()]

@router.post("/contracts", status_code=201)
def create_contract(data: ContractCreate, db: Session = Depends(get_db)):
    c = models.ProjectContract(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "contract_no": c.contract_no, "message": "Contract created"}

@router.delete("/contracts/{cid}")
def delete_contract(cid: int, db: Session = Depends(get_db)):
    c = db.query(models.ProjectContract).filter(models.ProjectContract.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    db.delete(c); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# BUDGET
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/budget/{project_id}")
def get_budget(project_id: int, db: Session = Depends(get_db)):
    budgets = db.query(models.Budget).filter(
        models.Budget.project_id == project_id
    ).order_by(models.Budget.revision.desc()).all()
    result = []
    for b in budgets:
        items = [{"id": i.id, "category": i.category, "description": i.description,
                  "budgeted_cost": i.budgeted_cost, "actual_cost": i.actual_cost,
                  "committed": i.committed, "variance": i.variance}
                 for i in b.items]
        result.append({"id": b.id, "name": b.name, "total_budget": b.total_budget,
                        "approved": b.approved, "revision": b.revision, "items": items})
    return result

@router.post("/budget", status_code=201)
def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    budget = models.Budget(
        project_id=data.project_id,
        name=data.name,
    )
    db.add(budget); db.flush()
    total = 0.0
    for item_data in data.items:
        item = models.BudgetItem(
            budget_id=budget.id,
            category=item_data.category,
            description=item_data.description,
            budgeted_cost=item_data.budgeted_cost,
        )
        total += item_data.budgeted_cost
        db.add(item)
    budget.total_budget = total
    db.commit(); db.refresh(budget)
    return {"id": budget.id, "name": budget.name, "total_budget": budget.total_budget}

@router.post("/budget/{budget_id}/approve")
def approve_budget(budget_id: int, approved_by: str = "admin", db: Session = Depends(get_db)):
    from datetime import datetime
    b = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not b: raise HTTPException(404, "Not found")
    b.approved = True; b.approved_by = approved_by; b.approved_at = datetime.utcnow()
    db.commit(); return {"message": "Budget approved"}

@router.get("/dashboard/{project_id}")
def commercial_dashboard(project_id: int, db: Session = Depends(get_db)):
    """Commercial summary for a project."""
    boq_total = db.query(func.coalesce(func.sum(models.BOQItem.amount), 0)).filter(
        models.BOQItem.project_id == project_id).scalar() or 0
    po_total = db.query(func.coalesce(func.sum(models.PurchaseOrder.total), 0)).filter(
        models.PurchaseOrder.project_id == project_id).scalar() or 0
    po_approved = db.query(func.coalesce(func.sum(models.PurchaseOrder.total), 0)).filter(
        models.PurchaseOrder.project_id == project_id,
        models.PurchaseOrder.status == "confirmed").scalar() or 0
    contract_val = db.query(func.coalesce(func.sum(models.ProjectContract.contract_value), 0)).filter(
        models.ProjectContract.project_id == project_id).scalar() or 0
    vendors_used = db.query(func.count(func.distinct(models.PurchaseOrder.vendor_id))).filter(
        models.PurchaseOrder.project_id == project_id).scalar() or 0
    return {
        "boq_total": float(boq_total),
        "po_total": float(po_total),
        "po_approved": float(po_approved),
        "contract_value": float(contract_val),
        "vendors_used": int(vendors_used),
    }
