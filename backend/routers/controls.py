"""
Project Controls — Change Orders, RFIs, and Drawing Register
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
import models

router = APIRouter(prefix="/controls", tags=["Project Controls"])


class ChangeOrderIn(BaseModel):
    project_id: int
    contract_id: Optional[int] = None
    co_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    reason: Optional[str] = None
    status: str = "draft"
    cost_impact: float = 0.0
    time_impact_days: int = 0
    requested_by: Optional[str] = None
    submitted_date: Optional[date] = None
    approved_by: Optional[str] = None
    approved_date: Optional[date] = None
    notes: Optional[str] = None


class RFIIn(BaseModel):
    project_id: int
    rfi_number: Optional[str] = None
    subject: str
    question: str
    answer: Optional[str] = None
    discipline: Optional[str] = None
    priority: str = "medium"
    status: str = "open"
    raised_by: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    answered_by: Optional[str] = None


class DrawingIn(BaseModel):
    project_id: int
    drawing_no: Optional[str] = None
    title: str
    discipline: Optional[str] = None
    revision: str = "0"
    status: str = "draft"
    issue_date: Optional[date] = None
    received_date: Optional[date] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None
    approved_by: Optional[str] = None
    file_name: Optional[str] = None
    notes: Optional[str] = None


def _next_no(db: Session, model, project_id: int, field: str, prefix: str) -> str:
    count = db.query(model).filter(model.project_id == project_id).count() + 1
    while True:
        candidate = f"{prefix}-{project_id:03d}-{count:04d}"
        if not db.query(model).filter(getattr(model, field) == candidate).first():
            return candidate
        count += 1


def _change_order_dict(co):
    return {
        "id": co.id, "project_id": co.project_id, "contract_id": co.contract_id,
        "co_number": co.co_number, "title": co.title, "description": co.description,
        "reason": co.reason, "status": co.status, "cost_impact": co.cost_impact,
        "time_impact_days": co.time_impact_days, "requested_by": co.requested_by,
        "submitted_date": str(co.submitted_date) if co.submitted_date else None,
        "approved_by": co.approved_by,
        "approved_date": str(co.approved_date) if co.approved_date else None,
        "notes": co.notes, "created_at": co.created_at,
    }


def _rfi_dict(rfi):
    return {
        "id": rfi.id, "project_id": rfi.project_id, "rfi_number": rfi.rfi_number,
        "subject": rfi.subject, "question": rfi.question, "answer": rfi.answer,
        "discipline": rfi.discipline, "priority": rfi.priority, "status": rfi.status,
        "raised_by": rfi.raised_by, "assigned_to": rfi.assigned_to,
        "due_date": str(rfi.due_date) if rfi.due_date else None,
        "answered_by": rfi.answered_by,
        "answered_at": rfi.answered_at.isoformat() if rfi.answered_at else None,
        "created_at": rfi.created_at,
    }


def _drawing_dict(d):
    return {
        "id": d.id, "project_id": d.project_id, "drawing_no": d.drawing_no,
        "title": d.title, "discipline": d.discipline, "revision": d.revision,
        "status": d.status, "issue_date": str(d.issue_date) if d.issue_date else None,
        "received_date": str(d.received_date) if d.received_date else None,
        "prepared_by": d.prepared_by, "checked_by": d.checked_by,
        "approved_by": d.approved_by, "file_name": d.file_name,
        "notes": d.notes, "created_at": d.created_at,
    }


@router.get("/summary/{project_id}")
def controls_summary(project_id: int, db: Session = Depends(get_db)):
    open_rfis = db.query(models.RFI).filter(
        models.RFI.project_id == project_id,
        models.RFI.status.in_(["open", "submitted"])
    ).count()
    approved_changes = db.query(func.coalesce(func.sum(models.ChangeOrder.cost_impact), 0)).filter(
        models.ChangeOrder.project_id == project_id,
        models.ChangeOrder.status == "approved"
    ).scalar() or 0
    pending_changes = db.query(models.ChangeOrder).filter(
        models.ChangeOrder.project_id == project_id,
        models.ChangeOrder.status.in_(["draft", "submitted"])
    ).count()
    latest_drawings = db.query(models.DrawingRegister).filter(
        models.DrawingRegister.project_id == project_id,
        models.DrawingRegister.status != "superseded"
    ).count()
    return {
        "open_rfis": open_rfis,
        "pending_change_orders": pending_changes,
        "approved_change_value": float(approved_changes),
        "active_drawings": latest_drawings,
    }


@router.get("/change-orders")
def list_change_orders(project_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.ChangeOrder)
    if project_id:
        q = q.filter(models.ChangeOrder.project_id == project_id)
    if status:
        q = q.filter(models.ChangeOrder.status == status)
    return [_change_order_dict(c) for c in q.order_by(models.ChangeOrder.id.desc()).all()]


@router.post("/change-orders", status_code=201)
def create_change_order(data: ChangeOrderIn, db: Session = Depends(get_db)):
    d = data.model_dump()
    if not d.get("co_number"):
        d["co_number"] = _next_no(db, models.ChangeOrder, data.project_id, "co_number", "CO")
    co = models.ChangeOrder(**d)
    db.add(co)
    db.commit()
    db.refresh(co)
    return _change_order_dict(co)


@router.put("/change-orders/{co_id}")
def update_change_order(co_id: int, data: ChangeOrderIn, db: Session = Depends(get_db)):
    co = db.query(models.ChangeOrder).filter(models.ChangeOrder.id == co_id).first()
    if not co:
        raise HTTPException(404, "Change order not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(co, k, v)
    db.commit()
    return _change_order_dict(co)


@router.delete("/change-orders/{co_id}")
def delete_change_order(co_id: int, db: Session = Depends(get_db)):
    co = db.query(models.ChangeOrder).filter(models.ChangeOrder.id == co_id).first()
    if not co:
        raise HTTPException(404, "Change order not found")
    db.delete(co)
    db.commit()
    return {"message": "Deleted"}


@router.get("/rfis")
def list_rfis(project_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.RFI)
    if project_id:
        q = q.filter(models.RFI.project_id == project_id)
    if status:
        q = q.filter(models.RFI.status == status)
    return [_rfi_dict(r) for r in q.order_by(models.RFI.id.desc()).all()]


@router.post("/rfis", status_code=201)
def create_rfi(data: RFIIn, db: Session = Depends(get_db)):
    d = data.model_dump()
    if not d.get("rfi_number"):
        d["rfi_number"] = _next_no(db, models.RFI, data.project_id, "rfi_number", "RFI")
    if d.get("answer") and d.get("status") == "open":
        d["status"] = "answered"
        d["answered_at"] = datetime.utcnow()
    rfi = models.RFI(**d)
    db.add(rfi)
    db.commit()
    db.refresh(rfi)
    return _rfi_dict(rfi)


@router.put("/rfis/{rfi_id}")
def update_rfi(rfi_id: int, data: RFIIn, db: Session = Depends(get_db)):
    rfi = db.query(models.RFI).filter(models.RFI.id == rfi_id).first()
    if not rfi:
        raise HTTPException(404, "RFI not found")
    values = data.model_dump(exclude_none=True)
    if values.get("answer") and not rfi.answered_at:
        values["answered_at"] = datetime.utcnow()
        values.setdefault("status", "answered")
    for k, v in values.items():
        setattr(rfi, k, v)
    db.commit()
    return _rfi_dict(rfi)


@router.delete("/rfis/{rfi_id}")
def delete_rfi(rfi_id: int, db: Session = Depends(get_db)):
    rfi = db.query(models.RFI).filter(models.RFI.id == rfi_id).first()
    if not rfi:
        raise HTTPException(404, "RFI not found")
    db.delete(rfi)
    db.commit()
    return {"message": "Deleted"}


@router.get("/drawings")
def list_drawings(project_id: Optional[int] = None, discipline: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.DrawingRegister)
    if project_id:
        q = q.filter(models.DrawingRegister.project_id == project_id)
    if discipline:
        q = q.filter(models.DrawingRegister.discipline == discipline)
    return [_drawing_dict(d) for d in q.order_by(models.DrawingRegister.id.desc()).all()]


@router.post("/drawings", status_code=201)
def create_drawing(data: DrawingIn, db: Session = Depends(get_db)):
    d = data.model_dump()
    if not d.get("drawing_no"):
        d["drawing_no"] = _next_no(db, models.DrawingRegister, data.project_id, "drawing_no", "DWG")
    drawing = models.DrawingRegister(**d)
    db.add(drawing)
    db.commit()
    db.refresh(drawing)
    return _drawing_dict(drawing)


@router.put("/drawings/{drawing_id}")
def update_drawing(drawing_id: int, data: DrawingIn, db: Session = Depends(get_db)):
    drawing = db.query(models.DrawingRegister).filter(models.DrawingRegister.id == drawing_id).first()
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(drawing, k, v)
    db.commit()
    return _drawing_dict(drawing)


@router.delete("/drawings/{drawing_id}")
def delete_drawing(drawing_id: int, db: Session = Depends(get_db)):
    drawing = db.query(models.DrawingRegister).filter(models.DrawingRegister.id == drawing_id).first()
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    db.delete(drawing)
    db.commit()
    return {"message": "Deleted"}
