"""
International Structural Design Code Values
─────────────────────────────────────────────────────────────────────────────
Sources (all publicly available national standards):
  • Canada  : NBCC 2020 (National Building Code of Canada, NRC)
  • USA     : ASCE 7-22 (Minimum Design Loads), ACI 318-19 (Concrete)
  • Europe  : EN 1991-1-1:2002 (Actions), EN 1992-1-1:2004 (Concrete),
              EN 1998-1:2004 (Seismic)
  • India   : IS 456:2000, IS 875 Part 1/2/3, IS 1893:2016  (existing module)
─────────────────────────────────────────────────────────────────────────────
"""
from typing import Dict, Any
import math

# ══════════════════════════════════════════════════════════════════════════════
# LIVE LOAD TABLES
# ══════════════════════════════════════════════════════════════════════════════

# Canada NBCC 2020 — Table 4.1.5.3  (kPa = kN/m²)
NBCC_LIVE_LOADS: Dict[str, float] = {
    "residential_dwelling":     1.9,   # Cl. 4.1.5.3(1)
    "residential_corridor":     3.6,
    "office":                   2.4,   # Table 4.1.5.3 – Office floors
    "office_lobby":             4.8,
    "retail_ground":            4.8,
    "retail_upper":             3.6,
    "assembly_fixed_seats":     2.9,
    "assembly_movable":         4.8,
    "assembly_stage":           7.2,
    "storage_light":            6.0,
    "storage_heavy":            12.0,
    "parking_cars":             2.4,
    "parking_trucks":           12.0,
    "roof_accessible":          2.2,
    "roof_inaccessible":        1.0,
    "mechanical_room":          3.6,
    "classroom":                2.4,
    "library_reading":          2.9,
    "library_stacks":           7.2,
    "hospital_ward":            2.0,
    "hospital_operating":       2.9,
}

# USA ASCE 7-22 — Table 4.3-1  (kPa — converted from psf: 1 psf = 0.04788 kPa)
ASCE_LIVE_LOADS: Dict[str, float] = {
    "residential_private":      1.92,  # 40 psf
    "residential_public":       1.92,
    "office":                   2.40,  # 50 psf
    "office_lobby":             4.79,  # 100 psf
    "retail_ground":            4.79,
    "retail_upper":             3.59,  # 75 psf
    "assembly_fixed_seats":     2.87,  # 60 psf
    "assembly_movable":         4.79,  # 100 psf
    "assembly_stage":           7.18,  # 150 psf
    "storage_light":            6.00,  # 125 psf
    "storage_heavy":            11.97, # 250 psf
    "parking_cars":             2.40,  # 50 psf
    "parking_trucks_heavier":   9.58,  # 200 psf
    "roof_accessible":          1.92,  # 40 psf
    "roof_inaccessible":        0.96,  # 20 psf
    "mechanical_room":          3.59,
    "classroom":                1.92,  # 40 psf
    "library_reading":          2.87,  # 60 psf
    "library_stacks":           7.18,  # 150 psf
    "hospital_ward":            1.92,
    "hospital_operating":       2.87,
}

# Eurocode EN 1991-1-1:2002 — Table 6.1/6.2  (kN/m²)
EC_LIVE_LOADS: Dict[str, float] = {
    "Cat_A_residential":        2.0,   # Floors of residential buildings
    "Cat_A_stairs":             3.0,
    "Cat_B_office":             2.5,   # Office areas
    "Cat_C1_congregation":      3.0,   # Areas with tables (cafeteria)
    "Cat_C2_fixed_seats":       4.0,   # Areas with fixed seats (theatre)
    "Cat_C3_movable":           5.0,   # Areas without obstacles (museums)
    "Cat_C4_gymnasium":         5.0,
    "Cat_C5_assembly":          5.0,   # Stages
    "Cat_D1_retail_ground":     5.0,   # Retail/shop area
    "Cat_D2_retail_upper":      5.0,
    "Cat_E1_storage":           7.5,   # Storage areas
    "Cat_E2_industrial":        7.5,
    "Cat_F_parking_car":        2.5,   # Vehicles ≤ 30 kN
    "Cat_G_parking_medium":     5.0,   # 30–160 kN vehicles
    "Cat_H_roof_inaccessible":  0.75,  # Inaccessible roofs
    "Cat_I_roof_accessible":    2.0,
    "Cat_K_helicopter":         20.0,
}


