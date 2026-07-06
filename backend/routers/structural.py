"""
Structural Engineering API — Phase 2
All endpoints return JSON results from IS-code calculation engines
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from structural.loads     import calculate_dead_loads, calculate_wind_load, calculate_seismic_load, load_combination, LIVE_LOAD_TABLE, UNIT_WEIGHTS, WIND_SPEED_CITY, CITY_SEISMIC_ZONE
from structural.rcc_beam  import design_beam
from structural.rcc_column import design_column_axial, design_column_uniaxial
from structural.rcc_slab  import design_one_way_slab, design_two_way_slab
from structural.foundation import design_isolated_footing
from structural.bbs       import generate_beam_bbs, generate_column_bbs, generate_slab_bbs, generate_footing_bbs, consolidate_bbs
from structural.mix_design import design_mix
from structural.boq       import boq_beam, boq_column, boq_slab, boq_footing, generate_structural_boq
from proof_sources import attach_proof, proof_block

router = APIRouter(prefix="/structural", tags=["Structural Engineering"])

PROOF_IS_LOADS = proof_block(
    "Indian Standards",
    ["IS 875 load provisions", "IS 1893 seismic provisions", "IS 456 load combination workflow"],
    ["india_bis", "india_nbc"],
    "Static reference tables are embedded for fast preliminary design. Verify exact project occupancy, wind speed, seismic zone, and local authority requirements.",
)
PROOF_IS_CONCRETE = proof_block(
    "IS 456:2000",
    ["IS 456 limit state design", "IS 456 detailing and serviceability provisions"],
    ["india_bis"],
    "Preliminary reinforced concrete design. Final drawings must verify detailing, durability, fire, ductility, and local amendments.",
)
PROOF_IS_BBS = proof_block(
    "IS 456:2000",
    ["IS 456 reinforcement detailing", "IS 2502 bar bending schedule practice"],
    ["india_bis"],
    "Bar lengths are generated from input geometry and detailing assumptions. Verify bend deductions, lap locations, hooks, couplers, and site drawing notes.",
)
PROOF_IS_MIX = proof_block(
    "IS 10262 / IS 456",
    ["IS 10262 concrete mix proportioning", "IS 456 durability requirements"],
    ["india_bis"],
    "Preliminary mix proportioning. Trial mixes, material test certificates, exposure class, admixture compatibility, and plant calibration govern production use.",
)
PROOF_BOQ = proof_block(
    "Project quantity workflow",
    ["Measurement is based on project drawings and local contract method of measurement"],
    ["india_bis"],
    "BOQ values are generated from user-entered member geometry and quantities. Contract documents and local measurement rules govern billing.",
)


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD CALCULATORS
# ═══════════════════════════════════════════════════════════════════════════════

class DeadLoadInput(BaseModel):
    slab_thickness_mm: float = Field(150, ge=75, le=400)
    floor_finish_kn_m2: float = Field(1.0, ge=0)
    partition_kn_m2: float = Field(1.0, ge=0)
    ceiling_kn_m2: float = Field(0.25, ge=0)
    wall_thickness_mm: float = Field(0, ge=0)
    wall_height_m: float = Field(0, ge=0)

class WindLoadInput(BaseModel):
    city: str = "Mumbai"
    building_height_m: float = Field(15, ge=3, le=300)
    terrain_category: str = "2"
    structure_class: str = "B_general"
    topography: str = "flat"
    custom_vb: Optional[float] = None

class SeismicLoadInput(BaseModel):
    city: str = "Mumbai"
    total_seismic_weight_kn: float = Field(5000, ge=100)
    building_height_m: float = Field(15, ge=3)
    num_floors: int = Field(5, ge=1, le=50)
    soil_type: str = "II"
    response_reduction: float = Field(5.0, ge=1, le=9)
    building_use: str = "residential"
    custom_zone: Optional[str] = None

class LoadCombinationInput(BaseModel):
    DL: float
    LL: float
    WL: float = 0
    EQ: float = 0

@router.get("/loads/tables")
def get_load_tables():
    """Reference tables: live loads, unit weights, wind speeds, seismic zones."""
    return {
        "live_loads_kN_m2": LIVE_LOAD_TABLE,
        "unit_weights_kN_m3": UNIT_WEIGHTS,
        "wind_speeds_by_city": WIND_SPEED_CITY,
        "seismic_zones_by_city": CITY_SEISMIC_ZONE,
        "proof": PROOF_IS_LOADS,
    }

@router.post("/loads/dead")
def calc_dead_load(data: DeadLoadInput):
    return attach_proof(calculate_dead_loads(
        slab_thickness_mm=data.slab_thickness_mm,
        floor_finish_kn_m2=data.floor_finish_kn_m2,
        partition_kn_m2=data.partition_kn_m2,
        ceiling_kn_m2=data.ceiling_kn_m2,
        wall_thickness_mm=data.wall_thickness_mm,
        wall_height_m=data.wall_height_m,
    ), PROOF_IS_LOADS)

@router.post("/loads/wind")
def calc_wind_load(data: WindLoadInput):
    return attach_proof(calculate_wind_load(
        city=data.city,
        building_height_m=data.building_height_m,
        terrain_category=data.terrain_category,
        structure_class=data.structure_class,
        topography=data.topography,
        custom_vb=data.custom_vb,
    ), proof_block(
        "IS 875 Part 3",
        ["IS 875 Part 3 wind loads", "National Building Code of India wind design references"],
        ["india_bis", "india_nbc"],
        "Wind result uses stored basic wind speed data or user override. Confirm current wind map, terrain, topography, shielding, and local authority requirements.",
    ))

@router.post("/loads/seismic")
def calc_seismic_load(data: SeismicLoadInput):
    return attach_proof(calculate_seismic_load(
        city=data.city,
        total_seismic_weight_kn=data.total_seismic_weight_kn,
        building_height_m=data.building_height_m,
        num_floors=data.num_floors,
        soil_type=data.soil_type,
        response_reduction=data.response_reduction,
        building_use=data.building_use,
        custom_zone=data.custom_zone,
    ), proof_block(
        "IS 1893",
        ["IS 1893 seismic zone and equivalent static analysis provisions"],
        ["india_bis", "india_nbc"],
        "Seismic result uses city/zone lookup or user override. Confirm exact coordinates, soil class, importance, ductility, irregularity, and local seismic requirements.",
    ))

@router.post("/loads/combination")
def calc_load_combination(data: LoadCombinationInput):
    return attach_proof(load_combination(data.DL, data.LL, data.WL, data.EQ), PROOF_IS_LOADS)


# ═══════════════════════════════════════════════════════════════════════════════
# BEAM DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class BeamDesignInput(BaseModel):
    span_m: float = Field(5.0, ge=0.5, le=30)
    Mu_kNm: float = Field(80, ge=0)
    Vu_kN: float = Field(60, ge=0)
    beam_type: str = "simply_supported"
    b_mm: float = Field(230, ge=150, le=1000)
    D_mm: Optional[float] = None
    fck: float = Field(25, ge=15, le=50)
    fy: float = Field(415, ge=250, le=600)
    cover_mm: float = Field(25, ge=15, le=75)
    stirrup_dia_mm: float = Field(8, ge=6, le=16)
    main_bar_dia_mm: float = Field(16, ge=10, le=32)

@router.post("/beam/design")
def beam_design(data: BeamDesignInput):
    return attach_proof(design_beam(
        span_m=data.span_m, Mu_kNm=data.Mu_kNm, Vu_kN=data.Vu_kN,
        beam_type=data.beam_type, b_mm=data.b_mm, D_mm=data.D_mm,
        fck=data.fck, fy=data.fy, cover_mm=data.cover_mm,
        stirrup_dia_mm=data.stirrup_dia_mm, main_bar_dia_mm=data.main_bar_dia_mm,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 flexure", "IS 456 shear", "IS 456 deflection", "IS 456 detailing"],
        ["india_bis"],
        "Preliminary RCC beam design. Verify ductile detailing, development length, torsion, serviceability, exposure, and final bar arrangement.",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class ColumnAxialInput(BaseModel):
    Pu_kN: float = Field(800, ge=10)
    height_m: float = Field(3.0, ge=2, le=15)
    b_mm: float = Field(300, ge=200, le=1200)
    D_mm: float = Field(300, ge=200, le=1200)
    fck: float = Field(25, ge=15, le=50)
    fy: float = Field(415, ge=250, le=600)
    end_condition: str = "both_fixed"
    cover_mm: float = Field(40, ge=25, le=75)
    bar_dia_mm: float = Field(16, ge=12, le=32)

class ColumnUniaxialInput(ColumnAxialInput):
    Mu_kNm: float = Field(50, ge=0)

@router.post("/column/design/axial")
def column_axial(data: ColumnAxialInput):
    return attach_proof(design_column_axial(
        Pu_kN=data.Pu_kN, height_m=data.height_m,
        b_mm=data.b_mm, D_mm=data.D_mm, fck=data.fck, fy=data.fy,
        end_condition=data.end_condition, cover_mm=data.cover_mm,
        bar_dia_mm=data.bar_dia_mm,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 compression member design", "IS 456 slenderness and detailing"],
        ["india_bis"],
        "Preliminary axial column design. Verify minimum eccentricity, slenderness, biaxial effects, ties, ductile detailing, and second-order effects.",
    ))

@router.post("/column/design/uniaxial")
def column_uniaxial(data: ColumnUniaxialInput):
    return attach_proof(design_column_uniaxial(
        Pu_kN=data.Pu_kN, Mu_kNm=data.Mu_kNm, height_m=data.height_m,
        b_mm=data.b_mm, D_mm=data.D_mm, fck=data.fck, fy=data.fy,
        end_condition=data.end_condition, cover_mm=data.cover_mm,
        bar_dia_mm=data.bar_dia_mm,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 column axial load and uniaxial bending", "IS 456 minimum eccentricity"],
        ["india_bis"],
        "Preliminary uniaxial column design. Verify full interaction, biaxial moments, slenderness magnification, ductile detailing, and load combinations.",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# SLAB DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class OneWaySlabInput(BaseModel):
    span_m: float = Field(3.5, ge=1, le=8)
    total_load_kN_m2: float = Field(8, ge=1)
    fck: float = Field(25, ge=15, le=50)
    fy: float = Field(415, ge=250, le=600)
    support: str = "simply_supported"
    cover_mm: float = Field(20, ge=15, le=50)
    main_bar_dia_mm: float = Field(10, ge=8, le=20)
    dist_bar_dia_mm: float = Field(8, ge=6, le=12)

class TwoWaySlabInput(BaseModel):
    lx_m: float = Field(3.5, ge=1, le=8)
    ly_m: float = Field(4.5, ge=1, le=12)
    total_load_kN_m2: float = Field(8, ge=1)
    fck: float = Field(25, ge=15, le=50)
    fy: float = Field(415, ge=250, le=600)
    cover_mm: float = Field(20, ge=15, le=50)
    main_bar_dia_mm: float = Field(10, ge=8, le=20)

@router.post("/slab/design/oneway")
def slab_oneway(data: OneWaySlabInput):
    return attach_proof(design_one_way_slab(
        span_m=data.span_m, total_load_kN_m2=data.total_load_kN_m2,
        fck=data.fck, fy=data.fy, support=data.support,
        cover_mm=data.cover_mm, main_bar_dia_mm=data.main_bar_dia_mm,
        dist_bar_dia_mm=data.dist_bar_dia_mm,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 slab flexure", "IS 456 minimum reinforcement", "IS 456 shear and deflection"],
        ["india_bis"],
        "Preliminary one-way slab design. Verify support continuity, deflection, crack control, distribution steel, openings, and detailing.",
    ))

@router.post("/slab/design/twoway")
def slab_twoway(data: TwoWaySlabInput):
    return attach_proof(design_two_way_slab(
        lx_m=data.lx_m, ly_m=data.ly_m, total_load_kN_m2=data.total_load_kN_m2,
        fck=data.fck, fy=data.fy, cover_mm=data.cover_mm,
        main_bar_dia_mm=data.main_bar_dia_mm,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 two-way slab coefficients", "IS 456 Table 26", "IS 456 detailing provisions"],
        ["india_bis"],
        "Preliminary two-way slab design. Verify edge restraint case, torsion steel, punching, openings, deflection, and final detailing.",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# FOUNDATION DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class FootingInput(BaseModel):
    Pu_kN: float = Field(800, ge=10)
    Mu_kNm: float = Field(0, ge=0)
    fck: float = Field(25, ge=15, le=50)
    fy: float = Field(415, ge=250, le=600)
    sbc_kN_m2: float = Field(150, ge=50, le=500)
    col_b_mm: float = Field(300, ge=200, le=800)
    col_D_mm: float = Field(300, ge=200, le=800)
    cover_mm: float = Field(50, ge=40, le=75)
    bar_dia_mm: float = Field(12, ge=10, le=20)
    depth_of_foundation_m: float = Field(1.5, ge=0.5, le=5)

@router.post("/foundation/design")
def footing_design(data: FootingInput):
    return attach_proof(design_isolated_footing(
        Pu_kN=data.Pu_kN, Mu_kNm=data.Mu_kNm,
        fck=data.fck, fy=data.fy, sbc_kN_m2=data.sbc_kN_m2,
        col_b_mm=data.col_b_mm, col_D_mm=data.col_D_mm,
        cover_mm=data.cover_mm, bar_dia_mm=data.bar_dia_mm,
        depth_of_foundation_m=data.depth_of_foundation_m,
    ), proof_block(
        "IS 456:2000",
        ["IS 456 isolated footing flexure", "IS 456 one-way shear", "IS 456 punching shear"],
        ["india_bis"],
        "Preliminary isolated footing design. Soil bearing must come from project geotechnical report and local foundation requirements.",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# BAR BENDING SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════

class BeamBBSInput(BaseModel):
    beam_id: str = "B1"
    span_mm: float = Field(5000, ge=500)
    b_mm: float = Field(230, ge=150)
    D_mm: float = Field(450, ge=200)
    cover_mm: float = Field(25, ge=15)
    main_bar_dia_mm: float = Field(16, ge=10, le=32)
    n_main_bars: int = Field(3, ge=2, le=10)
    stirrup_dia_mm: float = Field(8, ge=6, le=16)
    stirrup_spacing_mm: float = Field(150, ge=75, le=300)
    extra_top_dia_mm: float = Field(0, ge=0)
    n_extra_top: int = Field(0, ge=0)
    Ld_mm: float = Field(470, ge=200, le=1500)

class ColumnBBSInput(BaseModel):
    col_id: str = "C1"
    height_mm: float = Field(3000, ge=1000)
    b_mm: float = Field(300, ge=200)
    D_mm: float = Field(300, ge=200)
    cover_mm: float = Field(40, ge=25)
    main_bar_dia_mm: float = Field(16, ge=12, le=32)
    n_main_bars: int = Field(4, ge=4, le=20)
    tie_dia_mm: float = Field(8, ge=6, le=12)
    tie_spacing_mm: float = Field(150, ge=75, le=300)

class SlabBBSInput(BaseModel):
    slab_id: str = "S1"
    lx_mm: float = Field(3500, ge=1000)
    ly_mm: float = Field(4500, ge=1000)
    D_mm: float = Field(150, ge=75)
    cover_mm: float = Field(20, ge=15)
    main_dia_mm: float = Field(10, ge=8, le=20)
    main_spacing_mm: float = Field(150, ge=75, le=300)
    dist_dia_mm: float = Field(8, ge=6, le=16)
    dist_spacing_mm: float = Field(200, ge=75, le=450)

@router.post("/bbs/beam")
def bbs_beam(data: BeamBBSInput):
    return attach_proof(generate_beam_bbs(
        beam_id=data.beam_id, span_mm=data.span_mm,
        b_mm=data.b_mm, D_mm=data.D_mm, cover_mm=data.cover_mm,
        main_bar_dia_mm=data.main_bar_dia_mm, n_main_bars=data.n_main_bars,
        stirrup_dia_mm=data.stirrup_dia_mm, stirrup_spacing_mm=data.stirrup_spacing_mm,
        extra_top_dia_mm=data.extra_top_dia_mm, n_extra_top=data.n_extra_top,
        Ld_mm=data.Ld_mm,
    ), PROOF_IS_BBS)

@router.post("/bbs/column")
def bbs_column(data: ColumnBBSInput):
    return attach_proof(generate_column_bbs(
        col_id=data.col_id, height_mm=data.height_mm,
        b_mm=data.b_mm, D_mm=data.D_mm, cover_mm=data.cover_mm,
        main_bar_dia_mm=data.main_bar_dia_mm, n_main_bars=data.n_main_bars,
        tie_dia_mm=data.tie_dia_mm, tie_spacing_mm=data.tie_spacing_mm,
    ), PROOF_IS_BBS)

@router.post("/bbs/slab")
def bbs_slab(data: SlabBBSInput):
    return attach_proof(generate_slab_bbs(
        slab_id=data.slab_id, lx_mm=data.lx_mm, ly_mm=data.ly_mm,
        D_mm=data.D_mm, cover_mm=data.cover_mm,
        main_dia_mm=data.main_dia_mm, main_spacing_mm=data.main_spacing_mm,
        dist_dia_mm=data.dist_dia_mm, dist_spacing_mm=data.dist_spacing_mm,
    ), PROOF_IS_BBS)


# ═══════════════════════════════════════════════════════════════════════════════
# CONCRETE MIX DESIGN
# ═══════════════════════════════════════════════════════════════════════════════

class MixDesignInput(BaseModel):
    grade: str = "M25"
    exposure: str = "moderate"
    nominal_agg_size_mm: int = Field(20, ge=10, le=40)
    fa_zone: str = "II"
    slump_mm: int = Field(75, ge=25, le=200)
    cement_sg: float = Field(3.15, ge=3.0, le=3.3)
    fa_sg: float = Field(2.65, ge=2.4, le=2.8)
    ca_sg: float = Field(2.70, ge=2.4, le=2.9)
    admixture_percent: float = Field(0.0, ge=0, le=2)
    flyash_percent: float = Field(0.0, ge=0, le=35)

@router.post("/mix-design")
def concrete_mix_design(data: MixDesignInput):
    return attach_proof(design_mix(
        grade=data.grade, exposure=data.exposure,
        nominal_agg_size_mm=data.nominal_agg_size_mm,
        fa_zone=data.fa_zone, slump_mm=data.slump_mm,
        cement_sg=data.cement_sg, fa_sg=data.fa_sg, ca_sg=data.ca_sg,
        admixture_percent=data.admixture_percent,
        flyash_percent=data.flyash_percent,
    ), PROOF_IS_MIX)


# ═══════════════════════════════════════════════════════════════════════════════
# BOQ GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class BOQBeamInput(BaseModel):
    beam_id: str = "B1"
    span_m: float = 5.0
    b_mm: float = 230
    D_mm: float = 450
    n_spans: int = 1
    steel_kg: float = 85
    concrete_grade: str = "M25"
    fy: int = 415

class BOQColumnInput(BaseModel):
    col_id: str = "C1"
    height_m: float = 3.0
    b_mm: float = 300
    D_mm: float = 300
    n_columns: int = 1
    steel_kg: float = 45
    concrete_grade: str = "M25"
    fy: int = 415

class BOQSlabInput(BaseModel):
    slab_id: str = "S1"
    lx_m: float = 3.5
    ly_m: float = 4.5
    D_mm: float = 150
    n_panels: int = 1
    steel_kg: float = 120
    concrete_grade: str = "M25"
    fy: int = 415

class BOQFootingInput(BaseModel):
    fdn_id: str = "F1"
    L_m: float = 1.8
    B_m: float = 1.8
    D_mm: float = 400
    n_footings: int = 1
    steel_kg: float = 35
    concrete_grade: str = "M25"
    fy: int = 415

class ProjectBOQInput(BaseModel):
    beams:    List[BOQBeamInput] = []
    columns:  List[BOQColumnInput] = []
    slabs:    List[BOQSlabInput] = []
    footings: List[BOQFootingInput] = []

@router.post("/boq/beam")
def boq_beam_single(data: BOQBeamInput):
    return attach_proof(boq_beam(data.beam_id, data.span_m, data.b_mm, data.D_mm,
                    data.n_spans, data.steel_kg, data.concrete_grade, data.fy), PROOF_BOQ)

@router.post("/boq/generate")
def boq_generate(data: ProjectBOQInput):
    elements = []
    for b in data.beams:
        elements.append(boq_beam(b.beam_id, b.span_m, b.b_mm, b.D_mm, b.n_spans, b.steel_kg, b.concrete_grade, b.fy))
    for c in data.columns:
        elements.append(boq_column(c.col_id, c.height_m, c.b_mm, c.D_mm, c.n_columns, c.steel_kg, c.concrete_grade, c.fy))
    for s in data.slabs:
        elements.append(boq_slab(s.slab_id, s.lx_m, s.ly_m, s.D_mm, s.n_panels, s.steel_kg, s.concrete_grade, s.fy))
    for f in data.footings:
        elements.append(boq_footing(f.fdn_id, f.L_m, f.B_m, f.D_mm, f.n_footings, f.steel_kg,
                                    concrete_grade=f.concrete_grade, fy=f.fy))
    return attach_proof(generate_structural_boq(elements), PROOF_BOQ)
