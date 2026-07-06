"""
Quality Control — Phase 5
Material Tests (Cube, Slump, Rebar), QC Inspections + Checklists,
Non-Conformance Reports, Punch List / Snag List
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
from database import get_db
import models

router = APIRouter(prefix="/quality", tags=["Quality Control"])


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class MaterialTestCreate(BaseModel):
    project_id: int
    test_type: str = "cube_compressive"
    test_date: date
    element: Optional[str] = None
    pour_reference: Optional[str] = None
    design_code: str = "IS"
    grade: Optional[str] = None
    sample_no: Optional[str] = None
    cube_size_mm: int = 150
    water_cement_ratio: Optional[float] = None
    slump_mm: Optional[float] = None
    cube1_7day_kN: Optional[float] = None
    cube2_7day_kN: Optional[float] = None
    cube3_7day_kN: Optional[float] = None
    cube1_28day_kN: Optional[float] = None
    cube2_28day_kN: Optional[float] = None
    cube3_28day_kN: Optional[float] = None
    rebar_dia_mm: Optional[int] = None
    yield_strength_MPa: Optional[float] = None
    uts_MPa: Optional[float] = None
    elongation_pct: Optional[float] = None
    lab_name: Optional[str] = None
    tested_by: Optional[str] = None
    witnessed_by: Optional[str] = None
    certificate_no: Optional[str] = None
    remarks: Optional[str] = None

class QCChecklistItemCreate(BaseModel):
    item_no: Optional[str] = None
    check_point: str
    reference: Optional[str] = None
    requirement: Optional[str] = None
    actual: Optional[str] = None
    status: str = "pending"
    remarks: Optional[str] = None

class QCInspectionCreate(BaseModel):
    project_id: int
    inspection_no: Optional[str] = None
    inspection_type: str = "pre_pour"
    element: Optional[str] = None
    floor_level: Optional[str] = None
    inspection_date: Optional[date] = None
    inspector_name: Optional[str] = None
    contractor_rep: Optional[str] = None
    consultant_rep: Optional[str] = None
    overall_remarks: Optional[str] = None
    checklist: List[QCChecklistItemCreate] = []

class NCRCreate(BaseModel):
    project_id: int
    ncr_no: Optional[str] = None
    title: str
    description: Optional[str] = None
    element: Optional[str] = None
    floor_level: Optional[str] = None
    nc_date: Optional[date] = None
    raised_by: Optional[str] = None
    assigned_to: Optional[str] = None
    severity: str = "medium"
    root_cause: Optional[str] = None
    immediate_action: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    due_date: Optional[date] = None
    cost_of_nc: float = 0.0

class PunchListCreate(BaseModel):
    project_id: int
    item_no: Optional[str] = None
    description: str
    location: Optional[str] = None
    raised_by: Optional[str] = None
    assigned_to: Optional[str] = None
    raised_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: str = "medium"
    remarks: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL TESTS — helpers
# ══════════════════════════════════════════════════════════════════════════════

def _compute_cube_results(d: dict) -> dict:
    """
    Auto-compute average strengths and pass/fail per IS 456 / ACI 318.
    IS 456 Cl. 16: Individual cube ≥ 0.85 × fck; average ≥ fck
    """
    area_mm2 = d.get("cube_size_mm", 150) ** 2

    def strength(kN):
        if kN is None: return None
        return round(kN * 1000 / area_mm2, 2)  # N/mm² = MPa

    s1_7 = strength(d.get("cube1_7day_kN"))
    s2_7 = strength(d.get("cube2_7day_kN"))
    s3_7 = strength(d.get("cube3_7day_kN"))
    s1_28 = strength(d.get("cube1_28day_kN"))
    s2_28 = strength(d.get("cube2_28day_kN"))
    s3_28 = strength(d.get("cube3_28day_kN"))

    vals_7  = [v for v in [s1_7, s2_7, s3_7] if v is not None]
    vals_28 = [v for v in [s1_28, s2_28, s3_28] if v is not None]

    avg_7  = round(sum(vals_7) / len(vals_7), 2) if vals_7 else None
    avg_28 = round(sum(vals_28) / len(vals_28), 2) if vals_28 else None

    if d.get("cube1_7day_kN") and d.get("avg_7day_kN") is None:
        d["avg_7day_kN"] = avg_7
    if d.get("cube1_28day_kN") and d.get("avg_28day_kN") is None:
        d["avg_28day_kN"] = avg_28

    d["fck_achieved_MPa"] = avg_28

    # Pass/fail on 28-day (IS 456 approach)
    if avg_28 is not None and d.get("grade"):
        grade_str = d["grade"].upper().replace("M", "")
        try:
            fck = float(grade_str.split("/")[0])
            min_individual = 0.85 * fck
            passes = avg_28 >= fck and all(v >= min_individual for v in vals_28)
            d["result"] = "pass" if passes else "fail"
        except (ValueError, IndexError):
            d["result"] = "pending"
    else:
        d["result"] = "pending"

    return d


# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL TESTS
# ══════════════════════════════════════════════════════════════════════════════

def _test_dict(t):
    return {
        "id": t.id, "project_id": t.project_id, "test_type": t.test_type,
        "test_date": str(t.test_date), "element": t.element,
        "pour_reference": t.pour_reference, "design_code": t.design_code,
        "grade": t.grade, "sample_no": t.sample_no, "cube_size_mm": t.cube_size_mm,
        "water_cement_ratio": t.water_cement_ratio, "slump_mm": t.slump_mm,
        "cube1_7day_kN": t.cube1_7day_kN, "cube2_7day_kN": t.cube2_7day_kN,
        "cube3_7day_kN": t.cube3_7day_kN, "avg_7day_kN": t.avg_7day_kN,
        "cube1_28day_kN": t.cube1_28day_kN, "cube2_28day_kN": t.cube2_28day_kN,
        "cube3_28day_kN": t.cube3_28day_kN, "avg_28day_kN": t.avg_28day_kN,
        "fck_achieved_MPa": t.fck_achieved_MPa, "result": t.result,
        "rebar_dia_mm": t.rebar_dia_mm, "yield_strength_MPa": t.yield_strength_MPa,
        "uts_MPa": t.uts_MPa, "elongation_pct": t.elongation_pct,
        "lab_name": t.lab_name, "tested_by": t.tested_by,
        "certificate_no": t.certificate_no, "remarks": t.remarks,
    }

@router.get("/tests/{project_id}")
def list_tests(project_id: int, test_type: Optional[str] = None,
               db: Session = Depends(get_db)):
    q = db.query(models.MaterialTest).filter(
        models.MaterialTest.project_id == project_id)
    if test_type: q = q.filter(models.MaterialTest.test_type == test_type)
    return [_test_dict(t) for t in q.order_by(models.MaterialTest.test_date.desc()).all()]

@router.post("/tests", status_code=201)
def create_test(data: MaterialTestCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    d = _compute_cube_results(d)
    test = models.MaterialTest(**d)
    db.add(test); db.commit(); db.refresh(test)
    return _test_dict(test)

@router.put("/tests/{test_id}")
def update_test(test_id: int, data: MaterialTestCreate, db: Session = Depends(get_db)):
    t = db.query(models.MaterialTest).filter(models.MaterialTest.id == test_id).first()
    if not t: raise HTTPException(404, "Not found")
    d = data.model_dump(exclude_none=True)
    d = _compute_cube_results(d)
    for k, v in d.items(): setattr(t, k, v)
    db.commit(); return _test_dict(t)

@router.delete("/tests/{test_id}")
def delete_test(test_id: int, db: Session = Depends(get_db)):
    t = db.query(models.MaterialTest).filter(models.MaterialTest.id == test_id).first()
    if not t: raise HTTPException(404, "Not found")
    db.delete(t); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# QC INSPECTIONS
# ══════════════════════════════════════════════════════════════════════════════

# Standard checklists per inspection type
STANDARD_CHECKLISTS = {
    "rebar": [
        ("1", "Bar diameter and spacing as per drawing", "IS 456 Cl. 26.3", "Per drawing"),
        ("2", "Cover blocks in position", "IS 456 Cl. 26.4", "Min 40mm for beam"),
        ("3", "Laps and splices as per BBS", "IS 456 Cl. 26.2.5", "Per BBS"),
        ("4", "Stirrups / links spacing correct", "IS 456 Cl. 40.4", "Per drawing"),
        ("5", "Cranking of bars as per drawing", "BBS", "Per BBS"),
        ("6", "Mechanical splices if used — approved coupler", "IS 456", "Certificate required"),
        ("7", "No rust, mud, or oil on bars", "IS 456 Cl. 5.6", "Clean surface"),
        ("8", "Chair/support bars in position", "Good practice", "Every 1.2m"),
    ],
    "formwork": [
        ("1", "Formwork plumb and level checked", "IS 456 Cl. 11", "Tolerance ±3mm"),
        ("2", "Props and bracing adequate", "IS 4014", "Per design"),
        ("3", "Joints sealed to prevent grout loss", "IS 456", "No gaps"),
        ("4", "Release agent applied uniformly", "Good practice", "Even coat"),
        ("5", "Embedded items and inserts fixed", "Drawings", "Per drawing"),
        ("6", "Openings for MEP services formed", "MEP drawings", "Per coord drawing"),
        ("7", "Surveyor sign-off on levels and lines", "Project QC Plan", "Written sign-off"),
    ],
    "pre_pour": [
        ("1", "Rebar inspection passed (ITP signed)", "Project ITP", "Signed off"),
        ("2", "Formwork inspection passed", "Project ITP", "Signed off"),
        ("3", "Concrete mix design approved", "IS 10262", "Approved mix"),
        ("4", "Slump target defined and communicated", "IS 456 Table 5", "Max 150mm"),
        ("5", "Cube moulds and water available on site", "IS 516", "3 sets minimum"),
        ("6", "Vibrators tested and functioning", "Good practice", "2 nos. minimum"),
        ("7", "Concrete pour card prepared", "QC Plan", "Card ready"),
        ("8", "Night lighting if pour extends to night", "Safety", "Adequate lux"),
    ],
    "concrete_finish": [
        ("1", "Concrete compacted uniformly (no honeycomb)", "IS 456 Cl. 13.3", "No voids"),
        ("2", "Top surface level / within tolerance", "IS 456", "±5mm"),
        ("3", "Curing compound applied or wet curing started", "IS 456 Cl. 13.5", "Min 7 days"),
        ("4", "Cube test samples taken (every 50 m3 or 3 cubes per pour)", "IS 456 Cl. 15", "3 cubes"),
        ("5", "Slump recorded at pour point", "IS 456", "Recorded"),
        ("6", "Pour card completed with start/end time", "QC Plan", "Signed"),
    ],
}

def _inspection_dict(insp, include_checklist=True):
    d = {"id": insp.id, "project_id": insp.project_id,
         "inspection_no": insp.inspection_no,
         "inspection_type": insp.inspection_type,
         "element": insp.element, "floor_level": insp.floor_level,
         "inspection_date": str(insp.inspection_date) if insp.inspection_date else None,
         "inspector_name": insp.inspector_name,
         "contractor_rep": insp.contractor_rep, "consultant_rep": insp.consultant_rep,
         "result": insp.result, "overall_remarks": insp.overall_remarks,
         "next_action": insp.next_action}
    if include_checklist:
        d["checklist"] = [
            {"id": ci.id, "item_no": ci.item_no, "check_point": ci.check_point,
             "reference": ci.reference, "requirement": ci.requirement,
             "actual": ci.actual, "status": ci.status, "remarks": ci.remarks}
            for ci in insp.checklist_items
        ]
        # Auto-calculate result
        items = insp.checklist_items
        if items:
            fails = sum(1 for i in items if i.status == "fail")
            passes = sum(1 for i in items if i.status == "pass")
            d["pass_count"] = passes
            d["fail_count"] = fails
    return d

@router.get("/inspections/{project_id}")
def list_inspections(project_id: int, db: Session = Depends(get_db)):
    insps = db.query(models.QCInspection).filter(
        models.QCInspection.project_id == project_id
    ).order_by(models.QCInspection.inspection_date.desc()).all()
    return [_inspection_dict(i, include_checklist=False) for i in insps]

@router.get("/inspections/{project_id}/{insp_id}")
def get_inspection(project_id: int, insp_id: int, db: Session = Depends(get_db)):
    insp = db.query(models.QCInspection).filter(
        models.QCInspection.id == insp_id,
        models.QCInspection.project_id == project_id
    ).first()
    if not insp: raise HTTPException(404, "Not found")
    return _inspection_dict(insp, include_checklist=True)

@router.get("/checklist-template/{inspection_type}")
def get_checklist_template(inspection_type: str):
    """Return standard checklist for an inspection type."""
    items = STANDARD_CHECKLISTS.get(inspection_type, [])
    return {"inspection_type": inspection_type,
            "items": [{"item_no": i[0], "check_point": i[1],
                        "reference": i[2], "requirement": i[3]}
                       for i in items]}

@router.post("/inspections", status_code=201)
def create_inspection(data: QCInspectionCreate, db: Session = Depends(get_db)):
    # Auto-generate inspection number if not provided
    insp_no = data.inspection_no
    if not insp_no:
        count = db.query(models.QCInspection).filter(
            models.QCInspection.project_id == data.project_id).count()
        insp_no = f"ITP-{data.project_id:03d}-{count+1:04d}"

    insp = models.QCInspection(
        project_id=data.project_id,
        inspection_no=insp_no,
        inspection_type=data.inspection_type,
        element=data.element,
        floor_level=data.floor_level,
        inspection_date=data.inspection_date,
        inspector_name=data.inspector_name,
        contractor_rep=data.contractor_rep,
        consultant_rep=data.consultant_rep,
        overall_remarks=data.overall_remarks,
    )
    db.add(insp); db.flush()

    # Use provided checklist or load standard template
    checklist_items = data.checklist
    if not checklist_items and data.inspection_type in STANDARD_CHECKLISTS:
        checklist_items = [
            QCChecklistItemCreate(item_no=i[0], check_point=i[1],
                                   reference=i[2], requirement=i[3])
            for i in STANDARD_CHECKLISTS[data.inspection_type]
        ]

    for ci in checklist_items:
        item = models.QCChecklistItem(
            inspection_id=insp.id,
            item_no=ci.item_no,
            check_point=ci.check_point,
            reference=ci.reference,
            requirement=ci.requirement,
            actual=ci.actual,
            status=ci.status,
            remarks=ci.remarks,
        )
        db.add(item)

    db.commit(); db.refresh(insp)
    return {"id": insp.id, "inspection_no": insp_no, "message": "Inspection created"}

@router.put("/inspections/{insp_id}/checklist")
def update_checklist(insp_id: int, items: List[QCChecklistItemCreate],
                      db: Session = Depends(get_db)):
    """Update all checklist items for an inspection (pass/fail/na results)."""
    insp = db.query(models.QCInspection).filter(models.QCInspection.id == insp_id).first()
    if not insp: raise HTTPException(404, "Not found")

    # Update existing items
    existing = {ci.item_no: ci for ci in insp.checklist_items}
    for item_data in items:
        if item_data.item_no in existing:
            ci = existing[item_data.item_no]
            ci.actual = item_data.actual
            ci.status = item_data.status
            ci.remarks = item_data.remarks

    # Auto result: fail if any item fails
    all_items = insp.checklist_items
    if all_items:
        has_fail = any(i.status == "fail" for i in all_items)
        all_done = all(i.status in ["pass", "fail", "na"] for i in all_items)
        if all_done:
            insp.result = "fail" if has_fail else "pass"

    db.commit()
    return {"message": "Checklist updated", "result": insp.result}

@router.delete("/inspections/{insp_id}")
def delete_inspection(insp_id: int, db: Session = Depends(get_db)):
    insp = db.query(models.QCInspection).filter(models.QCInspection.id == insp_id).first()
    if not insp: raise HTTPException(404, "Not found")
    db.delete(insp); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# NON-CONFORMANCE REPORTS (NCR)
# ══════════════════════════════════════════════════════════════════════════════

def _ncr_dict(n):
    return {"id": n.id, "project_id": n.project_id, "ncr_no": n.ncr_no,
            "title": n.title, "description": n.description,
            "element": n.element, "floor_level": n.floor_level,
            "nc_date": str(n.nc_date) if n.nc_date else None,
            "raised_by": n.raised_by, "assigned_to": n.assigned_to,
            "severity": n.severity, "root_cause": n.root_cause,
            "immediate_action": n.immediate_action,
            "corrective_action": n.corrective_action,
            "preventive_action": n.preventive_action,
            "due_date": str(n.due_date) if n.due_date else None,
            "closed_date": str(n.closed_date) if n.closed_date else None,
            "status": n.status, "cost_of_nc": n.cost_of_nc}

@router.get("/ncr/{project_id}")
def list_ncrs(project_id: int, status: Optional[str] = None,
              db: Session = Depends(get_db)):
    q = db.query(models.NCReport).filter(models.NCReport.project_id == project_id)
    if status: q = q.filter(models.NCReport.status == status)
    return [_ncr_dict(n) for n in q.order_by(models.NCReport.nc_date.desc()).all()]

@router.post("/ncr", status_code=201)
def create_ncr(data: NCRCreate, db: Session = Depends(get_db)):
    ncr_no = data.ncr_no
    if not ncr_no:
        count = db.query(models.NCReport).filter(
            models.NCReport.project_id == data.project_id).count()
        ncr_no = f"NCR-{data.project_id:03d}-{count+1:04d}"
    d = data.model_dump()
    d["ncr_no"] = ncr_no
    ncr = models.NCReport(**d)
    db.add(ncr); db.commit(); db.refresh(ncr)
    return _ncr_dict(ncr)

@router.put("/ncr/{ncr_id}")
def update_ncr(ncr_id: int, data: NCRCreate, db: Session = Depends(get_db)):
    ncr = db.query(models.NCReport).filter(models.NCReport.id == ncr_id).first()
    if not ncr: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items(): setattr(ncr, k, v)
    db.commit(); return _ncr_dict(ncr)

@router.post("/ncr/{ncr_id}/close")
def close_ncr(ncr_id: int, db: Session = Depends(get_db)):
    ncr = db.query(models.NCReport).filter(models.NCReport.id == ncr_id).first()
    if not ncr: raise HTTPException(404, "Not found")
    ncr.status = "closed"; ncr.closed_date = date.today()
    db.commit(); return {"message": "NCR closed"}

@router.delete("/ncr/{ncr_id}")
def delete_ncr(ncr_id: int, db: Session = Depends(get_db)):
    ncr = db.query(models.NCReport).filter(models.NCReport.id == ncr_id).first()
    if not ncr: raise HTTPException(404, "Not found")
    db.delete(ncr); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# PUNCH LIST / SNAG LIST
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/punch/{project_id}")
def list_punch(project_id: int, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.PunchListItem).filter(
        models.PunchListItem.project_id == project_id)
    if status: q = q.filter(models.PunchListItem.status == status)
    items = q.order_by(models.PunchListItem.raised_date.desc()).all()
    return [{"id": i.id, "item_no": i.item_no, "description": i.description,
             "location": i.location, "raised_by": i.raised_by, "assigned_to": i.assigned_to,
             "raised_date": str(i.raised_date) if i.raised_date else None,
             "due_date": str(i.due_date) if i.due_date else None,
             "closed_date": str(i.closed_date) if i.closed_date else None,
             "status": i.status, "priority": i.priority, "remarks": i.remarks}
            for i in items]

@router.post("/punch", status_code=201)
def create_punch(data: PunchListCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    if not d.get("item_no"):
        count = db.query(models.PunchListItem).filter(
            models.PunchListItem.project_id == data.project_id).count()
        d["item_no"] = f"SL-{count+1:04d}"
    item = models.PunchListItem(**d)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "item_no": item.item_no, "message": "Punch list item added"}

@router.post("/punch/{item_id}/close")
def close_punch(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.PunchListItem).filter(models.PunchListItem.id == item_id).first()
    if not item: raise HTTPException(404, "Not found")
    item.status = "closed"; item.closed_date = date.today()
    db.commit(); return {"message": "Closed"}

@router.delete("/punch/{item_id}")
def delete_punch(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.PunchListItem).filter(models.PunchListItem.id == item_id).first()
    if not item: raise HTTPException(404, "Not found")
    db.delete(item); db.commit(); return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# QA DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/{project_id}")
def qa_dashboard(project_id: int, db: Session = Depends(get_db)):
    """QA/QC KPIs for a project."""
    tests = db.query(models.MaterialTest).filter(
        models.MaterialTest.project_id == project_id).all()
    test_pass = sum(1 for t in tests if t.result == "pass")
    test_fail = sum(1 for t in tests if t.result == "fail")

    inspections = db.query(models.QCInspection).filter(
        models.QCInspection.project_id == project_id).all()
    insp_pass = sum(1 for i in inspections if i.result == "pass")
    insp_fail = sum(1 for i in inspections if i.result == "fail")

    ncrs = db.query(models.NCReport).filter(
        models.NCReport.project_id == project_id).all()
    ncr_open   = sum(1 for n in ncrs if n.status == "open")
    ncr_closed = sum(1 for n in ncrs if n.status == "closed")
    ncr_cost   = sum(n.cost_of_nc for n in ncrs)

    punch = db.query(models.PunchListItem).filter(
        models.PunchListItem.project_id == project_id).all()
    punch_open   = sum(1 for p in punch if p.status == "open")
    punch_closed = sum(1 for p in punch if p.status == "closed")

    # Concrete cube summary
    cube_tests = [t for t in tests if t.test_type == "cube_compressive"]
    avg_28day = None
    if cube_tests:
        vals = [t.fck_achieved_MPa for t in cube_tests if t.fck_achieved_MPa]
        if vals: avg_28day = round(sum(vals) / len(vals), 2)

    return {
        "tests": {"total": len(tests), "pass": test_pass, "fail": test_fail,
                  "pass_rate": round(test_pass / len(tests) * 100, 1) if tests else 0,
                  "avg_28day_strength_MPa": avg_28day},
        "inspections": {"total": len(inspections), "pass": insp_pass, "fail": insp_fail,
                         "pass_rate": round(insp_pass / len(inspections) * 100, 1) if inspections else 0},
        "ncr": {"total": len(ncrs), "open": ncr_open, "closed": ncr_closed,
                "cost": round(ncr_cost, 2)},
        "punch_list": {"total": len(punch), "open": punch_open, "closed": punch_closed,
                        "close_rate": round(punch_closed / len(punch) * 100, 1) if punch else 0},
    }