def get_live_load(code: str, occupancy: str) -> Dict[str, Any]:
    """Return live load for given code and occupancy type."""
    tables = {
        "IS": None,       # handled by existing loads.py
        "NBCC": NBCC_LIVE_LOADS,
        "ASCE": ASCE_LIVE_LOADS,
        "EC":   EC_LIVE_LOADS,
    }
    if code not in tables or tables[code] is None:
        return {"error": "Use IS code endpoint for Indian standards"}
    table = tables[code]
    if occupancy not in table:
        # Return available keys
        return {"available_occupancies": list(table.keys()),
                "error": f"Occupancy '{occupancy}' not found"}
    value = table[occupancy]
    return {
        "code": code,
        "occupancy": occupancy,
        "live_load_kPa": value,
        "live_load_kN_m2": value,
        "note": {
            "NBCC": "NBCC 2020 Table 4.1.5.3 (NRC Canada)",
            "ASCE": "ASCE 7-22 Table 4.3-1",
            "EC":   "EN 1991-1-1:2002 Tables 6.1–6.10",
        }.get(code, "")
    }


# ══════════════════════════════════════════════════════════════════════════════
# WIND LOAD CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_wind_nbcc(
    q_ref: float,          # Reference velocity pressure (Pa) from NBCC Appendix C
    Ce: float,             # Exposure factor (height/terrain — Table 4.1.7.1)
    Ct: float = 1.0,       # Topographic factor
    Cg: float = 2.0,       # Gust factor (2.0 for cladding; 1.9 for MWFRS typically)
    Cp: float = 0.8,       # Net pressure coefficient (windward face = +0.8)
    importance_factor: float = 1.0,  # Iw: Normal=1.0, High=1.15, Post-disaster=1.25
) -> Dict[str, Any]:
    """
    NBCC 2020 Cl. 4.1.7.1
    p = Iw × q × Ce × Ct × Cg × Cp  (Pa)
    """
    p = importance_factor * q_ref * Ce * Ct * Cg * Cp
    return {
        "code": "NBCC 2020",
        "clause": "4.1.7.1",
        "inputs": {"q_ref_Pa": q_ref, "Ce": Ce, "Ct": Ct, "Cg": Cg, "Cp": Cp, "Iw": importance_factor},
        "wind_pressure_Pa": round(p, 1),
        "wind_pressure_kPa": round(p / 1000, 3),
        "formula": "p = Iw × q × Ce × Ct × Cg × Cp",
        "note": "q from NBCC 2020 Appendix C wind maps. Ce from Table 4.1.7.1."
    }


def calc_wind_asce(
    V_mph: float,          # Basic wind speed (mph) from ASCE 7-22 Fig. 26.5-1A/B/C
    Kz: float,             # Velocity pressure exposure coeff (Table 26.10-1)
    Kzt: float = 1.0,      # Topographic factor (Section 26.8)
    Ke: float = 1.0,       # Ground elevation factor (Section 26.9) — default 1.0
    Kd: float = 0.85,      # Wind directionality factor (Table 26.6-1)
    GCp: float = 0.8,      # External pressure coefficient (windward)
    risk_category: int = 2  # I=0.87, II=1.0, III=1.15, IV=1.15
) -> Dict[str, Any]:
    """
    ASCE 7-22 Chapter 26/27
    qz = 0.00256 × Kz × Kzt × Ke × Kd × V²  (psf)
    p = qz × GCp
    """
    # Importance / Risk Category — wind speed is risk-category-specific in ASCE 7-22
    V_ms = V_mph * 0.44704   # convert to m/s
    qz_psf = 0.00256 * Kz * Kzt * Ke * Kd * (V_mph ** 2)   # lb/ft²
    qz_Pa  = qz_psf * 47.88                                   # 1 psf = 47.88 Pa
    p_psf  = qz_psf * GCp
    p_Pa   = qz_Pa  * GCp
    return {
        "code": "ASCE 7-22",
        "clause": "Sections 26–27",
        "inputs": {"V_mph": V_mph, "V_ms": round(V_ms, 2), "Kz": Kz, "Kzt": Kzt,
                   "Ke": Ke, "Kd": Kd, "GCp": GCp, "risk_category": risk_category},
        "velocity_pressure_qz_psf": round(qz_psf, 2),
        "velocity_pressure_qz_Pa":  round(qz_Pa, 1),
        "design_pressure_psf": round(p_psf, 2),
        "design_pressure_Pa":  round(p_Pa, 1),
        "design_pressure_kPa": round(p_Pa / 1000, 3),
        "formula": "qz = 0.00256 × Kz × Kzt × Ke × Kd × V²  (psf)",
        "note": "V from ASCE 7-22 Fig. 26.5-1. Kz from Table 26.10-1. See Section 27 for MWFRS."
    }


