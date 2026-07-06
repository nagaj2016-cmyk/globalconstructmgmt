"""
Phase 10 — BIM (Building Information Modelling) Router
Manages building models, elements (walls/slabs/columns/beams/etc.),
quantity takeoff, clash detection, and 3D viewer data.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json, math, uuid, os

from database import get_db
from models import BIMModel, BIMElement, ClashDetection, Project

router = APIRouter(prefix="/bim", tags=["BIM"])

# ── Element type catalogue ─────────────────────────────────────────────────────
ELEMENT_TYPES = [
    "Wall", "ExternalWall", "InternalWall", "CurtainWall",
    "Slab", "FloorSlab", "RoofSlab",
    "Column", "Beam",
    "Door", "Window",
    "Stair", "Ramp", "Roof",
    "Footing", "PileGroup",
    "MEP_Pipe", "MEP_Duct", "MEP_Equipment",
    "Furniture", "Other",
]

MATERIAL_PRESETS = {
    "Wall": ["Brick Masonry", "RCC", "AAC Block", "Drywall", "Glass"],
    "Slab": ["RCC M25", "RCC M30", "Precast", "Composite"],
    "Column": ["RCC M25", "RCC M30", "Steel", "Composite"],
    "Beam":   ["RCC M25", "RCC M30", "Steel I-Section", "Timber"],
    "Door":   ["Timber", "Steel", "UPVC", "Aluminium"],
    "Window": ["Aluminium", "UPVC", "Steel", "Timber"],
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class BIMModelCreate(BaseModel):
    project_id: int
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    total_floors: int = 1
    building_height_m: float = 0.0
    gross_area_m2: float = 0.0

class BIMModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    total_floors: Optional[int] = None
    building_height_m: Optional[float] = None
    gross_area_m2: Optional[float] = None

class BIMElementCreate(BaseModel):
    model_id: int
    element_type: str
    name: Optional[str] = None
    level: str = "Ground Floor"
    floor_number: int = 0
    material: Optional[str] = None
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    length_m: float = 1.0
    width_m: float = 0.2
    height_m: float = 3.0
    rotation_deg: float = 0.0
    mark: Optional[str] = None
    status: str = "design"
    properties: Optional[Dict[str, Any]] = None

class BIMElementUpdate(BaseModel):
    element_type: Optional[str] = None
    name: Optional[str] = None
    level: Optional[str] = None
    floor_number: Optional[int] = None
    material: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    rotation_deg: Optional[float] = None
    status: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

class ClashReq(BaseModel):
    model_id: int


# ── Helpers ────────────────────────────────────────────────────────────────────

def _calc_quantities(e: BIMElement) -> Dict[str, float]:
    """Recalculate volume and area from dimensions."""
    vol = e.length_m * e.width_m * e.height_m
    if e.element_type in ("Slab", "FloorSlab", "RoofSlab"):
        area = e.length_m * e.width_m
    else:
        area = e.length_m * e.height_m
    return {"volume_m3": round(vol, 4), "area_m2": round(area, 4)}


def _el_to_dict(e: BIMElement) -> dict:
    return {
        "id": e.id,
        "model_id": e.model_id,
        "ifc_guid": e.ifc_guid,
        "element_type": e.element_type,
        "name": e.name,
        "level": e.level,
        "floor_number": e.floor_number,
        "material": e.material,
        "position": {"x": e.pos_x, "y": e.pos_y, "z": e.pos_z},
        "dimensions": {"length": e.length_m, "width": e.width_m, "height": e.height_m},
        "rotation_deg": e.rotation_deg,
        "volume_m3": e.volume_m3,
        "area_m2": e.area_m2,
        "mark": e.mark,
        "status": e.status,
        "properties": e.properties or {},
        "created_at": str(e.created_at),
    }


def _model_to_dict(m: BIMModel) -> dict:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "name": m.name,
        "description": m.description,
        "version": m.version,
        "total_floors": m.total_floors,
        "building_height_m": m.building_height_m,
        "gross_area_m2": m.gross_area_m2,
        "file_format": m.file_format,
        "element_count": len(m.elements) if m.elements else 0,
        "created_at": str(m.created_at),
    }


# ── Model CRUD ─────────────────────────────────────────────────────────────────

@router.post("/models")
def create_model(req: BIMModelCreate, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == req.project_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    m = BIMModel(**req.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return _model_to_dict(m)


@router.get("/models")
def list_models(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(BIMModel)
    if project_id:
        q = q.filter(BIMModel.project_id == project_id)
    return [_model_to_dict(m) for m in q.order_by(BIMModel.id.desc()).all()]


@router.get("/models/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    m = db.query(BIMModel).filter(BIMModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    data = _model_to_dict(m)
    data["elements"] = [_el_to_dict(e) for e in m.elements]
    return data


@router.put("/models/{model_id}")
def update_model(model_id: int, req: BIMModelUpdate, db: Session = Depends(get_db)):
    m = db.query(BIMModel).filter(BIMModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    db.commit(); db.refresh(m)
    return _model_to_dict(m)


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    m = db.query(BIMModel).filter(BIMModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    db.delete(m); db.commit()
    return {"message": "Model deleted"}


# ── Element CRUD ───────────────────────────────────────────────────────────────

@router.post("/elements")
def create_element(req: BIMElementCreate, db: Session = Depends(get_db)):
    m = db.query(BIMModel).filter(BIMModel.id == req.model_id).first()
    if not m:
        raise HTTPException(404, "BIM model not found")
    data = req.model_dump()
    data["ifc_guid"] = str(uuid.uuid4()).upper()[:22]
    if not data.get("name"):
        count = db.query(BIMElement).filter(
            BIMElement.model_id == req.model_id,
            BIMElement.element_type == req.element_type
        ).count()
        data["name"] = f"{req.element_type}-{count+1:03d}"
    # Calculate quantities
    e_tmp = BIMElement(**data)
    q = _calc_quantities(e_tmp)
    data["volume_m3"] = q["volume_m3"]
    data["area_m2"] = q["area_m2"]
    e = BIMElement(**data)
    db.add(e); db.commit(); db.refresh(e)
    return _el_to_dict(e)


@router.get("/elements")
def list_elements(
    model_id: Optional[int] = None,
    element_type: Optional[str] = None,
    floor_number: Optional[int] = None,
    db: Session = Depends(get_db)
):
    q = db.query(BIMElement)
    if model_id:        q = q.filter(BIMElement.model_id == model_id)
    if element_type:    q = q.filter(BIMElement.element_type == element_type)
    if floor_number is not None: q = q.filter(BIMElement.floor_number == floor_number)
    return [_el_to_dict(e) for e in q.order_by(BIMElement.id).all()]


@router.get("/elements/{element_id}")
def get_element(element_id: int, db: Session = Depends(get_db)):
    e = db.query(BIMElement).filter(BIMElement.id == element_id).first()
    if not e:
        raise HTTPException(404, "Element not found")
    return _el_to_dict(e)


@router.put("/elements/{element_id}")
def update_element(element_id: int, req: BIMElementUpdate, db: Session = Depends(get_db)):
    e = db.query(BIMElement).filter(BIMElement.id == element_id).first()
    if not e:
        raise HTTPException(404, "Element not found")
    for k, v in req.model_dump(exclude_none=True).items():
        setattr(e, k, v)
    q = _calc_quantities(e)
    e.volume_m3 = q["volume_m3"]
    e.area_m2   = q["area_m2"]
    db.commit(); db.refresh(e)
    return _el_to_dict(e)


@router.delete("/elements/{element_id}")
def delete_element(element_id: int, db: Session = Depends(get_db)):
    e = db.query(BIMElement).filter(BIMElement.id == element_id).first()
    if not e:
        raise HTTPException(404, "Element not found")
    db.delete(e); db.commit()
    return {"message": "Element deleted"}


# ── Quantity Takeoff ───────────────────────────────────────────────────────────

@router.get("/models/{model_id}/takeoff")
def quantity_takeoff(model_id: int, db: Session = Depends(get_db)):
    """Generate structured quantity takeoff from all elements in the model."""
    m = db.query(BIMModel).filter(BIMModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")

    elements = db.query(BIMElement).filter(BIMElement.model_id == model_id).all()
    summary: Dict[str, Dict] = {}
    grand_vol = grand_area = 0.0
    floor_summary: Dict[str, Dict] = {}

    for e in elements:
        et = e.element_type
        if et not in summary:
            summary[et] = {"count": 0, "total_volume_m3": 0.0, "total_area_m2": 0.0,
                           "materials": {}}
        summary[et]["count"] += 1
        summary[et]["total_volume_m3"] += e.volume_m3 or 0
        summary[et]["total_area_m2"]   += e.area_m2   or 0
        mat = e.material or "Unknown"
        summary[et]["materials"][mat] = summary[et]["materials"].get(mat, 0) + 1
        grand_vol  += e.volume_m3 or 0
        grand_area += e.area_m2   or 0

        fl = e.level or "Unknown"
        if fl not in floor_summary:
            floor_summary[fl] = {"element_count": 0, "volume_m3": 0.0, "area_m2": 0.0}
        floor_summary[fl]["element_count"] += 1
        floor_summary[fl]["volume_m3"] += e.volume_m3 or 0
        floor_summary[fl]["area_m2"]   += e.area_m2   or 0

    # Round
    for v in summary.values():
        v["total_volume_m3"] = round(v["total_volume_m3"], 3)
        v["total_area_m2"]   = round(v["total_area_m2"],   3)

    return {
        "model_id": model_id,
        "model_name": m.name,
        "total_elements": len(elements),
        "total_volume_m3": round(grand_vol, 3),
        "total_area_m2": round(grand_area, 3),
        "by_element_type": summary,
        "by_floor": floor_summary,
    }


# ── Clash Detection (bounding-box AABB) ───────────────────────────────────────

@router.post("/models/{model_id}/clash-detect")
def run_clash_detection(model_id: int, db: Session = Depends(get_db)):
    """Simple axis-aligned bounding box clash detection."""
    elements = db.query(BIMElement).filter(BIMElement.model_id == model_id).all()

    # Remove old auto-clashes
    db.query(ClashDetection).filter(ClashDetection.model_id == model_id).delete()
    db.commit()

    clashes = []
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            # Skip same-floor check for vertical elements like columns/walls (z overlap only)
            ax1, ax2 = a.pos_x, a.pos_x + a.length_m
            ay1, ay2 = a.pos_y, a.pos_y + a.width_m
            az1, az2 = a.pos_z, a.pos_z + a.height_m
            bx1, bx2 = b.pos_x, b.pos_x + b.length_m
            by1, by2 = b.pos_y, b.pos_y + b.width_m
            bz1, bz2 = b.pos_z, b.pos_z + b.height_m

            # AABB overlap test
            if (ax1 < bx2 and ax2 > bx1 and
                ay1 < by2 and ay2 > by1 and
                az1 < bz2 and az2 > bz1):
                # Compute penetration depth
                ox = min(ax2, bx2) - max(ax1, bx1)
                oy = min(ay2, by2) - max(ay1, by1)
                oz = min(az2, bz2) - max(az1, bz1)
                depth = min(ox, oy, oz)
                severity = "major" if depth > 0.1 else "minor"
                cl = ClashDetection(
                    model_id=model_id,
                    element_a_id=a.id,
                    element_b_id=b.id,
                    clash_type="hard",
                    severity=severity,
                    status="open",
                    description=(
                        f"AABB clash: {a.name or a.element_type} vs {b.name or b.element_type} "
                        f"| penetration ~{depth:.3f}m"
                    ),
                )
                db.add(cl)
                clashes.append({
                    "element_a": a.name or a.element_type,
                    "element_b": b.name or b.element_type,
                    "severity": severity,
                    "penetration_m": round(depth, 3),
                })

    db.commit()
    return {
        "model_id": model_id,
        "clashes_found": len(clashes),
        "elements_checked": len(elements),
        "clashes": clashes,
    }


@router.get("/models/{model_id}/clashes")
def get_clashes(model_id: int, db: Session = Depends(get_db)):
    rows = db.query(ClashDetection).filter(ClashDetection.model_id == model_id).all()
    return [
        {
            "id": c.id,
            "element_a_id": c.element_a_id,
            "element_b_id": c.element_b_id,
            "clash_type": c.clash_type,
            "severity": c.severity,
            "status": c.status,
            "description": c.description,
            "detected_at": str(c.detected_at),
        }
        for c in rows
    ]


# ── 3D Viewer Data ─────────────────────────────────────────────────────────────

@router.get("/models/{model_id}/viewer-data")
def get_viewer_data(model_id: int, db: Session = Depends(get_db)):
    """Return optimised JSON for Three.js frontend viewer."""
    m = db.query(BIMModel).filter(BIMModel.id == model_id).first()
    if not m:
        raise HTTPException(404, "Model not found")
    elements = db.query(BIMElement).filter(BIMElement.model_id == model_id).all()

    # Color map by element type — industry-standard visual language
    COLORS = {
        "Column":       "#8d99ae",   # concrete medium-gray
        "Beam":         "#5c6bc0",   # structural indigo-blue
        "Slab":         "#b0bec5",   # light concrete
        "FloorSlab":    "#cfd8dc",
        "RoofSlab":     "#90a4ae",
        "Footing":      "#78909c",   # darker foundation concrete
        "Wall":         "#d4a373",   # warm brick/masonry
        "ExternalWall": "#c1956e",
        "InternalWall": "#e9c46a",
        "CurtainWall":  "#a8dadc",   # glass curtain wall
        "Door":         "#a0856e",
        "Window":       "#90e0ef",   # glass blue
        "Staircase":    "#f4a261",   # orange accent
        "Stair":        "#f4a261",
        "Ramp":         "#e9c46a",
        "SteelColumn":  "#546e7a",
        "SteelBeam":    "#37474f",
        "MEP_Pipe":     "#2d6a4f",
        "MEP_Duct":     "#74c69d",
        "Roof":         "#6c757d",
        "Other":        "#ced4da",
    }

    objects = []
    for e in elements:
        objects.append({
            "id": e.id,
            "type": e.element_type,
            "name": e.name,
            "level": e.level,
            "floor": e.floor_number,
            "pos": [e.pos_x, e.pos_z, -e.pos_y],   # Three.js Y-up
            "size": [
                max(e.length_m, 0.01),
                max(e.height_m, 0.01),
                max(e.width_m,  0.01),
            ],
            "rotation": e.rotation_deg,
            "color": COLORS.get(e.element_type, "#ced4da"),
            "material": e.material,
            "status": e.status,
        })

    floors = sorted(list({e.floor_number for e in elements}))
    return {
        "model": {
            "id": m.id, "name": m.name, "version": m.version,
            "total_floors": m.total_floors,
            "height_m": m.building_height_m,
        },
        "objects": objects,
        "stats": {
            "total": len(objects),
            "floors": floors,
            "by_type": {
                t: sum(1 for e in elements if e.element_type == t)
                for t in set(e.element_type for e in elements)
            },
        },
    }


# ── Meta ───────────────────────────────────────────────────────────────────────

@router.get("/element-types")
def element_types():
    return {"types": ELEMENT_TYPES, "material_presets": MATERIAL_PRESETS}
