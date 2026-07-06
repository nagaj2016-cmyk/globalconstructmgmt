from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=List[schemas.ProjectOut])
def list_projects(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Project)
    if status:
        q = q.filter(models.Project.status == status)
    return q.order_by(models.Project.created_at.desc()).all()


@router.post("/", response_model=schemas.ProjectOut, status_code=201)
def create_project(data: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(p)
    db.commit()
    return {"message": "Deleted"}


# ── Tasks ──────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/tasks", response_model=List[schemas.TaskOut])
def get_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.Task).filter(models.Task.project_id == project_id).all()


@router.post("/{project_id}/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(project_id: int, data: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = models.Task(**data.model_dump(), project_id=project_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, data: schemas.TaskUpdate, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(t)
    db.commit()
    return {"message": "Deleted"}