def calc_wind_eurocode(
    vb0: float,            # Fundamental basic wind velocity (m/s) — National Annex
    c0: float = 1.0,       # Orography factor (EN 1991-1-4 Cl. 4.3.3)
    cdir: float = 1.0,     # Directional factor (National Annex, default 1.0)
    cseason: float = 1.0,  # Season factor (National Annex, default 1.0)
    z: float = 10.0,       # Height above ground (m)
    terrain_cat: str = "II",  # I=open sea, II=country, III=suburban, IV=urban
    cp_net: float = 0.8,   # Net pressure coefficient
) -> Dict[str, Any]:
    """
    EN 1991-1-4:2005 Wind Actions
    vb = cdir × cseason × vb0
    cr(z) = kr × ln(z/z0)  for z ≥ zmin
    vm(z) = cr(z) × c0(z) × vb
    qp(z) = [1 + 7 × Iv(z)] × 0.5 × ρ × vm²(z)  where ρ = 1.25 kg/m³
    we = qp(z) × cp_net
    """
    TERRAIN = {
        "0":   {"z0": 0.003, "zmin": 1.0,  "kr": 0.156},  # Sea
        "I":   {"z0": 0.01,  "zmin": 1.0,  "kr": 0.170},
        "II":  {"z0": 0.05,  "zmin": 2.0,  "kr": 0.190},  # Ref terrain
        "III": {"z0": 0.30,  "zmin": 5.0,  "kr": 0.215},
        "IV":  {"z0": 1.00,  "zmin": 10.0, "kr": 0.234},
    }
    tc = TERRAIN.get(terrain_cat, TERRAIN["II"])
    z0, zmin, kr = tc["z0"], tc["zmin"], tc["kr"]

    vb = cdir * cseason * vb0
    z_eff = max(z, zmin)

    cr = kr * math.log(z_eff / z0)                          # roughness factor
    vm = cr * c0 * vb                                        # mean wind velocity
    Iv = 1.0 / (c0 * math.log(z_eff / z0))                  # turbulence intensity
    rho = 1.25                                               # air density kg/m³
    qp = (1 + 7 * Iv) * 0.5 * rho * vm ** 2                 # peak velocity pressure (Pa)
    we = qp * cp_net

    return {
        "code": "EN 1991-1-4:2005",
        "clause": "Sections 4–5",
        "inputs": {"vb0_ms": vb0, "cdir": cdir, "cseason": cseason, "c0": c0,
                   "z_m": z, "terrain_cat": terrain_cat, "cp_net": cp_net},
        "vb_ms": round(vb, 2),
        "cr_z":  round(cr, 4),
        "vm_z_ms": round(vm, 2),
        "turbulence_Iv": round(Iv, 4),
        "peak_velocity_pressure_qp_Pa": round(qp, 1),
        "peak_velocity_pressure_qp_kPa": round(qp / 1000, 3),
        "wind_pressure_we_Pa":  round(we, 1),
        "wind_pressure_we_kPa": round(we / 1000, 3),
        "formula": "we = qp(z) × cp  |  qp = [1+7·Iv] × 0.5 × 1.25 × vm²",
        "note": "vb0 from National Annex wind maps. EN 1991-1-4:2005 Eq. 4.8."
    }


