from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import date
import random, string
from database import get_db
import models, schemas

router = APIRouter(tags=["Finance"])


# ── Invoices ───────────────────────────────────────────────────────────────────

def gen_invoice_no(db):
    prefix = "INV"
    year = date.today().year
    count = db.query(models.Invoice).count() + 1
    return f"{prefix}-{year}-{count:04d}"


@router.get("/invoices", response_model=List[schemas.InvoiceOut])
def list_invoices(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Invoice)
    if status:
        q = q.filter(models.Invoice.status == status)
    return q.order_by(models.Invoice.created_at.desc()).all()


@router.post("/invoices", response_model=schemas.InvoiceOut, status_code=201)
def create_invoice(data: schemas.InvoiceCreate, db: Session = Depends(get_db)):
    items_data = data.line_items
    inv_data = data.model_dump(exclude={"line_items"})
    if not inv_data.get("invoice_no"):
        inv_data["invoice_no"] = gen_invoice_no(db)

    subtotal = sum((item.quantity * item.rate) for item in items_data)
    tax_rate = inv_data.get("tax_rate", 18.0)
    tax_amount = subtotal * tax_rate / 100
    total = subtotal + tax_amount

    inv_data.update(subtotal=subtotal, tax_amount=tax_amount, total=total)
    invoice = models.Invoice(**inv_data)
    db.add(invoice)
    db.flush()

    for item in items_data:
        ii = models.InvoiceItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            rate=item.rate,
            amount=item.quantity * item.rate,
        )
        db.add(ii)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.put("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def update_invoice(invoice_id: int, data: schemas.InvoiceUpdate, db: Session = Depends(get_db)):
    inv = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(inv, k, v)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(inv)
    db.commit()
    return {"message": "Deleted"}


# ── Expenses ───────────────────────────────────────────────────────────────────

@router.get("/expenses", response_model=List[schemas.ExpenseOut])
def list_expenses(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Expense)
    if project_id:
        q = q.filter(models.Expense.project_id == project_id)
    return q.order_by(models.Expense.date.desc()).all()


@router.post("/expenses", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(data: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    exp = models.Expense(**data.model_dump())
    db.add(exp)
    # Update project spent
    if data.project_id:
        p = db.query(models.Project).filter(models.Project.id == data.project_id).first()
        if p:
            p.spent = (p.spent or 0) + data.amount
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(exp)
    db.commit()
    return {"message": "Deleted"}
