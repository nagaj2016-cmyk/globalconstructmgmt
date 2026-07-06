"""Company, Branch, Department, Contractor, Consultant — Phase 1 Core ERP"""
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
import models

router = APIRouter(prefix="/company", tags=["Company & Org"])

BRAND_DIR = "uploads/branding"
os.makedirs(BRAND_DIR, exist_ok=True)
_ALLOWED_IMG = {".png", ".jpg", ".jpeg"}


def _save_image(file: UploadFile, kind: str) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_IMG:
        raise HTTPException(status_code=400, detail="Logo/seal must be PNG or JPG.")
    data = file.file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 3 MB).")
    name = f"{kind}_{uuid.uuid4().hex}{ext}"
    with open(os.path.join(BRAND_DIR, name), "wb") as f:
        f.write(data)
    return f"/uploads/branding/{name}"


@router.get("/branding")
def get_branding(current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    co = db.query(models.Company).filter(models.Company.id == current_user.company_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="No company for this user")
    return {"company": co.name, "logo_url": co.logo_url, "seal_url": co.seal_url}


@router.post("/branding")
def set_branding(logo: Optional[UploadFile] = File(None),
                 seal: Optional[UploadFile] = File(None),
                 current_user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Upload the firm logo and/or the responsible engineer's seal. Both appear
    on generated calculation sheets."""
    if current_user.role not in ("admin",) and not getattr(current_user, "is_platform_admin", False):
        # allow admins; also allow the tenant's own admin
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only an admin can set firm branding.")
    co = db.query(models.Company).filter(models.Company.id == current_user.company_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="No company for this user")
    if logo is not None:
        co.logo_url = _save_image(logo, "logo")
    if seal is not None:
        co.seal_url = _save_image(seal, "seal")
    db.commit()
    return {"ok": True, "logo_url": co.logo_url, "seal_url": co.seal_url}


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    short_name: Optional[str] = None
    registration_no: Optional[str] = None
    gst_no: Optional[str] = None
    country: str = "India"
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    plan: Optional[str] = "starter"

class BranchCreate(BaseModel):
    company_id: int
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class DepartmentCreate(BaseModel):
    company_id: int
    name: str
    code: Optional[str] = None
    head_name: Optional[str] = None
    description: Optional[str] = None

class ContractorCreate(BaseModel):
    name: str
    company_name: Optional[str] = None
    trade: Optional[str] = None
    license_no: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    experience_years: int = 0
    notes: Optional[str] = None

class ConsultantCreate(BaseModel):
    name: str
    firm: Optional[str] = None
    specialization: Optional[str] = None
    license_no: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    fee_type: Optional[str] = None
    notes: Optional[str] = None


def _company_dict(c):
    return {"id": c.id, "name": c.name, "short_name": c.short_name,
            "registration_no": c.registration_no,
            "gst_no": getattr(c, "gst_no", None),
            "country": c.country, "currency": c.currency,
            "timezone": getattr(c, "timezone", "Asia/Kolkata"),
            "city": getattr(c, "city", None),
            "address": c.address, "phone": c.phone,
            "email": c.email, "website": c.website, "plan": c.plan,
            "is_active": c.is_active, "created_at": str(c.created_at)}

def _contractor_dict(c):
    return {"id": c.id, "name": c.name, "company_name": c.company_name,
            "trade": c.trade, "license_no": c.license_no, "email": c.email,
            "phone": c.phone, "country": c.country, "rating": c.rating,
            "experience_years": c.experience_years, "is_active": c.is_active,
            "notes": c.notes}

def _consultant_dict(c):
    return {"id": c.id, "name": c.name, "firm": c.firm,
            "specialization": c.specialization, "license_no": c.license_no,
            "email": c.email, "phone": c.phone, "country": c.country,
            "fee_type": c.fee_type, "is_active": c.is_active, "notes": c.notes}


# ── Companies ────────────────────────────────────────────────────────────────

@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    return [_company_dict(c) for c in db.query(models.Company).order_by(models.Company.name).all()]

@router.post("/companies", status_code=201)
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    c = models.Company(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _company_dict(c)

@router.put("/companies/{cid}")
def update_company(cid: int, data: CompanyCreate, db: Session = Depends(get_db)):
    c = db.query(models.Company).filter(models.Company.id == cid).first()
    if not c: raise HTTPException(404, "Company not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(c, k, v)
    db.commit(); return _company_dict(c)

@router.delete("/companies/{cid}")
def delete_company(cid: int, db: Session = Depends(get_db)):
    c = db.query(models.Company).filter(models.Company.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    db.delete(c); db.commit(); return {"message": "Deleted"}


# ── Branches ─────────────────────────────────────────────────────────────────

@router.get("/branches")
def list_branches(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Branch)
    if company_id: q = q.filter(models.Branch.company_id == company_id)
    return [{"id": b.id, "company_id": b.company_id, "name": b.name,
             "city": b.city, "country": b.country, "phone": b.phone,
             "is_active": b.is_active} for b in q.all()]

@router.post("/branches", status_code=201)
def create_branch(data: BranchCreate, db: Session = Depends(get_db)):
    b = models.Branch(**data.model_dump())
    db.add(b); db.commit(); db.refresh(b)
    return {"id": b.id, "name": b.name, "message": "Branch created"}

@router.delete("/branches/{bid}")
def delete_branch(bid: int, db: Session = Depends(get_db)):
    b = db.query(models.Branch).filter(models.Branch.id == bid).first()
    if not b: raise HTTPException(404, "Not found")
    db.delete(b); db.commit(); return {"message": "Deleted"}


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/departments")
def list_departments(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Department)
    if company_id: q = q.filter(models.Department.company_id == company_id)
    return [{"id": d.id, "company_id": d.company_id, "name": d.name,
             "code": d.code, "head_name": d.head_name} for d in q.all()]

@router.post("/departments", status_code=201)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db)):
    d = models.Department(**data.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return {"id": d.id, "name": d.name, "message": "Department created"}

@router.delete("/departments/{did}")
def delete_department(did: int, db: Session = Depends(get_db)):
    d = db.query(models.Department).filter(models.Department.id == did).first()
    if not d: raise HTTPException(404, "Not found")
    db.delete(d); db.commit(); return {"message": "Deleted"}


# ── Contractors ───────────────────────────────────────────────────────────────

@router.get("/contractors")
def list_contractors(db: Session = Depends(get_db)):
    return [_contractor_dict(c) for c in
            db.query(models.Contractor).order_by(models.Contractor.name).all()]

@router.post("/contractors", status_code=201)
def create_contractor(data: ContractorCreate, db: Session = Depends(get_db)):
    c = models.Contractor(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _contractor_dict(c)

@router.put("/contractors/{cid}")
def update_contractor(cid: int, data: ContractorCreate, db: Session = Depends(get_db)):
    c = db.query(models.Contractor).filter(models.Contractor.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(c, k, v)
    db.commit(); return _contractor_dict(c)

@router.delete("/contractors/{cid}")
def delete_contractor(cid: int, db: Session = Depends(get_db)):
    c = db.query(models.Contractor).filter(models.Contractor.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    db.delete(c); db.commit(); return {"message": "Deleted"}


# ── Consultants ───────────────────────────────────────────────────────────────

@router.get("/consultants")
def list_consultants(db: Session = Depends(get_db)):
    return [_consultant_dict(c) for c in
            db.query(models.Consultant).order_by(models.Consultant.name).all()]

@router.post("/consultants", status_code=201)
def create_consultant(data: ConsultantCreate, db: Session = Depends(get_db)):
    c = models.Consultant(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _consultant_dict(c)

@router.put("/consultants/{cid}")
def update_consultant(cid: int, data: ConsultantCreate, db: Session = Depends(get_db)):
    c = db.query(models.Consultant).filter(models.Consultant.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(c, k, v)
    db.commit(); return _consultant_dict(c)

@router.delete("/consultants/{cid}")
def delete_consultant(cid: int, db: Session = Depends(get_db)):
    c = db.query(models.Consultant).filter(models.Consultant.id == cid).first()
    if not c: raise HTTPException(404, "Not found")
    db.delete(c); db.commit(); return {"message": "Deleted"}
