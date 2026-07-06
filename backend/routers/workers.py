from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas

router = APIRouter(prefix="/workers", tags=["Workers"])


@router.get("/", response_model=List[schemas.WorkerOut])
def list_workers(role: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Worker)
    if role:
        q = q.filter(models.Worker.role == role)
    if status:
        q = q.filter(models.Worker.status == status)
    return q.order_by(models.Worker.first_name).all()


@router.post("/", response_model=schemas.WorkerOut, status_code=201)
def create_worker(data: schemas.WorkerCreate, db: Session = Depends(get_db)):
    w = models.Worker(**data.model_dump())
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@router.get("/{worker_id}", response_model=schemas.WorkerOut)
def get_worker(worker_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Worker).filter(models.Worker.id == worker_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")
    return w


@router.put("/{worker_id}", response_model=schemas.WorkerOut)
def update_worker(worker_id: int, data: schemas.WorkerUpdate, db: Session = Depends(get_db)):
    w = db.query(models.Worker).filter(models.Worker.id == worker_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    db.commit()
    db.refresh(w)
    return w


@router.delete("/{worker_id}")
def delete_worker(worker_id: int, db: Session = Depends(get_db)):
    w = db.query(models.Worker).filter(models.Worker.id == worker_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")
    db.delete(w)
    db.commit()
    return {"message": "Deleted"}


# ── Attendance ─────────────────────────────────────────────────────────────────

@router.get("/attendance/all", response_model=List[schemas.AttendanceOut])
def list_attendance(date: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Attendance)
    if date:
        q = q.filter(models.Attendance.date == date)
    return q.order_by(models.Attendance.date.desc()).all()


@router.post("/attendance", response_model=schemas.AttendanceOut, status_code=201)
def mark_attendance(data: schemas.AttendanceCreate, db: Session = Depends(get_db)):
    a = models.Attendance(**data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get("/{worker_id}/attendance", response_model=List[schemas.AttendanceOut])
def worker_attendance(worker_id: int, db: Session = Depends(get_db)):
    return db.query(models.Attendance).filter(
        models.Attendance.worker_id == worker_id
    ).order_by(models.Attendance.date.desc()).all()