# ══════════════════════════════════════════════════════════════════════════════
# SEISMIC BASE SHEAR
# ══════════════════════════════════════════════════════════════════════════════

def calc_seismic_nbcc(
    Sa_02: float,    # Spectral acceleration at 0.2s from NBCC Seismic Hazard Tool
    Sa_10: float,    # Spectral acceleration at 1.0s
    W: float,        # Seismic weight (kN)
    Rd: float = 2.0, # Ductility-related force modification factor (Table 4.1.8.9)
    Ro: float = 1.3, # Over-strength-related modification factor (Table 4.1.8.9)
    IE: float = 1.0, # Importance factor (Normal=1.0, High=1.3, Post-disaster=1.5)
    T: float = 0.0,  # Fundamental period (s); 0 = use empirical
    Mv: float = 1.0, # Higher mode factor (Table 4.1.8.11)
    Fa: float = 1.0, # Site coefficient short period (Table 4.1.8.4A)
    Fv: float = 1.0, # Site coefficient 1.0s period (Table 4.1.8.4B)
    hn: float = 10.0,# Building height (m) for empirical period
    system: str = "moment_frame",
) -> Dict[str, Any]:
    """
    NBCC 2020 Cl. 4.1.8.11
    Vd = S(Ta) × Mv × IE × W / (Rd × Ro)
    S(T) = FaSa(0.2) or FvSa(T) interpolated
    Minimum Vd ≥ S(2.0)×Mv×IE×W / (Rd×Ro)
    """
    # Empirical period (Cl. 4.1.8.11(3))
    PERIOD_COEFF = {
        "moment_frame":    (0.085, 0.75),
        "braced_frame":    (0.025, 1.0),
        "shear_wall":      (0.05,  0.75),
        "other":           (0.1,   0.75),
    }
    ct, x = PERIOD_COEFF.get(system, (0.1, 0.75))
    Ta = ct * (hn ** x) if T == 0 else T

    # Design spectral acceleration — simplified linear interpolation
    # S(0.2) = Fa × Sa(0.2),  S(1.0) = Fv × Sa(1.0)
    S_02 = Fa * Sa_02
    S_10 = Fv * Sa_10

    if Ta <= 0.2:
        S_T = S_02
    elif Ta <= 1.0:
        S_T = S_02 + (S_10 - S_02) * (Ta - 0.2) / 0.8
    else:
        S_T = S_10 / Ta

    Vd = S_T * Mv * IE * W / (Rd * Ro)
    V_min = 0.2 * S_02 * IE * W / (Rd * Ro)  # 20% of elastic short-period
    Vd = max(Vd, V_min)

    return {
        "code": "NBCC 2020",
        "clause": "4.1.8.11",
        "inputs": {"Sa_02": Sa_02, "Sa_10": Sa_10, "W_kN": W, "Rd": Rd, "Ro": Ro,
                   "IE": IE, "Fa": Fa, "Fv": Fv, "hn_m": hn, "system": system},
        "period_Ta_s": round(Ta, 3),
        "S_02": round(S_02, 4),
        "S_10": round(S_10, 4),
        "S_T": round(S_T, 4),
        "base_shear_Vd_kN": round(Vd, 2),
        "Vd_pct_W": round(Vd / W * 100, 2),
        "formula": "Vd = S(Ta) × Mv × IE × W / (Rd × Ro)",
        "note": "Sa values from NBCC 2020 Appendix C seismic hazard tables (NRC/GSC Canada)"
    }


