"""
Site Operations — Phase 4
Daily Site Diary, Labour Attendance, Equipment Register, Fuel Log,
Material Consumption, Site Photos
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
import os, uuid
from database import get_db
from config import settings
import models

router = APIRouter(prefix="/site", tags=["Site Operations"])

PHOTO_DIR = os.path.join(settings.UPLOAD_DIR, "site_photos")
os.makedirs(PHOTO_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class SiteDiaryCreate(BaseModel):
    project_id: int
    report_date: date
    prepared_by: Optional[str] = None
    weather_morning: Optional[str] = None
    weather_afternoon: Optional[str] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    total_workers: int = 0
    total_engineers: int = 0
    work_done: Optional[str] = None
    material_used: Optional[str] = None
    equipment_used: Optional[str] = None
    visitors: Optional[str] = None
    instructions: Optional[str] = None
    delays: Optional[str] = None
    safety_notes: Optional[str] = None
    remarks: Optional[str] = None

class EquipmentCreate(BaseModel):
    name: str
    equipment_no: Optional[str] = None
    category: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership: str = "owned"
    vendor: Optional[str] = None
    daily_hire_rate: float = 0.0
    fuel_type: Optional[str] = None
    capacity: Optional[str] = None
    last_service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    insurance_expiry: Optional[date] = None
    project_id: Optional[int] = None
    notes: Optional[str] = None

class FuelLogCreate(BaseModel):
    equipment_id: int
    project_id: Optional[int] = None
    log_date: date
    fuel_type: Optional[str] = "diesel"
    liters: float = 0.0
    rate_per_ltr: float = 0.0
    meter_reading: float = 0.0
    hours_worked: float = 0.0
    filled_by: Optional[str] = None
    notes: Optional[str] = None

class MaterialConsumptionCreate(BaseModel):
    project_id: int
    item_id: Optional[int] = None
    log_date: date
    material: str
    quantity: float = 0.0
    unit: Optional[str] = None
    location_used: Optional[str] = None
    purpose: Optional[str] = None
    issued_by: Optional[str] = None

class AttendanceCreate(BaseModel):
    worker_id: int
    project_id: Optional[int] = None
    date: date
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    hours_worked: float = 0.0
    is_present: bool = True
    overtime_hours: float = 0.0
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    notes: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# SITE DIARY
# ══════════════════════════════════════════════════════════════════════════════

def _diary_dict(d):
    return {"id": d.id, "project_id": d.project_id,
            "report_date": str(d.report_date), "prepared_by": d.prepared_by,
            "weather_morning": d.weather_morning, "weather_afternoon": d.weather_afternoon,
            "temperature_c": d.temperature_c, "humidity_pct": d.humidity_pct,
            "total_workers": d.total_workers, "total_engineers": d.total_engineers,
            "work_done": d.work_done, "material_used": d.material_used,
            "equipment_used": d.equipment_used, "visitors": d.visitors,
            "instructions": d.instructions, "delays": d.delays,
            "safety_notes": d.safety_notes, "remarks": d.remarks,
            "created_at": str(d.created_at)}

@router.get("/diary/{project_id}")
def list_diaries(project_id: int, db: Session = Depends(get_db)):
    diaries = db.query(models.SiteDiary).filter(
        models.SiteDiary.project_id == project_id
    ).order_by(models.SiteDiary.report_date.desc()).all()
    return [_diary_dict(d) for d in diaries]

@router.get("/diary/{project_id}/{diary_id}")
def get_diary(project_id: int, diary_id: int, db: Session = Depends(get_db)):
    d = db.query(models.SiteDiary).filter(
        models.SiteDiary.id == diary_id,
        models.SiteDiary.project_id == project_id
    ).first()
    if not d: raise HTTPException(404, "Diary not found")
    return _diary_dict(d)

@router.post("/diary", status_code=201)
def create_diary(data: SiteDiaryCreate, db: Session = Depends(get_db)):
    # Check no duplicate for this date
    existing = db.query(models.SiteDiary).filter(
        models.SiteDiary.project_id == data.project_id,
        models.SiteDiary.report_date == data.report_date
    ).first()
    if existing:
        raise HTTPException(400, f"Diary already exists for {data.report_date}")
    d = models.SiteDiary(**data.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return _diary_dict(d)

@router.put("/diary/{diary_id}")
def update_diary(diary_id: int, data: SiteDiaryCreate, db: Session = Depends(get_db)):
    d = db.query(models.SiteDiary).filter(models.SiteDiary.id == diary_id).first()
    if not d: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(d, k, v)
    db.commit(); return _diary_dict(d)

@router.delete("/diary/{diary_id}")
def delete_diary(diary_id: int, db: Session = Depends(get_db)):
    d = db.query(models.SiteDiary).filter(models.SiteDiary.id == diary_id).first()
    if not d: raise HTTPException(404, "Not found")
    db.delete(d); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# EQUIPMENT
# ══════════════════════════════════════════════════════════════════════════════

def _equip_dict(e):
    return {"id": e.id, "name": e.name, "equipment_no": e.equipment_no,
            "category": e.category, "make": e.make, "model": e.model,
            "year": e.year, "ownership": e.ownership, "vendor": e.vendor,
            "daily_hire_rate": e.daily_hire_rate, "fuel_type": e.fuel_type,
            "capacity": e.capacity, "is_active": e.is_active,
            "project_id": e.project_id,
            "last_service_date": str(e.last_service_date) if e.last_service_date else None,
            "next_service_date": str(e.next_service_date) if e.next_service_date else None,
            "insurance_expiry": str(e.insurance_expiry) if e.insurance_expiry else None}

@router.get("/equipment")
def list_equipment(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Equipment)
    if project_id: q = q.filter(models.Equipment.project_id == project_id)
    return [_equip_dict(e) for e in q.order_by(models.Equipment.name).all()]

@router.post("/equipment", status_code=201)
def create_equipment(data: EquipmentCreate, db: Session = Depends(get_db)):
    e = models.Equipment(**data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return _equip_dict(e)

@router.put("/equipment/{eid}")
def update_equipment(eid: int, data: EquipmentCreate, db: Session = Depends(get_db)):
    e = db.query(models.Equipment).filter(models.Equipment.id == eid).first()
    if not e: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(e, k, v)
    db.commit(); return _equip_dict(e)

@router.delete("/equipment/{eid}")
def delete_equipment(eid: int, db: Session = Depends(get_db)):
    e = db.query(models.Equipment).filter(models.Equipment.id == eid).first()
    if not e: raise HTTPException(404, "Not found")
    db.delete(e); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# FUEL LOG
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/fuel")
def list_fuel(project_id: Optional[int] = None, equipment_id: Optional[int] = None,
              db: Session = Depends(get_db)):
    q = db.query(models.FuelLog)
    if project_id: q = q.filter(models.FuelLog.project_id == project_id)
    if equipment_id: q = q.filter(models.FuelLog.equipment_id == equipment_id)
    logs = q.order_by(models.FuelLog.log_date.desc()).all()
    return [{"id": l.id, "equipment_id": l.equipment_id, "project_id": l.project_id,
             "log_date": str(l.log_date), "fuel_type": l.fuel_type,
             "liters": l.liters, "rate_per_ltr": l.rate_per_ltr, "cost": l.cost,
             "meter_reading": l.meter_reading, "hours_worked": l.hours_worked,
             "filled_by": l.filled_by} for l in logs]

@router.post("/fuel", status_code=201)
def create_fuel_log(data: FuelLogCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    d["cost"] = round(d["liters"] * d["rate_per_ltr"], 2)
    log = models.FuelLog(**d)
    db.add(log); db.commit(); db.refresh(log)
    return {"id": log.id, "cost": log.cost, "message": "Fuel log created"}

@router.delete("/fuel/{lid}")
def delete_fuel_log(lid: int, db: Session = Depends(get_db)):
    log = db.query(models.FuelLog).filter(models.FuelLog.id == lid).first()
    if not log: raise HTTPException(404, "Not found")
    db.delete(log); db.commit(); return {"message": "Deleted"}

@router.get("/fuel/summary/{project_id}")
def fuel_summary(project_id: int, db: Session = Depends(get_db)):
    """Fuel consumption and cost summary per equipment."""
    logs = db.query(models.FuelLog).filter(models.FuelLog.project_id == project_id).all()
    equip_map = {}
    for log in logs:
        eid = log.equipment_id
        if eid not in equip_map:
            equip = db.query(models.Equipment).filter(models.Equipment.id == eid).first()
            equip_map[eid] = {"equipment_id": eid,
                              "name": equip.name if equip else "Unknown",
                              "total_liters": 0.0, "total_cost": 0.0, "logs": 0}
        equip_map[eid]["total_liters"] += log.liters
        equip_map[eid]["total_cost"] += log.cost
        equip_map[eid]["logs"] += 1
    return {"equipment": list(equip_map.values()),
            "total_liters": sum(l.liters for l in logs),
            "total_cost": sum(l.cost for l in logs)}


# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL CONSUMPTION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/material/{project_id}")
def list_consumption(project_id: int, db: Session = Depends(get_db)):
    logs = db.query(models.MaterialConsumption).filter(
        models.MaterialConsumption.project_id == project_id
    ).order_by(models.MaterialConsumption.log_date.desc()).all()
    return [{"id": l.id, "log_date": str(l.log_date), "material": l.material,
             "quantity": l.quantity, "unit": l.unit, "location_used": l.location_used,
             "purpose": l.purpose, "issued_by": l.issued_by} for l in logs]

@router.post("/material", status_code=201)
def create_consumption(data: MaterialConsumptionCreate, db: Session = Depends(get_db)):
    log = models.MaterialConsumption(**data.model_dump())
    db.add(log); db.commit(); db.refresh(log)
    return {"id": log.id, "message": "Consumption logged"}

@router.delete("/material/{lid}")
def delete_consumption(lid: int, db: Session = Depends(get_db)):
    log = db.query(models.MaterialConsumption).filter(models.MaterialConsumption.id == lid).first()
    if not log: raise HTTPException(404, "Not found")
    db.delete(log); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/attendance")
def list_attendance(project_id: Optional[int] = None, log_date: Optional[date] = None,
                    worker_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Attendance)
    if project_id: q = q.filter(models.Attendance.project_id == project_id)
    if log_date:   q = q.filter(models.Attendance.date == log_date)
    if worker_id:  q = q.filter(models.Attendance.worker_id == worker_id)
    records = q.order_by(models.Attendance.date.desc()).all()
    return [{"id": r.id, "worker_id": r.worker_id, "project_id": r.project_id,
             "date": str(r.date), "check_in": r.check_in, "check_out": r.check_out,
             "hours_worked": r.hours_worked, "is_present": r.is_present,
             "overtime_hours": r.overtime_hours,
             "gps_lat": r.gps_lat, "gps_lng": r.gps_lng} for r in records]

@router.post("/attendance", status_code=201)
def log_attendance(data: AttendanceCreate, db: Session = Depends(get_db)):
    # Check for duplicate
    existing = db.query(models.Attendance).filter(
        models.Attendance.worker_id == data.worker_id,
        models.Attendance.date == data.date
    ).first()
    if existing:
        raise HTTPException(400, "Attendance already logged for this date")
    a = models.Attendance(**data.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id, "message": "Attendance logged"}

@router.delete("/attendance/{aid}")
def delete_attendance(aid: int, db: Session = Depends(get_db)):
    a = db.query(models.Attendance).filter(models.Attendance.id == aid).first()
    if not a: raise HTTPException(404, "Not found")
    db.delete(a); db.commit(); return {"message": "Deleted"}

@router.get("/attendance/summary/{project_id}")
def attendance_summary(project_id: int, from_date: Optional[date] = None,
                        to_date: Optional[date] = None, db: Session = Depends(get_db)):
    """Head count and hours summary for a project date range."""
    q = db.query(models.Attendance).filter(models.Attendance.project_id == project_id)
    if from_date: q = q.filter(models.Attendance.date >= from_date)
    if to_date:   q = q.filter(models.Attendance.date <= to_date)
    records = q.all()
    total_present = sum(1 for r in records if r.is_present)
    total_hours   = sum(r.hours_worked for r in records)
    overtime      = sum(r.overtime_hours for r in records)
    return {"total_records": len(records), "total_present": total_present,
            "total_hours": round(total_hours, 1), "total_overtime": round(overtime, 1)}


# ══════════════════════════════════════════════════════════════════════════════
# SITE PHOTOS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/photos/{project_id}")
def list_photos(project_id: int, db: Session = Depends(get_db)):
    photos = db.query(models.SitePhoto).filter(
        models.SitePhoto.project_id == project_id
    ).order_by(models.SitePhoto.photo_date.desc()).all()
    return [{"id": p.id, "project_id": p.project_id, "diary_id": p.diary_id,
             "file_name": p.file_name, "caption": p.caption,
             "location_tag": p.location_tag, "gps_lat": p.gps_lat, "gps_lng": p.gps_lng,
             "photo_date": str(p.photo_date) if p.photo_date else None,
             "taken_by": p.taken_by,
             "url": "/uploads/site_photos/" + p.file_name if p.file_name else None}
            for p in photos]

@router.post("/photos/upload")
async def upload_photo(
    project_id: int,
    taken_by: str = "",
    caption: str = "",
    location_tag: str = "",
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    import aiofiles
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    fpath = os.path.join(PHOTO_DIR, fname)
    async with aiofiles.open(fpath, "wb") as f:
        content = await file.read()
        await f.write(content)

    photo = models.SitePhoto(
        project_id=project_id,
        file_name=fname,
        file_path=fpath,
        caption=caption,
        location_tag=location_tag,
        taken_by=taken_by,
        photo_date=date.today(),
    )
    db.add(photo); db.commit(); db.refresh(photo)
    return {"id": photo.id, "file_name": fname, "message": "Photo uploaded"}

@router.delete("/photos/{pid}")
def delete_photo(pid: int, db: Session = Depends(get_db)):
    p = db.query(models.SitePhoto).filter(models.SitePhoto.id == pid).first()
    if not p: raise HTTPException(404, "Not found")
    if p.file_path and os.path.exists(p.file_path):
        os.remove(p.file_path)
    db.delete(p); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# SITE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/{project_id}")
def site_dashboard(project_id: int, db: Session = Depends(get_db)):
    """Summary of site operations for a project."""
    diaries = db.query(models.SiteDiary).filter(
        models.SiteDiary.project_id == project_id).count()
    # Today's attendance
    today_att = db.query(models.Attendance).filter(
        models.Attendance.project_id == project_id,
        models.Attendance.date == date.today(),
        models.Attendance.is_present == True).count()
    equipment_count = db.query(models.Equipment).filter(
        models.Equipment.project_id == project_id,
        models.Equipment.is_active == True).count()
    fuel_cost = db.query(func.coalesce(func.sum(models.FuelLog.cost), 0)).filter(
        models.FuelLog.project_id == project_id).scalar() or 0
    photos = db.query(models.SitePhoto).filter(
        models.SitePhoto.project_id == project_id).count()
    # Last diary
    last_diary = db.query(models.SiteDiary).filter(
        models.SiteDiary.project_id == project_id
    ).order_by(models.SiteDiary.report_date.desc()).first()

    return {
        "diary_count": diaries,
        "today_workers": today_att,
        "active_equipment": equipment_count,
        "total_fuel_cost": float(fuel_cost),
        "photo_count": photos,
        "last_diary_date": str(last_diary.report_date) if last_diary else None,
    }
