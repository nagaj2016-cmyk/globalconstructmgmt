"""
Scheduling router — CPM/PERT, EVM, Gantt data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import BaseModel
from database import get_db
import models
from scheduling.cpm import calculate_cpm, gantt_data
from scheduling.evm import calculate_evm, build_s_curve

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])

# ── Pydantic models ─────────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    project_id: int
    name: str
    description: Optional[str] = None
    wbs_code: Optional[str] = None
    duration_days: float = 1.0
    cost_budget: float = 0.0
    predecessors: List[int] = []

class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    wbs_code: Optional[str] = None
    duration_days: Optional[float] = None
    cost_budget: Optional[float] = None
    predecessors: Optional[List[int]] = None
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    percent_complete: Optional[float] = None
    actual_cost: Optional[float] = None

class EVMInput(BaseModel):
    bac: float
    pv: float
    ev: float
    ac: float
    planned_duration: float = 100.0
    elapsed_time: float = 0.0

class EVMSnapshotCreate(BaseModel):
    project_id: int
    snapshot_date: date
    bac: float
    pv: float
    ev: float
    ac: float
    notes: Optional[str] = None


# ── Activity CRUD ───────────────────────────────────────────────────────────────

@router.get("/activities/{project_id}")
def list_activities(project_id: int, db: Session = Depends(get_db)):
    acts = db.query(models.Activity).filter(
        models.Activity.project_id == project_id
    ).order_by(models.Activity.id).all()
    return [{
        "id": a.id, "project_id": a.project_id, "name": a.name,
        "description": a.description, "wbs_code": a.wbs_code,
        "duration_days": a.duration_days, "cost_budget": a.cost_budget,
        "predecessors": a.predecessors or [],
        "early_start": a.early_start, "early_finish": a.early_finish,
        "late_start": a.late_start, "late_finish": a.late_finish,
        "total_float": a.total_float, "free_float": a.free_float,
        "is_critical": a.is_critical,
        "actual_start": str(a.actual_start) if a.actual_start else None,
        "actual_finish": str(a.actual_finish) if a.actual_finish else None,
        "percent_complete": a.percent_complete,
        "actual_cost": a.actual_cost,
    } for a in acts]


@router.post("/activities", status_code=201)
def create_activity(data: ActivityCreate, db: Session = Depends(get_db)):
    # verify project exists
    proj = db.query(models.Project).filter(models.Project.id == data.project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    a = models.Activity(**data.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id, "name": a.name, "message": "Activity created"}


@router.put("/activities/{act_id}")
def update_activity(act_id: int, data: ActivityUpdate, db: Session = Depends(get_db)):
    a = db.query(models.Activity).filter(models.Activity.id == act_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    db.commit(); db.refresh(a)
    return {"message": "Updated"}


@router.delete("/activities/{act_id}")
def delete_activity(act_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Activity).filter(models.Activity.id == act_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(a); db.commit()
    return {"message": "Deleted"}


# ── CPM / Gantt ─────────────────────────────────────────────────────────────────

@router.post("/cpm/{project_id}")
def run_cpm(project_id: int, db: Session = Depends(get_db)):
    """Run CPM on all activities of a project, store results back."""
    acts = db.query(models.Activity).filter(models.Activity.project_id == project_id).all()
    if not acts:
        raise HTTPException(status_code=404, detail="No activities found for this project")

    act_list = [{
        "id": a.id, "name": a.name, "wbs_code": a.wbs_code or "",
        "duration_days": a.duration_days, "cost_budget": a.cost_budget,
        "predecessors": a.predecessors or [],
        "percent_complete": a.percent_complete, "actual_cost": a.actual_cost,
    } for a in acts]

    result = calculate_cpm(act_list)

    # Persist CPM results back to DB
    for ra in result["activities"]:
        db_act = db.query(models.Activity).filter(models.Activity.id == ra["id"]).first()
        if db_act:
            db_act.early_start  = ra["ES"]
            db_act.early_finish = ra["EF"]
            db_act.late_start   = ra["LS"]
            db_act.late_finish  = ra["LF"]
            db_act.total_float  = ra["TF"]
            db_act.free_float   = ra["FF"]
            db_act.is_critical  = ra["is_critical"]
    db.commit()

    gantt = gantt_data(result)
    return {**result, "gantt": gantt}


@router.get("/gantt/{project_id}")
def get_gantt(project_id: int, db: Session = Depends(get_db)):
    """Return last computed Gantt data (no recalculation)."""
    acts = db.query(models.Activity).filter(models.Activity.project_id == project_id).all()
    if not acts:
        return {"rows": [], "project_duration": 0, "critical_path": []}
    rows = [{
        "id": a.id, "name": a.name, "wbs_code": a.wbs_code or "",
        "start": a.early_start, "duration": a.duration_days,
        "finish": a.early_finish, "float": a.total_float,
        "is_critical": a.is_critical, "percent_complete": a.percent_complete,
        "color": "#ef4444" if a.is_critical else "#3b82f6",
    } for a in sorted(acts, key=lambda x: x.early_start)]
    project_duration = max((a.early_finish for a in acts), default=0)
    critical_path = [a.id for a in acts if a.is_critical]
    return {"rows": rows, "project_duration": project_duration, "critical_path": critical_path}


# ── EVM ─────────────────────────────────────────────────────────────────────────

@router.post("/evm/calculate")
def evm_calculate(data: EVMInput):
    """Stateless EVM calculation — no DB required."""
    return calculate_evm(
        bac=data.bac, pv=data.pv, ev=data.ev, ac=data.ac,
        planned_duration=data.planned_duration, elapsed_time=data.elapsed_time
    )


@router.get("/evm/{project_id}")
def get_evm_snapshots(project_id: int, db: Session = Depends(get_db)):
    snaps = db.query(models.EVMSnapshot).filter(
        models.EVMSnapshot.project_id == project_id
    ).order_by(models.EVMSnapshot.snapshot_date).all()

    if not snaps:
        return {"snapshots": [], "s_curve": None, "latest_evm": None}

    snap_list = [{
        "id": s.id, "snapshot_date": str(s.snapshot_date),
        "bac": s.bac, "pv": s.pv, "ev": s.ev, "ac": s.ac, "notes": s.notes
    } for s in snaps]

    latest = snaps[-1]
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    planned_dur = 100.0
    elapsed = 0.0
    if proj and proj.start_date and proj.end_date:
        from datetime import date as dt
        total = (proj.end_date - proj.start_date).days or 1
        elapsed = (dt.today() - proj.start_date).days
        planned_dur = float(total)

    evm_result = calculate_evm(
        bac=latest.bac, pv=latest.pv, ev=latest.ev, ac=latest.ac,
        planned_duration=planned_dur, elapsed_time=elapsed
    )
    s_curve = build_s_curve(snap_list, latest.bac)

    return {"snapshots": snap_list, "s_curve": s_curve, "latest_evm": evm_result}


@router.post("/evm/snapshot", status_code=201)
def add_evm_snapshot(data: EVMSnapshotCreate, db: Session = Depends(get_db)):
    snap = models.EVMSnapshot(**data.model_dump())
    db.add(snap); db.commit(); db.refresh(snap)
    return {"id": snap.id, "message": "EVM snapshot saved"}


@router.delete("/evm/snapshot/{snap_id}")
def delete_evm_snapshot(snap_id: int, db: Session = Depends(get_db)):
    snap = db.query(models.EVMSnapshot).filter(models.EVMSnapshot.id == snap_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    db.delete(snap); db.commit()
    return {"message": "Deleted"}