def calc_seismic_asce(
    SDS: float,      # Design spectral acceleration short-period (g) — ASCE 7 Cl. 11.4
    SD1: float,      # Design spectral acceleration 1s period (g)
    W: float,        # Effective seismic weight (kN)
    R: float = 3.0,  # Response modification factor (Table 12.2-1)
    Ie: float = 1.0, # Importance factor (Table 1.5-2): Occ. II=1.0, III=1.25, IV=1.5
    T: float = 0.0,  # Fundamental period (s); 0 = empirical
    Ct: float = 0.028, # Period coefficient (Table 12.8-2)
    x_exp: float = 0.8, # Period exponent
    hn_ft: float = 33.0, # Height in feet for empirical period
) -> Dict[str, Any]:
    """
    ASCE 7-22 Equivalent Lateral Force (ELF) — Section 12.8
    Cs = SDS / (R/Ie)  [Eq. 12.8-2]
    Cs_max = SD1 / (T × R/Ie)  [Eq. 12.8-3]
    Cs_min = max(0.044×SDS×Ie, 0.01)  [Eq. 12.8-5]
    V = Cs × W
    """
    Ta = Ct * (hn_ft ** x_exp) if T == 0 else T

    RIe = R / Ie
    Cs = SDS / RIe
    Cs_max = SD1 / (Ta * RIe) if Ta > 0 else Cs
    Cs_min = max(0.044 * SDS * Ie, 0.01)
    # For high seismic (S1 ≥ 0.6g):
    if SD1 >= 0.6:
        Cs_min = max(Cs_min, 0.5 * SD1 / RIe)

    Cs_design = min(Cs, Cs_max)
    Cs_design = max(Cs_design, Cs_min)
    V = Cs_design * W

    return {
        "code": "ASCE 7-22",
        "clause": "Section 12.8 (ELF)",
        "inputs": {"SDS_g": SDS, "SD1_g": SD1, "W_kN": W, "R": R, "Ie": Ie,
                   "Ct": Ct, "x": x_exp, "hn_ft": hn_ft},
        "period_Ta_s": round(Ta, 3),
        "Cs_basic": round(Cs, 4),
        "Cs_max":   round(Cs_max, 4),
        "Cs_min":   round(Cs_min, 4),
        "Cs_design":round(Cs_design, 4),
        "base_shear_V_kN": round(V, 2),
        "V_pct_W": round(V / W * 100, 2),
        "formula": "Cs = SDS/(R/Ie);  V = Cs × W",
        "note": "SDS, SD1 from ASCE 7-22 Ch.11 / USGS seismic hazard web tool"
    }


def calc_seismic_eurocode(
    agR: float,      # Reference peak ground acceleration (g) from National Annex
    S: float,        # Soil factor (EN 1998-1 Table 3.2: A=1.0, B=1.2, C=1.15, D=1.35, E=1.4)
    W: float,        # Seismic weight (kN)
    q: float = 1.5,  # Behaviour factor (Table 5.1: DCL=1.5, DCM=3.0–3.9, DCH=4.5–5.85)
    gamma_I: float = 1.0,  # Importance factor (Class I=0.8, II=1.0, III=1.2, IV=1.4)
    T1: float = 0.0,      # Fundamental period (s); 0 = empirical
    lambda_coeff: float = 0.85,  # Correction factor λ (0.85 if T1 ≤ 2TC, else 1.0)
    TB: float = 0.15,  # Lower limit of constant spectral acceleration (s)
    TC: float = 0.50,  # Upper limit of constant spectral acceleration (s)
    TD: float = 2.00,  # Start of constant displacement range (s)
    beta: float = 0.2, # Lower bound factor (EN 1998-1 Cl. 3.2.2.5)
    hn: float = 10.0,  # Building height (m) for empirical period
    structure: str = "frame",
) -> Dict[str, Any]:
    """
    EN 1998-1:2004 Equivalent Static Force Method — Section 4.3.3.2
    ag = γI × agR
    Fb = Sd(T1) × m × λ   where Sd(T1) = ag × S × η × 2.5/q × (TC/T1)
    """
    # Empirical period Cl. 4.3.3.2.2 — Eq. (4.6)
    PERIOD_COEFF = {"frame": (0.075, 0.75), "wall": (0.05, 0.75), "other": (0.085, 0.75)}
    ct, x = PERIOD_COEFF.get(structure, (0.075, 0.75))
    if T1 == 0:
        T1 = ct * (hn ** x)

    ag = gamma_I * agR * 9.81   # m/s²

    # Elastic spectrum Eq. (3.13–3.16) damping correction η=1.0 (5% default)
    eta = 1.0  # for 5% damping
    if T1 < TB:
        Se_g = agR * S * (1 + T1 / TB * (eta * 2.5 - 1))
    elif T1 <= TC:
        Se_g = agR * S * eta * 2.5
    elif T1 <= TD:
        Se_g = agR * S * eta * 2.5 * (TC / T1)
    else:
        Se_g = agR * S * eta * 2.5 * (TC * TD / T1 ** 2)

    Sd_g = max(Se_g / q, beta * agR)   # design spectrum

    m = W / 9.81    # mass in tonnes
    Fb = Sd_g * 9.81 * m * lambda_coeff   # kN

    return {
        "code": "EN 1998-1:2004",
        "clause": "Section 4.3.3.2",
        "inputs": {"agR_g": agR, "S": S, "W_kN": W, "q": q, "gamma_I": gamma_I,
                   "T1_s": round(T1, 3), "TB": TB, "TC": TC, "TD": TD, "hn_m": hn},
        "ag_ms2": round(ag, 3),
        "period_T1_s": round(T1, 3),
        "Se_g": round(Se_g, 4),
        "Sd_g": round(Sd_g, 4),
        "base_shear_Fb_kN": round(Fb, 2),
        "Fb_pct_W": round(Fb / W * 100, 2),
        "formula": "Fb = Sd(T1) × m × λ",
        "note": "agR from EN 1998-1 National Annex seismic zone maps. q from EN 1998-1 Table 5.1."
    }


