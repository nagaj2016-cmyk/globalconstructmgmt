"""
International Structural Codes Router — Phase 8
NBCC 2020 (Canada), ASCE 7-22 / ACI 318-19 (USA), EN 1991/1992/1998 (Eurocode)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from structural.intl_codes import (
    get_live_load, load_combinations, material_strengths,
    calc_wind_nbcc, calc_wind_asce, calc_wind_eurocode,
    calc_seismic_nbcc, calc_seismic_asce, calc_seismic_eurocode,
    calc_snow_nbcc, calc_snow_asce, calc_snow_eurocode,
    NBCC_LIVE_LOADS, ASCE_LIVE_LOADS, EC_LIVE_LOADS
)
from proof_sources import attach_proof, proof_block

router = APIRouter(prefix="/intl", tags=["International Codes"])


def _intl_proof(code: str, topic: str = "general"):
    if code == "NBCC":
        keys = ["nbc_2020", "eccc_climate"] if topic in ("wind", "snow", "live") else ["nbc_2020", "nrcan_seismic"]
        return proof_block(
            "NBCC 2020",
            ["NBCC Division B Part 4", f"NBCC {topic} workflow"],
            keys,
            "Quick international calculator. Verify exact location, adopted edition, climate/seismic data, and local amendments.",
        )
    if code == "ASCE":
        keys = ["asce_7", "usgs_hazard"] if topic == "seismic" else ["asce_7"]
        return proof_block(
            "ASCE/SEI 7",
            ["ASCE 7 minimum design loads", f"ASCE 7 {topic} provisions"],
            keys,
            "Quick US calculator. Verify state/local adoption, risk category, official hazard data, and project-specific coefficients.",
        )
    if code == "EC":
        return proof_block(
            "Eurocodes",
            ["EN 1990 basis of design", "EN 1991 actions", "EN 1998 seismic design where applicable"],
            ["eurocodes_jrc", "cen"],
            "Quick Eurocode calculator. Verify National Annex values, local authority requirements, and the country-specific adopted edition.",
        )
    if code == "IS":
        return proof_block(
            "Indian Standards",
            ["IS 456", "IS 875", "IS 1893"],
            ["india_bis", "india_nbc"],
            "Quick India calculator. Verify BIS standard edition, local authority requirements, and project-specific inputs.",
        )
    if code == "ACI":
        return proof_block(
            "ACI 318",
            ["ACI 318 concrete strength design"],
            ["asce_7"],
            "Material factors only. Verify the adopted ACI edition and local building code.",
        )
    return proof_block("International code", ["User-selected code workflow"], ["eurocodes_jrc"])


# ── Reference data ────────────────────────────────────────────────────────────

@router.get("/codes")
def list_codes():
    return {
        "codes": [
            {"code": "IS",   "name": "Indian Standards (BIS)", "country": "India",
             "standards": ["IS 456:2000", "IS 875 Parts 1-3", "IS 1893:2016", "IS 10262:2019"]},
            {"code": "NBCC", "name": "National Building Code of Canada", "country": "Canada",
             "standards": ["NBCC 2020", "CSA A23.3-19", "CSA S16-19"]},
            {"code": "ASCE", "name": "ASCE 7-22 / ACI 318-19", "country": "USA",
             "standards": ["ASCE 7-22", "ACI 318-19", "AISC 360-22"]},
            {"code": "EC",   "name": "Eurocodes", "country": "Europe",
             "standards": ["EN 1990", "EN 1991-1-1", "EN 1991-1-3", "EN 1991-1-4",
                           "EN 1992-1-1", "EN 1998-1"]},
        ]
    }

@router.get("/live-loads/{code}")
def get_live_load_table(code: str):
    tables = {"NBCC": NBCC_LIVE_LOADS, "ASCE": ASCE_LIVE_LOADS, "EC": EC_LIVE_LOADS}
    if code not in tables:
        return {"error": "Supported codes: NBCC, ASCE, EC"}
    return {
        "code": code,
        "unit": "kPa (kN/m²)",
        "loads": [{"occupancy": k, "load_kPa": v} for k, v in tables[code].items()],
        "proof": _intl_proof(code, "live"),
    }

@router.get("/live-loads/{code}/{occupancy}")
def live_load(code: str, occupancy: str):
    return attach_proof(get_live_load(code, occupancy), _intl_proof(code, "live"))


# ── Wind loads ────────────────────────────────────────────────────────────────

class WindNBCCInput(BaseModel):
    q_ref: float             # Reference velocity pressure (Pa) — from NBCC Appendix C
    Ce: float = 0.9          # Exposure factor
    Ct: float = 1.0
    Cg: float = 2.0
    Cp: float = 0.8
    importance_factor: float = 1.0

class WindASCEInput(BaseModel):
    V_mph: float             # Basic wind speed (mph) — from ASCE 7-22 Fig. 26.5-1
    Kz: float = 0.85         # Velocity pressure coefficient
    Kzt: float = 1.0
    Ke: float = 1.0
    Kd: float = 0.85
    GCp: float = 0.8
    risk_category: int = 2

class WindECInput(BaseModel):
    vb0: float               # Fundamental basic wind velocity (m/s)
    c0: float = 1.0
    cdir: float = 1.0
    cseason: float = 1.0
    z: float = 10.0          # Height above ground (m)
    terrain_cat: str = "II"  # I, II, III, IV
    cp_net: float = 0.8

@router.post("/wind/nbcc")
def wind_nbcc(data: WindNBCCInput):
    return attach_proof(calc_wind_nbcc(**data.model_dump()), _intl_proof("NBCC", "wind"))

@router.post("/wind/asce")
def wind_asce(data: WindASCEInput):
    return attach_proof(calc_wind_asce(**data.model_dump()), _intl_proof("ASCE", "wind"))

@router.post("/wind/eurocode")
def wind_ec(data: WindECInput):
    return attach_proof(calc_wind_eurocode(**data.model_dump()), _intl_proof("EC", "wind"))


# ── Seismic ───────────────────────────────────────────────────────────────────

class SeismicNBCCInput(BaseModel):
    Sa_02: float             # Spectral acceleration at 0.2s (g) — NBCC hazard tool
    Sa_10: float             # Spectral acceleration at 1.0s (g)
    W: float                 # Seismic weight (kN)
    Rd: float = 2.0
    Ro: float = 1.3
    IE: float = 1.0
    Fa: float = 1.0
    Fv: float = 1.0
    hn: float = 10.0         # Building height (m)
    system: str = "moment_frame"

class SeismicASCEInput(BaseModel):
    SDS: float               # Design spectral accel short-period (g)
    SD1: float               # Design spectral accel 1s (g)
    W: float                 # Effective seismic weight (kN)
    R: float = 3.0
    Ie: float = 1.0
    Ct: float = 0.028
    x_exp: float = 0.8
    hn_ft: float = 33.0

class SeismicECInput(BaseModel):
    agR: float               # Reference PGA (g) — National Annex
    S: float = 1.0           # Soil factor
    W: float                 # Seismic weight (kN)
    q: float = 1.5           # Behaviour factor
    gamma_I: float = 1.0
    T1: float = 0.0
    hn: float = 10.0
    TB: float = 0.15
    TC: float = 0.50
    TD: float = 2.00
    structure: str = "frame"

@router.post("/seismic/nbcc")
def seismic_nbcc(data: SeismicNBCCInput):
    return attach_proof(calc_seismic_nbcc(**data.model_dump()), _intl_proof("NBCC", "seismic"))

@router.post("/seismic/asce")
def seismic_asce(data: SeismicASCEInput):
    return attach_proof(calc_seismic_asce(**data.model_dump()), _intl_proof("ASCE", "seismic"))

@router.post("/seismic/eurocode")
def seismic_ec(data: SeismicECInput):
    return attach_proof(calc_seismic_eurocode(**data.model_dump()), _intl_proof("EC", "seismic"))


# ── Snow loads ────────────────────────────────────────────────────────────────

class SnowNBCCInput(BaseModel):
    Ss: float                # Ground snow load (kPa) — NBCC Appendix C
    Sr: float = 0.0          # Rain load (kPa)
    Cb: float = 0.8
    Cw: float = 1.0
    Cs: float = 1.0
    Ca: float = 1.0
    Is: float = 1.0

class SnowASCEInput(BaseModel):
    pg: float                # Ground snow load (kPa) — ASCE 7-22 Fig. 7.2-1
    Ce: float = 1.0
    Ct: float = 1.0
    Is: float = 1.0
    roof_type: str = "flat"

class SnowECInput(BaseModel):
    sk: float                # Ground snow load (kN/m²) — National Annex
    mu1: float = 0.8
    Ce_ec: float = 1.0
    Ct_ec: float = 1.0

@router.post("/snow/nbcc")
def snow_nbcc(data: SnowNBCCInput):
    return attach_proof(calc_snow_nbcc(**data.model_dump()), _intl_proof("NBCC", "snow"))

@router.post("/snow/asce")
def snow_asce(data: SnowASCEInput):
    return attach_proof(calc_snow_asce(**data.model_dump()), _intl_proof("ASCE", "snow"))

@router.post("/snow/eurocode")
def snow_ec(data: SnowECInput):
    return attach_proof(calc_snow_eurocode(**data.model_dump()), _intl_proof("EC", "snow"))


# ── Load combinations ─────────────────────────────────────────────────────────

class LoadComboInput(BaseModel):
    D: float                 # Dead load
    L: float                 # Live load
    W: float = 0.0           # Wind load
    S: float = 0.0           # Snow load
    E: float = 0.0           # Seismic load
    code: str = "IS"

@router.post("/combinations")
def get_load_combinations(data: LoadComboInput):
    return attach_proof(load_combinations(**data.model_dump()), _intl_proof(data.code, "load combinations"))


# ── Material strengths ────────────────────────────────────────────────────────

class MaterialInput(BaseModel):
    fck_MPa: float = 25.0    # Concrete characteristic strength
    fy_MPa: float = 415.0    # Steel yield strength
    code: str = "IS"

@router.post("/materials")
def get_material_strengths(data: MaterialInput):
    return attach_proof(material_strengths(**data.model_dump()), _intl_proof(data.code, "materials"))


# ── Multi-code comparison ─────────────────────────────────────────────────────

@router.post("/compare/seismic")
def compare_seismic(W: float = 1000.0):
    """Quick comparison of seismic base shear across all codes for a given weight."""
    return {
        "note": "Approximate comparison for a typical 10m building, moderate seismic zone",
        "weight_kN": W,
        "results": {
            "IS 1893:2016": {
                "Ah_approx": 0.09,
                "base_shear_kN": round(0.09 * W, 1),
                "note": "Z=0.16 (Zone III), Sa/g=2.5, R=5, I=1.0"
            },
            "NBCC 2020": calc_seismic_nbcc(Sa_02=0.66, Sa_10=0.21, W=W,
                                             Rd=2.0, Ro=1.3, IE=1.0, hn=10.0),
            "ASCE 7-22":  calc_seismic_asce(SDS=0.75, SD1=0.30, W=W,
                                              R=3.0, Ie=1.0, hn_ft=33.0),
            "EN 1998-1":  calc_seismic_eurocode(agR=0.10, S=1.2, W=W,
                                                  q=1.5, gamma_I=1.0, hn=10.0),
        },
        "proof": proof_block(
            "Multi-code seismic comparison",
            ["IS 1893", "NBCC seismic provisions", "ASCE 7 seismic provisions", "EN 1998 seismic provisions"],
            ["india_bis", "nbc_2020", "nrcan_seismic", "asce_7", "usgs_hazard", "eurocodes_jrc", "cen"],
            "Comparison uses representative default parameters only. Do not use it for final design without project-specific hazard values and local code adoption checks.",
        ),
    }
