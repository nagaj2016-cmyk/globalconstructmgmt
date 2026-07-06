"""
Phase 9 — Steel Design Router
IS 800:2007 + AISC 360-22 LRFD
Endpoints: beam design, column design, connections, section selector
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from structural.steel_is800 import (
    design_beam_IS800, design_column_IS800,
    design_bolt_IS800, design_fillet_weld_IS800,
    design_beam_AISC, design_column_AISC,
    select_beam_IS800, get_section_properties,
    IS_SECTIONS, AISC_SECTIONS, STEEL_GRADES_IS, BOLT_GRADES,
)
from proof_sources import attach_proof, proof_block

router = APIRouter(prefix="/steel", tags=["Steel Design"])

PROOF_IS800 = proof_block(
    "IS 800:2007",
    ["IS 800 steel member design", "IS 808 rolled steel sections", "IS 2062 steel grades"],
    ["india_bis"],
    "Preliminary steel design. Verify section database, steel certificates, connection restraint, fabrication tolerances, and local authority requirements.",
)
PROOF_IS800_CONNECTIONS = proof_block(
    "IS 800:2007",
    ["IS 800 bolted and welded connection provisions"],
    ["india_bis"],
    "Preliminary connection check. Verify eccentricity, prying, block shear, tear-out, net section, weld access, and fabrication/inspection requirements.",
)
PROOF_AISC = proof_block(
    "AISC 360",
    ["AISC 360 steel member design", "AISC shape database workflow"],
    ["aisc_360"],
    "Preliminary AISC steel design. Verify local building code adoption, official section properties, bracing, load combinations, and connection design.",
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class BeamIS800Req(BaseModel):
    section: str = Field("ISMB300", description="IS 808 section name")
    span_m: float = Field(6.0, gt=0)
    Md_kNm: float = Field(120.0, gt=0, description="Required moment demand (kNm)")
    Vd_kN: float  = Field(80.0,  gt=0, description="Required shear demand (kN)")
    grade: str    = Field("E250")
    Lz_m: Optional[float] = Field(None, description="Effective unbraced length (m); defaults to span")
    loading: Literal["udl", "point"] = Field("udl")

class ColumnIS800Req(BaseModel):
    section: str  = Field("ISMB300", description="IS 808 section name")
    P_kN: float   = Field(500.0, gt=0)
    Leff_m: float = Field(4.0,   gt=0)
    grade: str    = Field("E250")
    buckling_curve: Literal["a","b","c","d"] = Field("b")

class BoltIS800Req(BaseModel):
    dia_mm: float    = Field(20.0, description="Bolt diameter mm")
    n_bolts: int     = Field(4,    ge=1)
    n_shear_planes: int = Field(1, ge=1)
    P_kN: float      = Field(100.0, gt=0)
    plate_t_mm: float= Field(10.0,  gt=0)
    plate_fy: float  = Field(250.0)
    bolt_grade: str  = Field("8.8")

class WeldIS800Req(BaseModel):
    size_mm: float   = Field(8.0,   gt=0)
    length_mm: float = Field(200.0, gt=0)
    P_kN: float      = Field(80.0,  gt=0)
    grade: str       = Field("E250")

class BeamAISCReq(BaseModel):
    section: str   = Field("W18x97")
    span_ft: float = Field(20.0, gt=0)
    Mu_kip_ft: float = Field(150.0, gt=0)
    Vu_kips: float   = Field(40.0,  gt=0)
    Lb_ft: float     = Field(5.0,   gt=0)
    Fy_ksi: float    = Field(50.0)
    loading: Literal["udl","point"] = Field("udl")

class ColumnAISCReq(BaseModel):
    section: str    = Field("W14x48")
    Pu_kips: float  = Field(200.0, gt=0)
    KL_ft: float    = Field(14.0,  gt=0)
    Fy_ksi: float   = Field(50.0)

class SelectorReq(BaseModel):
    span_m: float  = Field(6.0,   gt=0)
    Md_kNm: float  = Field(120.0, gt=0)
    Vd_kN: float   = Field(80.0,  gt=0)
    grade: str     = Field("E250")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sections")
def list_sections(system: str = "IS"):
    """All steel sections in the database."""
    return {
        "system": system,
        "sections": get_section_properties(system),
        "grades": list(STEEL_GRADES_IS.keys()) if system.upper() == "IS" else ["A36(Fy=36ksi)", "A992(Fy=50ksi)"],
        "bolt_grades": list(BOLT_GRADES.keys()),
        "proof": PROOF_IS800 if system.upper() == "IS" else PROOF_AISC,
    }


@router.post("/beam/is800")
def beam_is800(req: BeamIS800Req):
    """IS 800:2007 beam design — bending, shear, LTB, deflection."""
    return attach_proof(design_beam_IS800(
        req.section, req.span_m, req.Md_kNm, req.Vd_kN,
        req.grade, req.Lz_m, req.loading
    ), PROOF_IS800)


@router.post("/column/is800")
def column_is800(req: ColumnIS800Req):
    """IS 800:2007 axial compression — buckling, slenderness check."""
    return attach_proof(design_column_IS800(
        req.section, req.P_kN, req.Leff_m, req.grade, req.buckling_curve
    ), PROOF_IS800)


@router.post("/bolt/is800")
def bolt_is800(req: BoltIS800Req):
    """IS 800:2007 Cl. 10.3 — bolted bearing-type connection."""
    return attach_proof(design_bolt_IS800(
        req.dia_mm, req.n_bolts, req.n_shear_planes, req.P_kN,
        req.plate_t_mm, req.plate_fy, req.bolt_grade
    ), PROOF_IS800_CONNECTIONS)


@router.post("/weld/is800")
def weld_is800(req: WeldIS800Req):
    """IS 800:2007 Cl. 10.5 — fillet weld design."""
    return attach_proof(design_fillet_weld_IS800(req.size_mm, req.length_mm, req.P_kN, req.grade), PROOF_IS800_CONNECTIONS)


@router.post("/beam/aisc")
def beam_aisc(req: BeamAISCReq):
    """AISC 360-22 LRFD beam — flexure F2, shear G2, deflection L/360."""
    return attach_proof(design_beam_AISC(
        req.section, req.span_ft, req.Mu_kip_ft, req.Vu_kips,
        req.Lb_ft, req.Fy_ksi, req.loading
    ), PROOF_AISC)


@router.post("/column/aisc")
def column_aisc(req: ColumnAISCReq):
    """AISC 360-22 LRFD compression member — Cl. E3."""
    return attach_proof(design_column_AISC(req.section, req.Pu_kips, req.KL_ft, req.Fy_ksi), PROOF_AISC)


@router.post("/select/beam")
def auto_select_beam(req: SelectorReq):
    """Auto-select lightest IS section satisfying all IS 800:2007 checks."""
    return attach_proof(select_beam_IS800(req.span_m, req.Md_kNm, req.Vd_kN, req.grade), PROOF_IS800)


@router.get("/grades")
def steel_grades():
    """Material grade properties (IS 2062)."""
    return {"grades": [{"grade": k, **v} for k, v in STEEL_GRADES_IS.items()], "proof": PROOF_IS800}