# ══════════════════════════════════════════════════════════════════════════════
# SNOW LOADS
# ══════════════════════════════════════════════════════════════════════════════

def calc_snow_nbcc(
    Ss: float,        # Ground snow load (kPa) from NBCC Appendix C climate data
    Sr: float,        # Associated rain load (kPa)
    Cb: float = 0.8,  # Basic roof snow load factor (Cl. 4.1.6.2)
    Cw: float = 1.0,  # Wind exposure factor (1.0=sheltered, 0.75=exposed, 0.5=fully exposed)
    Cs: float = 1.0,  # Slope factor (1.0 for flat roof)
    Ca: float = 1.0,  # Accumulation factor (1.0 for uniform)
    Is: float = 1.0,  # Importance factor (Normal=1.0, High=1.15, Post-disaster=1.25)
) -> Dict[str, Any]:
    """NBCC 2020 Cl. 4.1.6.2 — S = Is × [Ss × (Cb × Cw × Cs × Ca) + Sr]"""
    S = Is * (Ss * (Cb * Cw * Cs * Ca) + Sr)
    return {
        "code": "NBCC 2020", "clause": "4.1.6.2",
        "inputs": {"Ss_kPa": Ss, "Sr_kPa": Sr, "Cb": Cb, "Cw": Cw, "Cs": Cs, "Ca": Ca, "Is": Is},
        "roof_snow_load_kPa": round(S, 3),
        "formula": "S = Is × [Ss × (Cb × Cw × Cs × Ca) + Sr]",
        "note": "Ss & Sr from NBCC 2020 Appendix C climate tables."
    }


def calc_snow_asce(
    pg: float,        # Ground snow load (kPa) from ASCE 7-22 Fig. 7.2-1
    Ce: float = 1.0,  # Exposure factor (Table 7.3-1: sheltered=1.3, terrain B exposed=0.9)
    Ct: float = 1.0,  # Thermal factor (Table 7.3-2: heated=1.0, cold=1.1, unheated=1.2)
    Is: float = 1.0,  # Importance factor (Table 1.5-2)
    roof_type: str = "flat",
) -> Dict[str, Any]:
    """ASCE 7-22 Section 7 — pf = 0.7 × Ce × Ct × Is × pg"""
    pf = 0.7 * Ce * Ct * Is * pg
    # Minimum: 0.96 kPa if pg > 0.96, else pg
    pf_min = pg if pg < 0.96 else 0.96
    pf = max(pf, pf_min)
    return {
        "code": "ASCE 7-22", "clause": "Section 7.3",
        "inputs": {"pg_kPa": pg, "Ce": Ce, "Ct": Ct, "Is": Is, "roof_type": roof_type},
        "flat_roof_snow_pf_kPa": round(pf, 3),
        "formula": "pf = 0.7 × Ce × Ct × Is × pg",
        "note": "pg from ASCE 7-22 Fig. 7.2-1 ground snow load map."
    }


