"""
Safety Module — Phase 6 (enhanced)
Incidents, Inspections, Toolbox Talks, Permits to Work, Risk Assessments
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime
from database import get_db
import models

router = APIRouter(prefix="/safety", tags=["Safety"])


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class IncidentCreate(BaseModel):
    project_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    incident_type: str = "incident"
    severity: str = "low"
    incident_date: Optional[date] = None
    time_of_incident: Optional[str] = None
    location: Optional[str] = None
    involved_workers: Optional[str] = None
    injuries: bool = False
    injury_details: Optional[str] = None
    lost_time_days: float = 0.0
    corrective_action: Optional[str] = None
    reported_by: Optional[str] = None
    investigated_by: Optional[str] = None

class InspectionCreate(BaseModel):
    project_id: Optional[int] = None
    title: str
    inspector: Optional[str] = None
    inspection_date: Optional[date] = None
    passed: bool = True
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    next_inspection: Optional[date] = None

class ToolboxTalkCreate(BaseModel):
    project_id: int
    topic: str
    talk_date: date
    conducted_by: Optional[str] = None
    location: Optional[str] = None
    duration_min: int = 15
    attendees_count: int = 0
    attendees: Optional[str] = None
    key_points: Optional[str] = None
    remarks: Optional[str] = None

class PTWCreate(BaseModel):
    project_id: int
    permit_no: Optional[str] = None
    permit_type: str = "hot_work"
    title: Optional[str] = None
    location: Optional[str] = None
    scope_of_work: Optional[str] = None
    requested_by: Optional[str] = None
    contractor: Optional[str] = None
    workers_involved: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    precautions: Optional[str] = None
    equipment_required: Optional[str] = None
    ppe_required: Optional[str] = None
    issued_by: Optional[str] = None
    remarks: Optional[str] = None

class RiskAssessmentCreate(BaseModel):
    project_id: int
    activity: str
    hazard: Optional[str] = None
    risk_description: Optional[str] = None
    likelihood: int = 3
    severity_score: int = 3
    control_measures: Optional[str] = None
    residual_risk: int = 4
    responsible: Optional[str] = None
    review_date: Optional[date] = None


# ══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ══════════════════════════════════════════════════════════════════════════════

def _incident_dict(i):
    return {"id": i.id, "project_id": i.project_id, "incident_no": i.incident_no,
            "title": i.title, "description": i.description,
            "incident_type": i.incident_type, "severity": i.severity,
            "incident_date": str(i.incident_date) if i.incident_date else None,
            "time_of_incident": i.time_of_incident, "location": i.location,
            "involved_workers": i.involved_workers, "injuries": i.injuries,
            "injury_details": i.injury_details, "lost_time_days": i.lost_time_days,
            "resolved": i.resolved, "corrective_action": i.corrective_action,
            "reported_by": i.reported_by, "investigated_by": i.investigated_by,
            "created_at": str(i.created_at)}

@router.get("/incidents")
def list_incidents(project_id: Optional[int] = None, resolved: Optional[bool] = None,
                   db: Session = Depends(get_db)):
    q = db.query(models.SafetyIncident)
    if project_id is not None: q = q.filter(models.SafetyIncident.project_id == project_id)
    if resolved is not None: q = q.filter(models.SafetyIncident.resolved == resolved)
    return [_incident_dict(i) for i in q.order_by(models.SafetyIncident.incident_date.desc()).all()]

@router.post("/incidents", status_code=201)
def create_incident(data: IncidentCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    count = db.query(models.SafetyIncident).count()
    d["incident_no"] = f"INC-{count+1:04d}"
    d["resolved"] = False
    inc = models.SafetyIncident(**d)
    db.add(inc); db.commit(); db.refresh(inc)
    return _incident_dict(inc)

@router.put("/incidents/{inc_id}")
def update_incident(inc_id: int, data: IncidentCreate, db: Session = Depends(get_db)):
    inc = db.query(models.SafetyIncident).filter(models.SafetyIncident.id == inc_id).first()
    if not inc: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(inc, k, v)
    db.commit(); return _incident_dict(inc)

@router.post("/incidents/{inc_id}/resolve")
def resolve_incident(inc_id: int, db: Session = Depends(get_db)):
    inc = db.query(models.SafetyIncident).filter(models.SafetyIncident.id == inc_id).first()
    if not inc: raise HTTPException(404, "Not found")
    inc.resolved = True; db.commit()
    return {"message": "Incident resolved"}

@router.delete("/incidents/{inc_id}")
def delete_incident(inc_id: int, db: Session = Depends(get_db)):
    inc = db.query(models.SafetyIncident).filter(models.SafetyIncident.id == inc_id).first()
    if not inc: raise HTTPException(404, "Not found")
    db.delete(inc); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# INSPECTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _insp_dict(i):
    return {"id": i.id, "project_id": i.project_id, "title": i.title,
            "inspector": i.inspector,
            "inspection_date": str(i.inspection_date) if i.inspection_date else None,
            "passed": i.passed, "findings": i.findings,
            "recommendations": i.recommendations,
            "next_inspection": str(i.next_inspection) if i.next_inspection else None}

@router.get("/inspections")
def list_inspections(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.SafetyInspection)
    if project_id is not None: q = q.filter(models.SafetyInspection.project_id == project_id)
    return [_insp_dict(i) for i in q.order_by(models.SafetyInspection.inspection_date.desc()).all()]

@router.post("/inspections", status_code=201)
def create_inspection(data: InspectionCreate, db: Session = Depends(get_db)):
    insp = models.SafetyInspection(**data.model_dump())
    db.add(insp); db.commit(); db.refresh(insp)
    return _insp_dict(insp)

@router.put("/inspections/{iid}")
def update_inspection(iid: int, data: InspectionCreate, db: Session = Depends(get_db)):
    insp = db.query(models.SafetyInspection).filter(models.SafetyInspection.id == iid).first()
    if not insp: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(insp, k, v)
    db.commit(); return _insp_dict(insp)

@router.delete("/inspections/{iid}")
def delete_inspection(iid: int, db: Session = Depends(get_db)):
    insp = db.query(models.SafetyInspection).filter(models.SafetyInspection.id == iid).first()
    if not insp: raise HTTPException(404, "Not found")
    db.delete(insp); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# TOOLBOX TALKS
# ══════════════════════════════════════════════════════════════════════════════

TOOLBOX_TOPICS = [
    "Working at Height — Fall Prevention",
    "Scaffolding Safety — Erection and Dismantling",
    "Confined Space Entry Procedures",
    "Hot Work Permits — Fire Prevention",
    "Electrical Safety — Lock Out Tag Out (LOTO)",
    "Excavation and Trenching Safety",
    "Manual Handling and Ergonomics",
    "PPE — Selection, Use, and Maintenance",
    "Emergency Evacuation Procedures",
    "Hazardous Materials — COSHH / MSDS",
    "Crane and Lifting Operations Safety",
    "Housekeeping and Slip/Trip Prevention",
    "Heat Stress and Hydration on Site",
    "Hand and Power Tool Safety",
    "Concrete Pour Safety Precautions",
    "Near Miss Reporting Culture",
    "First Aid and Emergency Response",
    "Traffic Management on Site",
]

@router.get("/toolbox")
def list_toolbox(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.ToolboxTalk)
    if project_id: q = q.filter(models.ToolboxTalk.project_id == project_id)
    talks = q.order_by(models.ToolboxTalk.talk_date.desc()).all()
    return [{"id": t.id, "project_id": t.project_id, "topic": t.topic,
             "talk_date": str(t.talk_date), "conducted_by": t.conducted_by,
             "location": t.location, "duration_min": t.duration_min,
             "attendees_count": t.attendees_count, "key_points": t.key_points,
             "remarks": t.remarks} for t in talks]

@router.get("/toolbox/topics")
def toolbox_topic_library():
    return {"topics": TOOLBOX_TOPICS}

@router.post("/toolbox", status_code=201)
def create_toolbox(data: ToolboxTalkCreate, db: Session = Depends(get_db)):
    talk = models.ToolboxTalk(**data.model_dump())
    db.add(talk); db.commit(); db.refresh(talk)
    return {"id": talk.id, "topic": talk.topic, "message": "Toolbox talk recorded"}

@router.delete("/toolbox/{tid}")
def delete_toolbox(tid: int, db: Session = Depends(get_db)):
    t = db.query(models.ToolboxTalk).filter(models.ToolboxTalk.id == tid).first()
    if not t: raise HTTPException(404, "Not found")
    db.delete(t); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# PERMITS TO WORK
# ══════════════════════════════════════════════════════════════════════════════

PTW_PRECAUTIONS = {
    "hot_work": "Fire watch posted. Fire extinguisher (DCP 9kg) nearby. Flammable materials removed 10m radius. Permit valid 8 hours max.",
    "confined_space": "Atmosphere tested: O2 19.5-23.5%, LEL <10%, CO <25ppm. Continuous monitoring. Buddy system. Rescue equipment on standby.",
    "height_work": "Full-body harness + lanyard. Exclusion zone below (1.5x height). Work platform secured. Harness inspected daily.",
    "excavation": "Trench box or benching for depth >1.5m. Edge protection 1m from edge. Utilities located and marked. Daily inspection.",
    "electrical": "Isolation confirmed by authorised person. LOTO applied. Test before touch. Only competent electrician.",
    "radiography": "Exclusion zone established per radiation level. TLD badge worn. Adjacent areas notified. RSO approval required.",
}

def _ptw_dict(p):
    return {"id": p.id, "project_id": p.project_id, "permit_no": p.permit_no,
            "permit_type": p.permit_type, "title": p.title, "location": p.location,
            "scope_of_work": p.scope_of_work, "requested_by": p.requested_by,
            "contractor": p.contractor, "workers_involved": p.workers_involved,
            "start_datetime": str(p.start_datetime) if p.start_datetime else None,
            "end_datetime": str(p.end_datetime) if p.end_datetime else None,
            "precautions": p.precautions, "ppe_required": p.ppe_required,
            "issued_by": p.issued_by, "approved_by": p.approved_by,
            "status": p.status, "remarks": p.remarks}

@router.get("/permits")
def list_permits(project_id: Optional[int] = None, status: Optional[str] = None,
                 db: Session = Depends(get_db)):
    q = db.query(models.PermitToWork)
    if project_id: q = q.filter(models.PermitToWork.project_id == project_id)
    if status: q = q.filter(models.PermitToWork.status == status)
    return [_ptw_dict(p) for p in q.order_by(models.PermitToWork.created_at.desc()).all()]

@router.get("/permits/precautions/{permit_type}")
def get_precautions(permit_type: str):
    return {"permit_type": permit_type,
            "standard_precautions": PTW_PRECAUTIONS.get(permit_type, "")}

@router.post("/permits", status_code=201)
def create_permit(data: PTWCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    if not d.get("permit_no"):
        count = db.query(models.PermitToWork).count()
        d["permit_no"] = f"PTW-{count+1:04d}"
    if not d.get("precautions"):
        d["precautions"] = PTW_PRECAUTIONS.get(d.get("permit_type", ""), "")
    ptw = models.PermitToWork(**d)
    db.add(ptw); db.commit(); db.refresh(ptw)
    return _ptw_dict(ptw)

@router.post("/permits/{ptw_id}/approve")
def approve_permit(ptw_id: int, approved_by: str = "HSE Manager", db: Session = Depends(get_db)):
    ptw = db.query(models.PermitToWork).filter(models.PermitToWork.id == ptw_id).first()
    if not ptw: raise HTTPException(404, "Not found")
    ptw.status = "approved"; ptw.approved_by = approved_by
    db.commit(); return {"message": "PTW approved"}

@router.post("/permits/{ptw_id}/close")
def close_permit(ptw_id: int, closed_by: str = "Site Engineer", db: Session = Depends(get_db)):
    ptw = db.query(models.PermitToWork).filter(models.PermitToWork.id == ptw_id).first()
    if not ptw: raise HTTPException(404, "Not found")
    ptw.status = "closed"; ptw.closed_by = closed_by; ptw.closed_at = datetime.utcnow()
    db.commit(); return {"message": "PTW closed"}

@router.delete("/permits/{ptw_id}")
def delete_permit(ptw_id: int, db: Session = Depends(get_db)):
    ptw = db.query(models.PermitToWork).filter(models.PermitToWork.id == ptw_id).first()
    if not ptw: raise HTTPException(404, "Not found")
    db.delete(ptw); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# RISK ASSESSMENTS
# ══════════════════════════════════════════════════════════════════════════════

RISK_MATRIX = {
    (1,1): "low", (1,2): "low", (1,3): "low", (1,4): "medium", (1,5): "medium",
    (2,1): "low", (2,2): "low", (2,3): "medium", (2,4): "medium", (2,5): "high",
    (3,1): "low", (3,2): "medium", (3,3): "medium", (3,4): "high", (3,5): "critical",
    (4,1): "medium", (4,2): "medium", (4,3): "high", (4,4): "critical", (4,5): "critical",
    (5,1): "medium", (5,2): "high", (5,3): "critical", (5,4): "critical", (5,5): "critical",
}

def _risk_dict(r):
    return {"id": r.id, "project_id": r.project_id, "activity": r.activity,
            "hazard": r.hazard, "risk_description": r.risk_description,
            "likelihood": r.likelihood, "severity_score": r.severity_score,
            "risk_score": r.risk_score, "risk_level": r.risk_level,
            "control_measures": r.control_measures, "residual_risk": r.residual_risk,
            "responsible": r.responsible,
            "review_date": str(r.review_date) if r.review_date else None,
            "status": r.status}

@router.get("/risks")
def list_risks(project_id: Optional[int] = None, risk_level: Optional[str] = None,
               db: Session = Depends(get_db)):
    q = db.query(models.RiskAssessment)
    if project_id: q = q.filter(models.RiskAssessment.project_id == project_id)
    if risk_level: q = q.filter(models.RiskAssessment.risk_level == risk_level)
    return [_risk_dict(r) for r in q.order_by(models.RiskAssessment.risk_score.desc()).all()]

@router.post("/risks", status_code=201)
def create_risk(data: RiskAssessmentCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    score = d["likelihood"] * d["severity_score"]
    d["risk_score"] = score
    d["risk_level"] = RISK_MATRIX.get(
        (min(d["likelihood"], 5), min(d["severity_score"], 5)), "medium")
    risk = models.RiskAssessment(**d)
    db.add(risk); db.commit(); db.refresh(risk)
    return _risk_dict(risk)

@router.delete("/risks/{rid}")
def delete_risk(rid: int, db: Session = Depends(get_db)):
    r = db.query(models.RiskAssessment).filter(models.RiskAssessment.id == rid).first()
    if not r: raise HTTPException(404, "Not found")
    db.delete(r); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# SAFETY DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
def safety_dashboard(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q_inc = db.query(models.SafetyIncident)
    q_ptw = db.query(models.PermitToWork)
    q_tbx = db.query(models.ToolboxTalk)
    q_risk = db.query(models.RiskAssessment)
    if project_id:
        q_inc  = q_inc.filter(models.SafetyIncident.project_id == project_id)
        q_ptw  = q_ptw.filter(models.PermitToWork.project_id == project_id)
        q_tbx  = q_tbx.filter(models.ToolboxTalk.project_id == project_id)
        q_risk = q_risk.filter(models.RiskAssessment.project_id == project_id)

    incidents = q_inc.all()
    return {
        "total_incidents": len(incidents),
        "open_incidents":  sum(1 for i in incidents if not i.resolved),
        "injuries":        sum(1 for i in incidents if i.injuries),
        "near_miss":       sum(1 for i in incidents if i.incident_type == "near_miss"),
        "lti_days":        sum(i.lost_time_days for i in incidents),
        "open_ptw":        q_ptw.filter(models.PermitToWork.status.in_(["pending","approved","active"])).count(),
        "toolbox_talks":   q_tbx.count(),
        "critical_risks":  q_risk.filter(models.RiskAssessment.risk_level.in_(["critical","high"])).count(),
    }
