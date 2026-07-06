"""
Engineering reference libraries — section catalogues for calculator dropdowns.
Reads the same section tables the steel calculators use, so the UI and the
calculations always agree on section properties.
"""
from fastapi import APIRouter, Depends, HTTPException
from database import get_db  # noqa: F401 (keeps route under the protected prefix)

from structural.steel_is800 import IS_SECTIONS, AISC_SECTIONS

router = APIRouter(prefix="/library", tags=["Reference Library"])

_SYSTEMS = {
    "IS": {"label": "IS 808 (Indian) rolled sections", "sections": IS_SECTIONS},
    "AISC": {"label": "AISC (US) W-sections", "sections": AISC_SECTIONS},
}


@router.get("/sections")
def list_sections(system: str = "IS"):
    key = system.upper()
    if key not in _SYSTEMS:
        raise HTTPException(status_code=404,
                            detail=f"Unknown system '{system}'. Available: {list(_SYSTEMS)}")
    data = _SYSTEMS[key]
    return {
        "system": key, "label": data["label"], "count": len(data["sections"]),
        "sections": [{"name": name, **props} for name, props in data["sections"].items()],
    }


@router.get("/systems")
def list_systems():
    return [{"system": k, "label": v["label"], "count": len(v["sections"])}
            for k, v in _SYSTEMS.items()]