def calc_snow_eurocode(
    sk: float,        # Characteristic ground snow load (kN/m²) — EN 1991-1-3 Cl. 5.2
    mu1: float = 0.8, # Shape coefficient (Table 5.2: flat roof ≤30° = 0.8)
    Ce_ec: float = 1.0,  # Exposure coefficient (default 1.0; C.2)
    Ct_ec: float = 1.0,  # Thermal coefficient (default 1.0; Section 6)
) -> Dict[str, Any]:
    """EN 1991-1-3:2003 — s = μi × Ce × Ct × sk"""
    s = mu1 * Ce_ec * Ct_ec * sk
    return {
        "code": "EN 1991-1-3:2003", "clause": "Section 5.2",
        "inputs": {"sk_kNm2": sk, "mu1": mu1, "Ce": Ce_ec, "Ct": Ct_ec},
        "roof_snow_load_kNm2": round(s, 3),
        "formula": "s = μ1 × Ce × Ct × sk",
        "note": "sk from EN 1991-1-3 Annex C national maps or National Annex."
    }


# ══════════════════════════════════════════════════════════════════════════════
# LOAD COMBINATIONS
# ══════════════════════════════════════════════════════════════════════════════

def load_combinations(
    D: float, L: float, W: float = 0, S: float = 0, E: float = 0,
    code: str = "IS"
) -> Dict[str, Any]:
    """
    Factored load combinations for each code.
    D=Dead, L=Live, W=Wind, S=Snow, E=Seismic (all in same units, e.g. kN/m²)
    """
    combos = {}

    if code == "IS":
        # IS 456:2000 / IS 875 Part 5
        combos = {
            "1.5(D+L)":             round(1.5*(D+L), 3),
            "1.2(D+L+W)":           round(1.2*(D+L+W), 3),
            "1.5(D+W)":             round(1.5*(D+W), 3),
            "0.9D + 1.5W":          round(0.9*D + 1.5*W, 3),
            "1.2(D+L+E)":           round(1.2*(D+L+E), 3),
            "1.5(D+E)":             round(1.5*(D+E), 3),
            "0.9D + 1.5E":          round(0.9*D + 1.5*E, 3),
        }
        ref = "IS 456:2000 / IS 875 Part 5"

    elif code == "NBCC":
        # NBCC 2020 Table 4.1.3.2
        combos = {
            "1.4D":                 round(1.4*D, 3),
            "1.25D + 1.5L":         round(1.25*D + 1.5*L, 3),
            "1.25D + 1.5S":         round(1.25*D + 1.5*S, 3),
            "1.25D + 1.5W":         round(1.25*D + 1.5*W, 3),
            "1.25D+1.5L+0.5S":      round(1.25*D + 1.5*L + 0.5*S, 3),
            "1.25D+1.5L+0.4W":      round(1.25*D + 1.5*L + 0.4*W, 3),
            "1.25D+0.5L+1.5S":      round(1.25*D + 0.5*L + 1.5*S, 3),
            "1.0D + 1.0E + 0.5L":   round(1.0*D + E + 0.5*L, 3),
            "0.9D + 1.5W":          round(0.9*D + 1.5*W, 3),
        }
        ref = "NBCC 2020 Table 4.1.3.2"

    elif code == "ASCE":
        # ASCE 7-22 Section 2.3 (LRFD)
        combos = {
            "1.4D":                 round(1.4*D, 3),
            "1.2D + 1.6L":          round(1.2*D + 1.6*L, 3),
            "1.2D+1.6S+L":          round(1.2*D + 1.6*S + L, 3),
            "1.2D+1.6W+L+0.5S":     round(1.2*D + 1.6*W + L + 0.5*S, 3),
            "0.9D + 1.6W":          round(0.9*D + 1.6*W, 3),
            "1.2D+E+L+0.2S":        round(1.2*D + E + L + 0.2*S, 3),
            "0.9D + E":             round(0.9*D + E, 3),
        }
        ref = "ASCE 7-22 Section 2.3 (LRFD)"

    elif code == "EC":
        # EN 1990:2002 — Eq. 6.10a/6.10b (ULS, STR)
        psi0_L = 0.7   # combination factor for live load (Category B office)
        psi0_W = 0.6   # combination factor for wind
        psi0_S = 0.5   # combination factor for snow
        combos = {
            "1.35D + 1.5L":             round(1.35*D + 1.5*L, 3),
            "1.35D+1.5W+1.5ψ0L":       round(1.35*D + 1.5*W + 1.5*psi0_L*L, 3),
            "1.35D+1.5L+1.5ψ0W":       round(1.35*D + 1.5*L + 1.5*psi0_W*W, 3),
            "1.35D+1.5S+1.5ψ0L":       round(1.35*D + 1.5*S + 1.5*psi0_L*L, 3),
            "1.0D + 1.0E + ψ2L":       round(1.0*D + E + 0.3*L, 3),   # ψ2=0.3 Cat B
            "0.9D + 1.5W (uplift)":    round(0.9*D + 1.5*W, 3),
        }
        ref = "EN 1990:2002 Table A1.2(B) Eq. 6.10"

    governing = max(combos, key=lambda k: abs(combos[k]))
    return {
        "code": code, "reference": ref,
        "inputs": {"D": D, "L": L, "W": W, "S": S, "E": E},
        "combinations": combos,
        "governing_combo": governing,
        "governing_value": combos[governing],
    }


# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL DESIGN STRENGTHS
# ══════════════════════════════════════════════════════════════════════════════

def material_strengths(fck_MPa: float, fy_MPa: float, code: str = "IS") -> Dict[str, Any]:
    """Design material strengths per code."""
    if code == "IS":
        fcd = 0.67 * fck_MPa / 1.5    # IS 456 Cl. 38.1
        fyd = fy_MPa / 1.15
        return {"code":"IS 456:2000","fck":fck_MPa,"fy":fy_MPa,
                "fcd_MPa":round(fcd,2),"fyd_MPa":round(fyd,2),
                "gamma_c":1.5,"gamma_s":1.15}
    elif code == "EC":
        fcd = fck_MPa / 1.5            # EN 1992-1-1 Cl. 2.4.2.4
        fyd = fy_MPa / 1.15
        return {"code":"EN 1992-1-1:2004","fck":fck_MPa,"fyk":fy_MPa,
                "fcd_MPa":round(fcd,2),"fyd_MPa":round(fyd,2),
                "gamma_c":1.5,"gamma_s":1.15,
                "note":"αcc=1.0 assumed; National Annex may specify 0.85"}
    elif code == "ACI":
        fc_prime = fck_MPa              # f'c in MPa
        fy = fy_MPa
        phi_b = 0.90                    # ACI 318-19 Table 21.2.1 (flexure)
        phi_v = 0.75                    # shear
        return {"code":"ACI 318-19","fc_prime_MPa":fc_prime,"fy_MPa":fy,
                "phi_flexure":phi_b,"phi_shear":phi_v,
                "note":"Strength reduction factors from ACI 318-19 Table 21.2.1"}
    elif code == "NBCC":
        # CSA A23.3-19
        phi_c = 0.65                    # concrete
        phi_s = 0.85                    # steel
        fcd = phi_c * fck_MPa
        fyd = phi_s * fy_MPa
        return {"code":"CSA A23.3-19","fc_prime_MPa":fck_MPa,"fy_MPa":fy_MPa,
                "phi_c":phi_c,"phi_s":phi_s,
                "fcd_MPa":round(fcd,2),"fyd_MPa":round(fyd,2),
                "note":"CSA A23.3-19 Cl. 8.4"}
    return {"error": "Unknown code"}
