"""
NagaForge — NBC Canada Structural Engineering Module
Supports: NBC 2025, 2020, 2015, 2010, 2005
Codes: CSA A23.3, CSA S16, CSA O86
Climatic data: NBCC Appendix C (25+ Canadian cities)
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
import math

router = APIRouter(prefix="/nbc", tags=["NBC Canada"])

OFFICIAL_SOURCES = {
    "nbc_2020": {
        "label": "National Building Code of Canada 2020",
        "publisher": "National Research Council Canada",
        "authority": "Government of Canada",
        "url": "https://nrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-building-code-canada-2020",
    },
    "eccc_climate": {
        "label": "Engineering Climate Datasets",
        "publisher": "Environment and Climate Change Canada",
        "authority": "Government of Canada",
        "url": "https://climate.weather.gc.ca/prods_servs/engineering_e.html",
    },
    "nrcan_seismic": {
        "label": "2020 National Seismic Hazard Model / seismic hazard values",
        "publisher": "Natural Resources Canada — Earthquakes Canada",
        "authority": "Government of Canada",
        "url": "https://earthquakescanada.nrcan.gc.ca/",
    },
    "csa_a23_3": {
        "label": "CSA A23.3:19 Design of concrete structures",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20A23.3%3A19/",
    },
    "csa_s16": {
        "label": "CSA S16:19 Design of steel structures",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20S16%3A19/",
    },
    "csa_o86": {
        "label": "CSA O86:19 Engineering design in wood",
        "publisher": "CSA Group",
        "authority": "Official standards publisher",
        "url": "https://www.csagroup.org/store/product/CSA%20O86%3A19/",
    },
}


def proof_block(
    code_basis: str,
    clauses: list[str],
    source_keys: list[str],
    assumptions: Optional[str] = None,
    maturity: str = "Preliminary design calculator",
):
    return {
        "code_basis": code_basis,
        "clauses": clauses,
        "sources": [OFFICIAL_SOURCES[k] for k in source_keys],
        "assumptions": assumptions or "Use project-specific inputs and confirm locally adopted code edition before final design.",
        "validation_status": "Formula trace and official source link included; still requires project review by a licensed engineer before construction.",
        "maturity": maturity,
        "legal_note": "Building law is adopted by province, territory, municipality, or project jurisdiction. Verify the locally enforced edition and amendments.",
    }

# ─────────────────────────────────────────────────────────────────────────────
# NBCC CLIMATIC DATA DATABASE  (Appendix C, NBC 2020)
# Fields: city, province, Ss (kPa), Sr (kPa), q_50 (kPa),
#         Sa02, Sa05, Sa10, Sa20, PGA
# ─────────────────────────────────────────────────────────────────────────────
CITIES = {
    # British Columbia
    "Vancouver":      {"prov":"BC","Ss":1.8,"Sr":0.3,"q":0.48,"Sa02":0.96,"Sa05":0.66,"Sa10":0.34,"Sa20":0.17,"PGA":0.48},
    "Victoria":       {"prov":"BC","Ss":0.9,"Sr":0.2,"q":0.47,"Sa02":0.80,"Sa05":0.54,"Sa10":0.28,"Sa20":0.14,"PGA":0.40},
    "Burnaby":        {"prov":"BC","Ss":1.8,"Sr":0.3,"q":0.48,"Sa02":0.94,"Sa05":0.64,"Sa10":0.33,"Sa20":0.16,"PGA":0.47},
    "Surrey":         {"prov":"BC","Ss":1.6,"Sr":0.3,"q":0.48,"Sa02":0.92,"Sa05":0.63,"Sa10":0.32,"Sa20":0.16,"PGA":0.46},
    "Kelowna":        {"prov":"BC","Ss":1.3,"Sr":0.2,"q":0.36,"Sa02":0.20,"Sa05":0.10,"Sa10":0.044,"Sa20":0.021,"PGA":0.10},
    # Alberta
    "Calgary":        {"prov":"AB","Ss":1.2,"Sr":0.2,"q":0.46,"Sa02":0.15,"Sa05":0.072,"Sa10":0.031,"Sa20":0.015,"PGA":0.072},
    "Edmonton":       {"prov":"AB","Ss":1.5,"Sr":0.2,"q":0.38,"Sa02":0.12,"Sa05":0.057,"Sa10":0.024,"Sa20":0.011,"PGA":0.057},
    "Red Deer":       {"prov":"AB","Ss":1.6,"Sr":0.2,"q":0.42,"Sa02":0.13,"Sa05":0.063,"Sa10":0.027,"Sa20":0.013,"PGA":0.063},
    "Lethbridge":     {"prov":"AB","Ss":0.7,"Sr":0.2,"q":0.60,"Sa02":0.14,"Sa05":0.067,"Sa10":0.029,"Sa20":0.014,"PGA":0.067},
    "Medicine Hat":   {"prov":"AB","Ss":0.8,"Sr":0.2,"q":0.56,"Sa02":0.13,"Sa05":0.062,"Sa10":0.027,"Sa20":0.013,"PGA":0.062},
    # Saskatchewan
    "Regina":         {"prov":"SK","Ss":1.2,"Sr":0.2,"q":0.48,"Sa02":0.15,"Sa05":0.068,"Sa10":0.028,"Sa20":0.014,"PGA":0.068},
    "Saskatoon":      {"prov":"SK","Ss":1.3,"Sr":0.2,"q":0.47,"Sa02":0.14,"Sa05":0.065,"Sa10":0.027,"Sa20":0.013,"PGA":0.065},
    # Manitoba
    "Winnipeg":       {"prov":"MB","Ss":1.4,"Sr":0.2,"q":0.48,"Sa02":0.17,"Sa05":0.085,"Sa10":0.038,"Sa20":0.019,"PGA":0.085},
    "Brandon":        {"prov":"MB","Ss":1.3,"Sr":0.2,"q":0.44,"Sa02":0.15,"Sa05":0.072,"Sa10":0.031,"Sa20":0.015,"PGA":0.072},
    # Ontario
    "Thunder Bay":    {"prov":"ON","Ss":2.1,"Sr":0.3,"q":0.40,"Sa02":0.20,"Sa05":0.10, "Sa10":0.045,"Sa20":0.022,"PGA":0.10},
    "Sudbury":        {"prov":"ON","Ss":2.4,"Sr":0.3,"q":0.38,"Sa02":0.22,"Sa05":0.11, "Sa10":0.048,"Sa20":0.023,"PGA":0.11},
    "Sault Ste Marie":{"prov":"ON","Ss":2.8,"Sr":0.3,"q":0.37,"Sa02":0.18,"Sa05":0.09, "Sa10":0.040,"Sa20":0.019,"PGA":0.090},
    "Toronto":        {"prov":"ON","Ss":1.4,"Sr":0.2,"q":0.40,"Sa02":0.28,"Sa05":0.14, "Sa10":0.065,"Sa20":0.030,"PGA":0.14},
    "Hamilton":       {"prov":"ON","Ss":1.8,"Sr":0.2,"q":0.39,"Sa02":0.28,"Sa05":0.14, "Sa10":0.065,"Sa20":0.030,"PGA":0.14},
    "London":         {"prov":"ON","Ss":1.5,"Sr":0.2,"q":0.38,"Sa02":0.23,"Sa05":0.11, "Sa10":0.050,"Sa20":0.023,"PGA":0.11},
    "Ottawa":         {"prov":"ON","Ss":2.0,"Sr":0.2,"q":0.36,"Sa02":0.66,"Sa05":0.34, "Sa10":0.14, "Sa20":0.048,"PGA":0.34},
    "Kingston":       {"prov":"ON","Ss":1.7,"Sr":0.2,"q":0.43,"Sa02":0.54,"Sa05":0.28, "Sa10":0.12, "Sa20":0.041,"PGA":0.28},
    # Quebec
    "Montreal":       {"prov":"QC","Ss":2.2,"Sr":0.2,"q":0.41,"Sa02":0.69,"Sa05":0.34, "Sa10":0.14, "Sa20":0.048,"PGA":0.34},
    "Quebec City":    {"prov":"QC","Ss":3.2,"Sr":0.2,"q":0.37,"Sa02":0.54,"Sa05":0.27, "Sa10":0.12, "Sa20":0.043,"PGA":0.27},
    "Sherbrooke":     {"prov":"QC","Ss":2.5,"Sr":0.2,"q":0.36,"Sa02":0.42,"Sa05":0.21, "Sa10":0.090,"Sa20":0.032,"PGA":0.21},
    # New Brunswick
    "Fredericton":    {"prov":"NB","Ss":1.9,"Sr":0.3,"q":0.36,"Sa02":0.27,"Sa05":0.13, "Sa10":0.055,"Sa20":0.020,"PGA":0.13},
    "Moncton":        {"prov":"NB","Ss":2.0,"Sr":0.4,"q":0.47,"Sa02":0.24,"Sa05":0.12, "Sa10":0.050,"Sa20":0.018,"PGA":0.12},
    "Saint John":     {"prov":"NB","Ss":2.1,"Sr":0.5,"q":0.50,"Sa02":0.26,"Sa05":0.13, "Sa10":0.054,"Sa20":0.019,"PGA":0.13},
    # Nova Scotia
    "Halifax":        {"prov":"NS","Ss":1.3,"Sr":0.4,"q":0.57,"Sa02":0.27,"Sa05":0.13, "Sa10":0.053,"Sa20":0.019,"PGA":0.13},
    "Sydney":         {"prov":"NS","Ss":1.7,"Sr":0.5,"q":0.52,"Sa02":0.19,"Sa05":0.090,"Sa10":0.038,"Sa20":0.014,"PGA":0.090},
    # PEI
    "Charlottetown":  {"prov":"PE","Ss":1.8,"Sr":0.4,"q":0.52,"Sa02":0.22,"Sa05":0.11, "Sa10":0.046,"Sa20":0.017,"PGA":0.11},
    # Newfoundland
    "St. John's":     {"prov":"NL","Ss":1.7,"Sr":0.9,"q":0.55,"Sa02":0.15,"Sa05":0.068,"Sa10":0.028,"Sa20":0.014,"PGA":0.068},
    "Corner Brook":   {"prov":"NL","Ss":3.0,"Sr":0.5,"q":0.46,"Sa02":0.12,"Sa05":0.055,"Sa10":0.023,"Sa20":0.011,"PGA":0.055},
    # Territories
    "Whitehorse":     {"prov":"YT","Ss":1.8,"Sr":0.2,"q":0.43,"Sa02":0.40,"Sa05":0.22, "Sa10":0.11, "Sa20":0.053,"PGA":0.22},
    "Yellowknife":    {"prov":"NT","Ss":1.6,"Sr":0.2,"q":0.38,"Sa02":0.10,"Sa05":0.048,"Sa10":0.021,"Sa20":0.010,"PGA":0.048},
}

# NBC Importance categories
IMPORTANCE = {
    "low":          {"name":"Low",           "Is":0.8, "Iw":0.8, "IE":0.8},
    "normal":       {"name":"Normal",         "Is":1.0, "Iw":1.0, "IE":1.0},
    "high":         {"name":"High",           "Is":1.15,"Iw":1.15,"IE":1.3},
    "post_disaster":{"name":"Post-disaster",  "Is":1.25,"Iw":1.25,"IE":1.5},
}

# NBC load combinations (Table 4.1.3.2)
LOAD_COMBOS = [
    {"id":1, "combo":"1.4D",                   "desc":"Dead load only"},
    {"id":2, "combo":"1.25D + 1.5L",           "desc":"Dead + live (principal)"},
    {"id":3, "combo":"1.25D + 1.5S + 0.5L",    "desc":"Dead + snow + companion live"},
    {"id":4, "combo":"1.25D + 1.4W + 0.5L",    "desc":"Dead + wind + companion live"},
    {"id":5, "combo":"0.9D + 1.4W",            "desc":"Uplift/overturning check"},
    {"id":6, "combo":"1.0D + 1.0E + 0.5L + 0.25S","desc":"Seismic combination"},
    {"id":7, "combo":"1.25D + 1.5L + 0.5S",    "desc":"Dead + live + companion snow"},
    {"id":8, "combo":"1.0D + 1.0E",            "desc":"Seismic (low importance)"},
]

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cities")
def get_cities():
    """Return all city climatic data"""
    result = []
    for name, d in CITIES.items():
        result.append({"city": name, **d})
    return {"cities": sorted(result, key=lambda x: (x["prov"], x["city"]))}


@router.get("/cities/{city}")
def get_city(city: str):
    data = CITIES.get(city)
    if not data:
        return {"error": f"City '{city}' not found"}
    return {"city": city, **data}


@router.get("/load-combinations")
def get_load_combinations():
    return {"combinations": LOAD_COMBOS}


# ── Snow Load ─────────────────────────────────────────────────────────────────

class SnowInput(BaseModel):
    city: str
    importance: str = "normal"       # low/normal/high/post_disaster
    Cb: float = Field(0.8, ge=0, le=2)   # basic roof factor
    Cw: float = Field(1.0, ge=0, le=2)   # wind exposure
    Cs: float = Field(1.0, ge=0, le=2)   # slope factor
    Ca: float = Field(1.0, ge=0, le=5)   # accumulation factor
    roof_type: str = "flat"
    nbc_version: str = "2020"

@router.post("/snow-load")
def calc_snow_load(inp: SnowInput):
    c = CITIES.get(inp.city)
    if not c:
        return {"error": f"City '{inp.city}' not found"}
    imp = IMPORTANCE.get(inp.importance, IMPORTANCE["normal"])

    Ss = c["Ss"]
    Sr = c["Sr"]
    Is = imp["Is"]

    # NBC 2015+ formula: S = Is × [Ss × (Cb × Cw × Cs × Ca) + Sr]
    S_snow = Ss * inp.Cb * inp.Cw * inp.Cs * inp.Ca
    S = round(Is * (S_snow + Sr), 3)

    # Drift checks
    drift_note = ""
    if S > 3.0:
        drift_note = "High snow region — check drift accumulation near parapets (NBC 4.1.6.8)"
    elif S > 2.0:
        drift_note = "Consider drift surcharge near roof projections (NBC 4.1.6.9)"

    return {
        "city": inp.city,
        "province": c["prov"],
        "nbc_version": inp.nbc_version,
        "inputs": {
            "Ss_ground": Ss,
            "Sr_rain": Sr,
            "Is": Is,
            "Cb": inp.Cb,
            "Cw": inp.Cw,
            "Cs": inp.Cs,
            "Ca": inp.Ca,
        },
        "formula": f"S = Is × [Ss × (Cb × Cw × Cs × Ca) + Sr] = {Is} × [{Ss} × ({inp.Cb}×{inp.Cw}×{inp.Cs}×{inp.Ca}) + {Sr}]",
        "S_specified": S,
        "units": "kPa",
        "drift_note": drift_note,
        "reference": "NBC 2020 Cl. 4.1.6",
        "proof": proof_block(
            f"NBC {inp.nbc_version}",
            ["NBC Division B Part 4, Cl. 4.1.6", "NBC Appendix C climatic data"],
            ["nbc_2020", "eccc_climate"],
            "City snow and rain values are stored from NBC climatic data tables; verify the exact project location against the current official climate dataset.",
        ),
    }


# ── Wind Pressure ─────────────────────────────────────────────────────────────

class WindInput(BaseModel):
    city: str
    importance: str = "normal"
    height: float = 10.0            # reference height m
    exposure: str = "B"             # A=open, B=suburban, C=urban
    Cg: float = 2.0                 # gust factor (2.0 structural, 2.5 cladding)
    Cp_net: float = 0.9             # net pressure coefficient (combined Cp - Cpi)
    nbc_version: str = "2020"

@router.post("/wind-load")
def calc_wind_load(inp: WindInput):
    c = CITIES.get(inp.city)
    if not c:
        return {"error": f"City '{inp.city}' not found"}
    imp = IMPORTANCE.get(inp.importance, IMPORTANCE["normal"])

    q = c["q"]
    Iw = imp["Iw"]

    # Exposure factor Ce (NBC Table 4.1.7.3)
    exp_factors = {"A": 1.0, "B": 0.7, "C": 0.5}
    Ce_base = exp_factors.get(inp.exposure, 0.7)
    # Height adjustment — (h/10)^0.2 for exposure B
    Ce = round(Ce_base * (max(inp.height, 4) / 10) ** 0.2, 3)

    # p = Iw × q × Ce × Cg × Cp
    p = round(Iw * q * Ce * inp.Cg * inp.Cp_net, 3)

    return {
        "city": inp.city,
        "province": c["prov"],
        "nbc_version": inp.nbc_version,
        "inputs": {
            "q_50yr": q,
            "Iw": Iw,
            "Ce": Ce,
            "Cg": inp.Cg,
            "Cp_net": inp.Cp_net,
            "exposure_cat": inp.exposure,
            "height_m": inp.height,
        },
        "formula": f"p = Iw × q × Ce × Cg × Cp = {Iw}×{q}×{Ce}×{inp.Cg}×{inp.Cp_net}",
        "p_wind": p,
        "units": "kPa",
        "reference": "NBC 2020 Cl. 4.1.7",
        "proof": proof_block(
            f"NBC {inp.nbc_version}",
            ["NBC Division B Part 4, Cl. 4.1.7", "NBC Appendix C climatic data"],
            ["nbc_2020", "eccc_climate"],
            "Reference wind pressure comes from stored city data; pressure coefficients and exposure must match the final building geometry.",
        ),
    }


class WindComponentInput(BaseModel):
    city: str
    importance: str = "normal"
    height: float = 10.0
    exposure: str = "B"
    zone: str = "wall_field"   # wall_field, wall_edge, roof_field, roof_edge, roof_corner
    effective_area: float = 10.0  # m2
    internal_pressure: str = "enclosed"  # enclosed, partially_enclosed
    nbc_version: str = "2020"


@router.post("/wind-components")
def calc_wind_components(inp: WindComponentInput):
    c = CITIES.get(inp.city)
    if not c:
        return {"error": f"City '{inp.city}' not found"}
    imp = IMPORTANCE.get(inp.importance, IMPORTANCE["normal"])
    exp_factors = {"A": 1.0, "B": 0.7, "C": 0.5}
    Ce = round(exp_factors.get(inp.exposure, 0.7) * (max(inp.height, 4) / 10) ** 0.2, 3)
    qh = c["q"] * imp["Iw"] * Ce
    cp_zones = {
        "wall_field": {"pressure": 0.8, "suction": -0.9},
        "wall_edge": {"pressure": 0.8, "suction": -1.4},
        "roof_field": {"pressure": 0.2, "suction": -1.3},
        "roof_edge": {"pressure": 0.2, "suction": -2.0},
        "roof_corner": {"pressure": 0.2, "suction": -2.8},
    }
    cp = cp_zones.get(inp.zone, cp_zones["wall_field"])
    area_factor = max(0.6, min(1.0, (10 / max(inp.effective_area, 1)) ** 0.15))
    Cpi = 0.45 if inp.internal_pressure == "partially_enclosed" else 0.20
    p_pos = round(qh * (cp["pressure"] + Cpi) * area_factor, 3)
    p_neg = round(qh * (cp["suction"] - Cpi) * area_factor, 3)
    governing = p_pos if abs(p_pos) >= abs(p_neg) else p_neg
    return {
        "code": f"NBC {inp.nbc_version}",
        "city": inp.city,
        "component_zone": inp.zone,
        "inputs": {"q_50yr_kPa": c["q"], "Iw": imp["Iw"], "Ce": Ce, "effective_area_m2": inp.effective_area, "area_factor": round(area_factor, 3), "Cpi": Cpi},
        "coefficients": {"external_pressure_Cp": cp["pressure"], "external_suction_Cp": cp["suction"]},
        "pressure_kPa": p_pos,
        "suction_kPa": p_neg,
        "governing_kPa": governing,
        "overall": "CHECK COMPONENTS",
        "reference": "NBC 2020 Cl. 4.1.7 component/cladding wind pressure workflow",
        "assumptions": "Zone coefficients are practical preliminary values. Confirm final Cp/Cpi from NBC figures for project geometry.",
        "proof": proof_block(
            f"NBC {inp.nbc_version}",
            ["NBC Division B Part 4, Cl. 4.1.7", "NBC component and cladding wind pressure figures/tables"],
            ["nbc_2020", "eccc_climate"],
            "Component coefficients are preliminary defaults and must be checked against the NBC figures for exact roof/wall zone geometry.",
        ),
    }


class SnowDriftInput(BaseModel):
    city: str
    importance: str = "normal"
    lower_roof_width: float = 12.0   # m
    upper_roof_width: float = 8.0    # m
    height_difference: float = 1.5   # m
    Cb: float = 0.8
    Cw: float = 1.0
    Cs: float = 1.0
    Ca: float = 1.0
    nbc_version: str = "2020"


@router.post("/snow-drift")
def calc_snow_drift(inp: SnowDriftInput):
    c = CITIES.get(inp.city)
    if not c:
        return {"error": f"City '{inp.city}' not found"}
    imp = IMPORTANCE.get(inp.importance, IMPORTANCE["normal"])
    base = calc_snow_load(SnowInput(
        city=inp.city, importance=inp.importance, Cb=inp.Cb, Cw=inp.Cw,
        Cs=inp.Cs, Ca=inp.Ca, nbc_version=inp.nbc_version
    ))
    S = base["S_specified"]
    gamma_snow = 2.4  # kN/m3 approximate snow density for drift surcharge
    hd = min(inp.height_difference, 0.6 * max(inp.lower_roof_width, 1))
    drift_width = min(4 * hd, inp.lower_roof_width, max(inp.upper_roof_width, 1))
    drift_surcharge = round(gamma_snow * hd / 2, 3)
    peak_load = round(S + drift_surcharge, 3)
    triangular_area = round(drift_surcharge * drift_width / 2, 3)
    return {
        "code": f"NBC {inp.nbc_version}",
        "city": inp.city,
        "province": c["prov"],
        "balanced_snow_kPa": S,
        "drift": {
            "height_difference_m": inp.height_difference,
            "effective_drift_height_m": round(hd, 2),
            "drift_width_m": round(drift_width, 2),
            "drift_surcharge_peak_kPa": drift_surcharge,
            "peak_snow_load_kPa": peak_load,
            "triangular_drift_load_kN_per_m": triangular_area,
        },
        "overall": "CHECK DRIFT" if drift_surcharge > 0 else "NO DRIFT",
        "reference": "NBC 2020 Cl. 4.1.6 roof accumulation/drift workflow",
        "assumptions": "Preliminary leeward step drift approximation. Confirm final drift geometry and local code interpretation before construction.",
        "proof": proof_block(
            f"NBC {inp.nbc_version}",
            ["NBC Division B Part 4, Cl. 4.1.6", "NBC roof accumulation/drift provisions"],
            ["nbc_2020", "eccc_climate"],
            "Drift geometry is a preliminary approximation; verify the roof step, parapet, and local accumulation case against the adopted NBC edition.",
        ),
    }


# ── Seismic ───────────────────────────────────────────────────────────────────

class SeismicInput(BaseModel):
    city: str
    importance: str = "normal"
    hn: float = Field(10.0, gt=0, le=500)          # total height m
    structural_system: str = "ductile_moment"      # see Rd/Ro table
    seismic_weight: float = Field(1000.0, gt=0)     # W in kN
    site_class: str = "C"           # A-F soil class
    nbc_version: str = "2020"

SYSTEMS = {
    "ductile_moment":    {"name":"Ductile Moment Frame (steel/concrete)", "Rd":5.0, "Ro":1.5},
    "moderately_ductile":{"name":"Moderately Ductile Moment Frame",       "Rd":3.5, "Ro":1.5},
    "limited_ductile":   {"name":"Limited Ductility Frame",                "Rd":2.0, "Ro":1.3},
    "ductile_sw":        {"name":"Ductile Shear Wall (concrete)",          "Rd":3.5, "Ro":1.6},
    "conventional":      {"name":"Conventional Construction",              "Rd":1.5, "Ro":1.3},
    "cantilever":        {"name":"Cantilever Column System",               "Rd":1.0, "Ro":1.0},
}

SITE_FACTORS = {
    # Fa values at Sa(0.2): A-F
    "A":{"Fa":0.7, "Fv":0.5, "name":"Hard Rock"},
    "B":{"Fa":0.8, "Fv":0.6, "name":"Rock"},
    "C":{"Fa":1.0, "Fv":1.0, "name":"Very Dense Soil / Soft Rock (default)"},
    "D":{"Fa":1.1, "Fv":1.4, "name":"Stiff Soil"},
    "E":{"Fa":0.9, "Fv":2.1, "name":"Soft Soil (requires dynamic analysis for E/F)"},
    "F":{"Fa":1.2, "Fv":2.5, "name":"Liquefiable / Sensitive (site-specific required)"},
}

@router.post("/seismic")
def calc_seismic(inp: SeismicInput):
    c = CITIES.get(inp.city)
    if not c:
        return {"error": f"City '{inp.city}' not found"}
    imp = IMPORTANCE.get(inp.importance, IMPORTANCE["normal"])
    sys = SYSTEMS.get(inp.structural_system, SYSTEMS["ductile_moment"])
    sf  = SITE_FACTORS.get(inp.site_class, SITE_FACTORS["C"])

    IE = imp["IE"]
    Rd = sys["Rd"]
    Ro = sys["Ro"]
    W  = inp.seismic_weight
    hn = inp.hn
    Fa = sf["Fa"]
    Fv = sf["Fv"]

    # Approximate fundamental period (NBC 4.1.8.11)
    # Concrete / steel moment frame: Ta = 0.085 × hn^0.75
    # Shear wall: Ta = 0.05 × hn^0.75
    if "sw" in inp.structural_system:
        Ta = round(0.05 * hn**0.75, 3)
    else:
        Ta = round(0.085 * hn**0.75, 3)

    # Design spectral acceleration S(Ta) by interpolation
    # Use site-modified Sa values
    Sa02 = c["Sa02"] * Fa
    Sa05 = c["Sa05"] * Fv
    Sa10 = c["Sa10"] * Fv
    Sa20 = c["Sa20"] * Fv

    if Ta <= 0.2:
        S_Ta = Sa02
    elif Ta <= 0.5:
        S_Ta = Sa02 + (Sa05 - Sa02) * (Ta - 0.2) / 0.3
    elif Ta <= 1.0:
        S_Ta = Sa05 + (Sa10 - Sa05) * (Ta - 0.5) / 0.5
    elif Ta <= 2.0:
        S_Ta = Sa10 + (Sa20 - Sa10) * (Ta - 1.0) / 1.0
    else:
        S_Ta = Sa20 / Ta * 2.0
    S_Ta = round(S_Ta, 4)

    # Higher mode factor Mv (simplified)
    Mv = 1.0 if Ta <= 1.0 else round(1.0 + 0.15 * (Ta - 1.0), 2)

    # Minimum base shear
    V = round(S_Ta * Mv * IE * W / (Rd * Ro), 1)
    V_min = round(S_Ta * 0.8 * Mv * IE * W / (Rd * Ro), 1)
    V_max = round(min(2/3 * Sa02 * Fv * Mv * IE * W / (Rd * Ro), 0.2 * Sa02 * IE * W), 1)
    V_final = max(V, V_min)

    return {
        "city": inp.city,
        "province": c["prov"],
        "nbc_version": inp.nbc_version,
        "inputs": {
            "hn": hn,
            "W": W,
            "IE": IE,
            "Rd": Rd,
            "Ro": Ro,
            "site_class": inp.site_class,
            "Fa": Fa,
            "Fv": Fv,
        },
        "spectral": {
            "Sa_02": round(Sa02, 3),
            "Sa_05": round(Sa05, 3),
            "Sa_10": round(Sa10, 3),
            "Sa_20": round(Sa20, 3),
        },
        "Ta": Ta,
        "S_Ta": S_Ta,
        "Mv": Mv,
        "V_design": V_final,
        "V_units": "kN",
        "V_over_W": round(V_final / W, 4),
        "system": sys["name"],
        "site": sf["name"],
        "formula": f"V = S(Ta)×Mv×IE×W / (Rd×Ro) = {S_Ta}×{Mv}×{IE}×{W} / ({Rd}×{Ro})",
        "reference": "NBC 2020 Cl. 4.1.8",
        "proof": proof_block(
            f"NBC {inp.nbc_version}",
            ["NBC Division B Part 4, Cl. 4.1.8", "NBC seismic hazard values"],
            ["nbc_2020", "nrcan_seismic"],
            "Seismic values are stored by city for fast preliminary checks; final projects should use official coordinates and locally adopted seismic data.",
        ),
    }


# ── CSA A23.3 Concrete Beam Design ───────────────────────────────────────────

class CSAConcreteBeamInput(BaseModel):
    # Geometry
    b: float = 300        # mm width
    d: float = 500        # mm effective depth
    # Materials
    fc: float = 30        # MPa concrete compressive strength
    fy: float = 400       # MPa rebar yield
    # Loading (factored)
    Mf: float = 200       # kN·m factored moment
    Vf: float = 150       # kN factored shear
    # Stirrups
    dv_s: float = 10      # mm stirrup diameter
    nlegs: int = 2        # stirrup legs


def _a23_alpha_beta(fc: float):
    return max(0.67, 0.85 - 0.0015 * fc), max(0.67, 0.97 - 0.0025 * fc)


@router.post("/csa-concrete-beam")
def csa_concrete_beam(inp: CSAConcreteBeamInput):
    # CSA A23.3-19 resistance factors
    phi_c = 0.65
    phi_s = 0.85

    fc  = inp.fc
    fy  = inp.fy
    b   = inp.b
    d   = inp.d
    Mf  = inp.Mf * 1e6   # Nm → N·mm

    # α1, β1 (CSA A23.3 Cl.10.1.7)
    alpha1, beta1 = _a23_alpha_beta(fc)

    # Balanced reinforcement ratio
    cb = 700 * d / (700 + fy)
    ab = beta1 * cb
    rho_b = alpha1 * phi_c * fc * beta1 * 700 / (phi_s * fy * (700 + fy))

    # Max allowed rho (CSA A23.3 Cl.10.5.2): 0.75 rho_b but ≤ code limit
    rho_max = 0.75 * rho_b

    # Required Ast
    # Mf = phi_s × Ast × fy × (d - a/2), iterate
    # Using quadratic: a = Ast×phi_s×fy / (alpha1×phi_c×fc×b)
    # → phi_s×fy×Ast×d - phi_s²×fy²×Ast²/(2×alpha1×phi_c×fc×b) = Mf
    A = phi_s * fy / (2 * alpha1 * phi_c * fc * b)
    B = -(phi_s * fy * d)
    C = Mf
    discriminant = B**2 - 4*A*C
    Ast_req = (-B - math.sqrt(discriminant)) / (2*A)
    a_req = Ast_req * phi_s * fy / (alpha1 * phi_c * fc * b)
    Mr = round(phi_s * Ast_req * fy * (d - a_req/2) / 1e6, 1)

    # Minimum Ast (CSA A23.3 Cl.10.5.1.2)
    Ast_min = max(0.2 * math.sqrt(fc) / fy * b * d, 1.4 / fy * b * d)

    # Choose rebar
    Ast_prov = max(Ast_req, Ast_min)
    rho_prov = Ast_prov / (b * d)
    status = "SAFE" if rho_prov <= rho_max and Ast_prov >= Ast_min else "REVISE"

    # Shear design (CSA A23.3 Cl.11 — General Method simplified)
    Vf_kN = inp.Vf
    # Concrete shear resistance Vc
    bw = b / 1000  # m
    dv = max(0.9*d, 0.72*inp.d) / 1000  # m
    beta_shear = 0.18
    Vc = round(phi_c * beta_shear * math.sqrt(fc) * bw * dv * 1000, 1)

    # Stirrup spacing (s) for Vs = Vf - Vc
    Vs_req = max(Vf_kN - Vc, 0)
    Av = inp.nlegs * math.pi * (inp.dv_s/2)**2
    if Vs_req > 0:
        s_req = round(phi_s * Av * fy * dv * 1000 / (Vs_req * 1000), 0)
        s_prov = min(s_req, 0.7 * inp.d, 600)
    else:
        s_prov = min(0.7 * inp.d, 600)
        s_req = s_prov

    shear_ok = "SAFE" if Vc + phi_s*Av*fy*dv*1000/(s_prov/1000)/1000 >= Vf_kN else "REVISE"

    return {
        "code": "CSA A23.3-19",
        "section": f"{b}×{inp.d} mm",
        "materials": {"fc": fc, "fy": fy},
        "flexure": {
            "Mf_kNm": inp.Mf,
            "Ast_required_mm2": round(Ast_req, 0),
            "Ast_min_mm2": round(Ast_min, 0),
            "Ast_provided_mm2": round(Ast_prov, 0),
            "a_depth_mm": round(a_req, 1),
            "Mr_kNm": Mr,
            "rho_prov": round(rho_prov * 100, 3),
            "rho_max_pct": round(rho_max * 100, 3),
            "flexure_status": "✓ SAFE" if Ast_prov >= Ast_req and rho_prov <= rho_max else "✗ REVISE",
        },
        "shear": {
            "Vf_kN": Vf_kN,
            "Vc_kN": Vc,
            "Vs_req_kN": round(Vs_req, 1),
            "stirrup": f"{inp.nlegs}L-{int(inp.dv_s)}mm",
            "s_required_mm": s_req,
            "s_provided_mm": s_prov,
            "shear_status": "✓ " + shear_ok,
        },
        "overall": "✓ SAFE" if "SAFE" in status and "SAFE" in shear_ok else "✗ REVISE — see notes",
        "reference": "CSA A23.3-19 Cl.10 & 11",
        "proof": proof_block(
            "CSA A23.3:19",
            ["CSA A23.3 flexure provisions", "CSA A23.3 shear provisions"],
            ["csa_a23_3"],
            "Preliminary reinforced concrete beam check; detailing, serviceability, development length, fire, and durability checks are separate.",
        ),
    }


# ── CSA A23.3 Concrete Column / Footing / Development ────────────────────────

class CSAConcreteColumnInput(BaseModel):
    b: float = 400          # mm
    h: float = 400          # mm
    fc: float = 30          # MPa
    fy: float = 400         # MPa
    bar_dia: float = 25     # mm
    n_bars: int = 8
    Pu: float = 1200        # kN factored axial load
    Mux: float = 120        # kN-m factored moment about x
    Muy: float = 80         # kN-m factored moment about y
    unsupported_length: float = 3.0  # m
    k_factor: float = 1.0


@router.post("/csa-concrete-column")
def csa_concrete_column(inp: CSAConcreteColumnInput):
    phi_c = 0.65
    phi_s = 0.85
    Ag = inp.b * inp.h
    Ast = inp.n_bars * math.pi * inp.bar_dia**2 / 4
    rho = Ast / Ag
    Ac = max(Ag - Ast, 0)

    Po = 0.85 * inp.fc * Ac + inp.fy * Ast
    Pr_max = 0.80 * (phi_c * 0.85 * inp.fc * Ac + phi_s * inp.fy * Ast) / 1000

    rx = 0.30 * inp.h
    ry = 0.30 * inp.b
    slender_x = inp.k_factor * inp.unsupported_length * 1000 / max(rx, 1)
    slender_y = inp.k_factor * inp.unsupported_length * 1000 / max(ry, 1)

    cover = 40
    d_x = max(inp.h - cover - inp.bar_dia / 2, inp.h * 0.8)
    d_y = max(inp.b - cover - inp.bar_dia / 2, inp.b * 0.8)
    alpha1, _ = _a23_alpha_beta(inp.fc)
    Mrx = phi_s * Ast * inp.fy * (d_x - alpha1 * inp.h / 6) / 1e6
    Mry = phi_s * Ast * inp.fy * (d_y - alpha1 * inp.b / 6) / 1e6

    axial_ratio = inp.Pu / Pr_max if Pr_max > 0 else 999
    mx_ratio = inp.Mux / Mrx if Mrx > 0 else 999
    my_ratio = inp.Muy / Mry if Mry > 0 else 999
    interaction = axial_ratio + mx_ratio + my_ratio
    rho_ok = 0.01 <= rho <= 0.08
    slender_note = "Slenderness effects should be considered" if max(slender_x, slender_y) > 34 else "Short column approximation"
    ok = interaction <= 1.0 and rho_ok

    return {
        "code": "CSA A23.3-19",
        "section": f"{int(inp.b)}x{int(inp.h)} mm",
        "reinforcement": f"{inp.n_bars}-{int(inp.bar_dia)}M equivalent bars",
        "Ag_mm2": round(Ag, 0),
        "Ast_mm2": round(Ast, 0),
        "rho_pct": round(rho * 100, 2),
        "axial": {
            "Pu_kN": inp.Pu,
            "Pr_max_kN": round(Pr_max, 1),
            "utilization_pct": round(axial_ratio * 100, 1),
        },
        "biaxial": {
            "Mux_kNm": inp.Mux,
            "Muy_kNm": inp.Muy,
            "Mrx_kNm": round(Mrx, 1),
            "Mry_kNm": round(Mry, 1),
            "interaction_ratio": round(interaction, 3),
            "interaction_status": "SAFE" if interaction <= 1.0 else "REVISE",
        },
        "slenderness": {
            "kl_r_x": round(slender_x, 1),
            "kl_r_y": round(slender_y, 1),
            "note": slender_note,
        },
        "overall": "SAFE" if ok else "REVISE",
        "reference": "CSA A23.3-19 compression member check, simplified P-Mx-My interaction",
        "assumptions": "Rectangular tied column, approximate biaxial interaction for preliminary design. Validate final design with detailed interaction diagrams.",
        "proof": proof_block(
            "CSA A23.3:19",
            ["CSA A23.3 compression member provisions", "CSA A23.3 axial load and biaxial bending interaction design"],
            ["csa_a23_3"],
            "Uses a simplified preliminary P-Mx-My interaction. Final column design should be checked with full code interaction diagrams and slenderness effects.",
        ),
    }


class CSAConcreteFootingInput(BaseModel):
    Pu: float = 1200          # kN service/factored vertical load
    Mx: float = 0             # kN-m
    My: float = 0             # kN-m
    bearing_capacity: float = 200  # kPa allowable/factored bearing
    column_b: float = 400     # mm
    column_h: float = 400     # mm
    footing_L: float = 2.8    # m
    footing_B: float = 2.8    # m
    thickness: float = 550    # mm
    fc: float = 30
    fy: float = 400


@router.post("/csa-concrete-footing")
def csa_concrete_footing(inp: CSAConcreteFootingInput):
    phi_c = 0.65
    phi_s = 0.85
    area = inp.footing_L * inp.footing_B
    q_avg = inp.Pu / area
    ex = inp.My / inp.Pu if inp.Pu else 0
    ey = inp.Mx / inp.Pu if inp.Pu else 0
    q_max = q_avg * (1 + 6 * abs(ex) / inp.footing_L + 6 * abs(ey) / inp.footing_B)
    q_min = q_avg * (1 - 6 * abs(ex) / inp.footing_L - 6 * abs(ey) / inp.footing_B)

    cant_x = (inp.footing_L - inp.column_b / 1000) / 2
    cant_y = (inp.footing_B - inp.column_h / 1000) / 2
    Mu_x = q_max * inp.footing_B * cant_x**2 / 2
    Mu_y = q_max * inp.footing_L * cant_y**2 / 2
    d = max(inp.thickness - 75, inp.thickness * 0.8)
    z = 0.9 * d
    As_x = Mu_x * 1e6 / (phi_s * inp.fy * z)
    As_y = Mu_y * 1e6 / (phi_s * inp.fy * z)

    bo = 2 * ((inp.column_b + d) + (inp.column_h + d))
    punching_v = max(inp.Pu - q_max * ((inp.column_b + d) / 1000) * ((inp.column_h + d) / 1000), 0)
    vc = 0.19 * math.sqrt(inp.fc)
    Vr_punch = phi_c * vc * bo * d / 1000
    punch_ratio = punching_v / Vr_punch if Vr_punch > 0 else 999

    one_way_vx = q_max * inp.footing_B * max(cant_x - d / 1000, 0)
    one_way_vy = q_max * inp.footing_L * max(cant_y - d / 1000, 0)
    bwx = inp.footing_B * 1000
    bwy = inp.footing_L * 1000
    Vr_x = phi_c * vc * bwx * d / 1000
    Vr_y = phi_c * vc * bwy * d / 1000

    ok = q_max <= inp.bearing_capacity and q_min >= 0 and punch_ratio <= 1 and one_way_vx <= Vr_x and one_way_vy <= Vr_y
    return {
        "code": "CSA A23.3-19 / NBC geotechnical bearing workflow",
        "footing": f"{inp.footing_L} m x {inp.footing_B} m x {int(inp.thickness)} mm",
        "soil": {
            "q_avg_kPa": round(q_avg, 1),
            "q_max_kPa": round(q_max, 1),
            "q_min_kPa": round(q_min, 1),
            "bearing_capacity_kPa": inp.bearing_capacity,
            "bearing_status": "SAFE" if q_max <= inp.bearing_capacity and q_min >= 0 else "REVISE",
        },
        "flexure": {
            "Mu_x_kNm": round(Mu_x, 1),
            "Mu_y_kNm": round(Mu_y, 1),
            "As_x_mm2_per_m": round(As_x / inp.footing_B, 0),
            "As_y_mm2_per_m": round(As_y / inp.footing_L, 0),
        },
        "punching": {
            "Vu_kN": round(punching_v, 1),
            "Vr_kN": round(Vr_punch, 1),
            "utilization_pct": round(punch_ratio * 100, 1),
            "status": "SAFE" if punch_ratio <= 1 else "REVISE",
        },
        "one_way_shear": {
            "Vx_kN": round(one_way_vx, 1),
            "Vr_x_kN": round(Vr_x, 1),
            "Vy_kN": round(one_way_vy, 1),
            "Vr_y_kN": round(Vr_y, 1),
        },
        "overall": "SAFE" if ok else "REVISE",
        "reference": "CSA A23.3-19 footing flexure, one-way shear, punching shear",
        "proof": proof_block(
            "CSA A23.3:19 with local geotechnical bearing input",
            ["CSA A23.3 footing flexure", "CSA A23.3 one-way shear", "CSA A23.3 two-way punching shear"],
            ["csa_a23_3"],
            "Soil bearing capacity must come from the project geotechnical report and local authority requirements.",
        ),
    }


class CSADevelopmentLengthInput(BaseModel):
    bar_dia: float = 20
    fc: float = 30
    fy: float = 400
    coating: str = "uncoated"  # uncoated / epoxy
    concrete_location: str = "normal"  # normal / top_bar
    confinement: str = "normal"  # normal / confined


@router.post("/csa-development-length")
def csa_development_length(inp: CSADevelopmentLengthInput):
    k_epoxy = 1.5 if inp.coating == "epoxy" else 1.0
    k_top = 1.3 if inp.concrete_location == "top_bar" else 1.0
    k_conf = 0.8 if inp.confinement == "confined" else 1.0
    base = 0.45 * inp.fy / math.sqrt(inp.fc) * inp.bar_dia
    ld = max(base * k_epoxy * k_top * k_conf, 300, 12 * inp.bar_dia)
    splice = 1.3 * ld
    hook = max(8 * inp.bar_dia, 150)
    return {
        "code": "CSA A23.3-19",
        "bar_dia_mm": inp.bar_dia,
        "factors": {"epoxy": k_epoxy, "top_bar": k_top, "confinement": k_conf},
        "tension_development_length_mm": round(ld, 0),
        "class_b_splice_length_mm": round(splice, 0),
        "standard_hook_embedment_mm": round(hook, 0),
        "reference": "CSA A23.3-19 development and splice length workflow, preliminary calculator",
        "proof": proof_block(
            "CSA A23.3:19",
            ["CSA A23.3 reinforcement development and splice provisions"],
            ["csa_a23_3"],
            "Preliminary development length workflow; verify bar location, cover, spacing, confinement, coating, and concrete placement conditions.",
        ),
    }


class CSAConcreteSlabInput(BaseModel):
    slab_type: str = "one_way"  # one_way / two_way_strip
    span_short: float = 4.0     # m
    span_long: float = 5.5      # m
    thickness: float = 150      # mm
    fc: float = 30
    fy: float = 400
    factored_load: float = 9.0  # kPa
    bar_dia: float = 12
    cover: float = 25


@router.post("/csa-concrete-slab")
def csa_concrete_slab(inp: CSAConcreteSlabInput):
    phi_s = 0.85
    phi_c = 0.65
    b = 1000.0
    d = max(inp.thickness - inp.cover - inp.bar_dia / 2, inp.thickness * 0.75)
    Lx = inp.span_short
    Ly = max(inp.span_long, inp.span_short)
    w = inp.factored_load

    if inp.slab_type == "two_way_strip" and Ly / Lx < 2:
        mx = w * Lx**2 / 18
        my = w * Lx**2 / 28
        mode = "two-way preliminary strip coefficients"
    else:
        mx = w * Lx**2 / 8
        my = 0.25 * mx
        mode = "one-way strip"

    z = 0.9 * d
    As_x = mx * 1e6 / (phi_s * inp.fy * z)
    As_y = my * 1e6 / (phi_s * inp.fy * z)
    As_min = max(0.0018 * b * inp.thickness, 0.2 * math.sqrt(inp.fc) / inp.fy * b * d)
    Avail_bar = math.pi * inp.bar_dia**2 / 4
    spacing_x = min(Avail_bar * 1000 / max(As_x, As_min), 3 * inp.thickness, 450)
    spacing_y = min(Avail_bar * 1000 / max(As_y, As_min), 3 * inp.thickness, 450)

    Vu = w * Lx / 2
    vc = 0.19 * math.sqrt(inp.fc)
    Vr = phi_c * vc * b * d / 1000
    shear_ok = Vu <= Vr
    return {
        "code": "CSA A23.3-19",
        "slab": f"{int(inp.thickness)} mm {inp.slab_type}",
        "mode": mode,
        "effective_depth_mm": round(d, 1),
        "moments": {"Mx_kNm_per_m": round(mx, 2), "My_kNm_per_m": round(my, 2)},
        "reinforcement": {
            "As_x_mm2_per_m": round(max(As_x, As_min), 0),
            "As_y_mm2_per_m": round(max(As_y, As_min), 0),
            "bar": f"{int(inp.bar_dia)}M equivalent",
            "spacing_x_mm": round(spacing_x, 0),
            "spacing_y_mm": round(spacing_y, 0),
        },
        "one_way_shear": {"Vu_kN_per_m": round(Vu, 1), "Vr_kN_per_m": round(Vr, 1), "status": "SAFE" if shear_ok else "REVISE"},
        "overall": "SAFE" if shear_ok else "REVISE",
        "reference": "CSA A23.3-19 slab flexure and one-way shear preliminary workflow",
        "proof": proof_block(
            "CSA A23.3:19",
            ["CSA A23.3 slab flexure", "CSA A23.3 minimum reinforcement", "CSA A23.3 one-way shear"],
            ["csa_a23_3"],
            "Two-way slab values use preliminary strip coefficients. Final design should verify boundary conditions, deflection, punching shear, and detailing.",
        ),
    }


class CSAConcretePunchingInput(BaseModel):
    Vu: float = 900           # kN factored punching shear demand
    column_b: float = 400     # mm
    column_h: float = 400     # mm
    slab_thickness: float = 220
    cover: float = 25
    bar_dia: float = 16
    fc: float = 30
    interior: bool = True


@router.post("/csa-punching-shear")
def csa_punching_shear(inp: CSAConcretePunchingInput):
    phi_c = 0.65
    d = max(inp.slab_thickness - inp.cover - inp.bar_dia / 2, inp.slab_thickness * 0.75)
    bo = 2 * ((inp.column_b + d) + (inp.column_h + d))
    if not inp.interior:
        bo *= 0.75
    beta = max(inp.column_b, inp.column_h) / max(min(inp.column_b, inp.column_h), 1)
    vc = min(0.19 * math.sqrt(inp.fc), (0.19 + 0.10 / beta) * math.sqrt(inp.fc))
    Vr = phi_c * vc * bo * d / 1000
    stress = inp.Vu * 1000 / (bo * d)
    util = inp.Vu / Vr if Vr > 0 else 999
    return {
        "code": "CSA A23.3-19",
        "critical_perimeter_mm": round(bo, 0),
        "effective_depth_mm": round(d, 1),
        "punching": {
            "Vu_kN": inp.Vu,
            "Vr_kN": round(Vr, 1),
            "v_u_MPa": round(stress, 3),
            "v_r_MPa": round(phi_c * vc, 3),
            "utilization_pct": round(util * 100, 1),
        },
        "overall": "SAFE" if util <= 1 else "REVISE",
        "reference": "CSA A23.3-19 two-way punching shear preliminary workflow",
        "proof": proof_block(
            "CSA A23.3:19",
            ["CSA A23.3 two-way shear / punching shear provisions"],
            ["csa_a23_3"],
            "Preliminary interior/edge perimeter approximation. Final design must confirm openings, unbalanced moment transfer, drops, capitals, and shear reinforcement.",
        ),
    }


# ── CSA S16 Steel Beam Design ─────────────────────────────────────────────────

class CSASteelBeamInput(BaseModel):
    section: str = "W310x97"   # Section name
    Fy: float = 350             # MPa (G40.21 350W)
    Mf: float = 300             # kN·m factored moment
    Vf: float = 200             # kN factored shear
    Lx: float = 6.0             # m span
    Lb: float = 0.0             # m unbraced length (0 = fully braced)
    # Standard properties (user can override)
    Ix: float = 280e6           # mm⁴
    Zx: float = 2030e3          # mm³ (plastic modulus)
    Sx: float = 1440e3          # mm³ (elastic section modulus)
    d:  float = 308             # mm depth
    tw: float = 9.9             # mm web thickness
    bf: float = 310             # mm flange width
    tf: float = 15.4            # mm flange thickness

@router.post("/csa-steel-beam")
def csa_steel_beam(inp: CSASteelBeamInput):
    phi = 0.90   # CSA S16 resistance factor

    Fy = inp.Fy
    Zx = inp.Zx
    Sx = inp.Sx

    # Plastic moment resistance
    Mp = Fy * Zx / 1e6          # kN·m
    Mr = round(phi * Mp, 1)     # factored resistance

    # Lateral-torsional buckling check (simplified)
    if inp.Lb > 0:
        # Limiting unbraced lengths
        Lp = round(1.76 * (inp.bf/2) * math.sqrt(200000/Fy) / 1000, 2)
        Lu = round(1.1 * math.sqrt(inp.Ix * Fy / (Sx * Fy)) / 1000, 2)

        if inp.Lb <= Lp:
            Mr_ltb = Mr
            ltb_regime = "Compact — no LTB reduction"
        elif inp.Lb <= Lu:
            factor = 1 - 0.5 * (inp.Lb - Lp) / (Lu - Lp)
            Mr_ltb = round(phi * Mp * factor, 1)
            ltb_regime = f"Inelastic LTB — Mr reduced to {Mr_ltb} kN·m"
        else:
            Me = round(math.pi**2 * 200000 * inp.Ix / (inp.Lb*1000)**2 * inp.Sx / inp.Zx / 1e6, 1)
            Mr_ltb = round(phi * Me, 1)
            ltb_regime = f"Elastic LTB — Mr reduced to {Mr_ltb} kN·m"
        Mr_final = min(Mr, Mr_ltb)
    else:
        Mr_final = Mr
        ltb_regime = "Fully braced — no LTB"
        Lp = Lu = 0

    # Shear resistance
    Aw = inp.d * inp.tw          # mm²
    Vr = round(phi * 0.66 * Fy * Aw / 1e3, 1)

    flexure_ok = Mr_final >= inp.Mf
    shear_ok   = Vr >= inp.Vf

    return {
        "code": "CSA S16-19",
        "section": inp.section,
        "steel_grade": f"G40.21 {Fy}W",
        "flexure": {
            "Mf_kNm": inp.Mf,
            "Mp_kNm": round(Mp, 1),
            "Mr_plastic_kNm": Mr,
            "Mr_final_kNm": Mr_final,
            "utilization_pct": round(inp.Mf / Mr_final * 100, 1),
            "LTB_regime": ltb_regime,
            "flexure_status": "✓ SAFE" if flexure_ok else "✗ REVISE",
        },
        "shear": {
            "Vf_kN": inp.Vf,
            "Vr_kN": Vr,
            "utilization_pct": round(inp.Vf / Vr * 100, 1),
            "shear_status": "✓ SAFE" if shear_ok else "✗ REVISE",
        },
        "overall": "✓ SAFE" if flexure_ok and shear_ok else "✗ REVISE — see shear/flexure",
        "reference": "CSA S16-19 Cl.13 & 14",
        "proof": proof_block(
            "CSA S16:19",
            ["CSA S16 member resistance", "CSA S16 flexural resistance", "CSA S16 shear resistance"],
            ["csa_s16"],
            "Preliminary steel beam check with user-entered section properties; verify the exact CISC section, class, bracing, holes, and loading.",
        ),
    }


class CSASteelColumnInput(BaseModel):
    section: str = "W310x97"
    Fy: float = 350
    Ag: float = 12300          # mm2
    rx: float = 132            # mm
    ry: float = 78             # mm
    KLx: float = 3.0           # m
    KLy: float = 3.0           # m
    Cf: float = 1400           # kN factored compression


@router.post("/csa-steel-column")
def csa_steel_column(inp: CSASteelColumnInput):
    phi = 0.90
    E = 200000
    klr_x = inp.KLx * 1000 / max(inp.rx, 1)
    klr_y = inp.KLy * 1000 / max(inp.ry, 1)
    klr = max(klr_x, klr_y)
    Fe = math.pi**2 * E / max(klr**2, 1)
    lam = math.sqrt(inp.Fy / Fe) if Fe > 0 else 99
    Cr_nom = inp.Ag * inp.Fy * (0.658 ** (lam**2)) if lam <= 1.5 else inp.Ag * 0.877 * Fe
    Cr = phi * Cr_nom / 1000
    util = inp.Cf / Cr if Cr > 0 else 999
    return {
        "code": "CSA S16-19",
        "section": inp.section,
        "slenderness": {"KLr_x": round(klr_x, 1), "KLr_y": round(klr_y, 1), "governing_KLr": round(klr, 1)},
        "stress": {"Fe_MPa": round(Fe, 1), "lambda": round(lam, 3)},
        "compression": {"Cf_kN": inp.Cf, "Cr_kN": round(Cr, 1), "utilization_pct": round(util * 100, 1)},
        "overall": "SAFE" if util <= 1 else "REVISE",
        "reference": "CSA S16-19 compression member column curve workflow",
        "proof": proof_block(
            "CSA S16:19",
            ["CSA S16 compression member resistance", "CSA S16 column curve workflow"],
            ["csa_s16"],
            "Preliminary axial steel column check. Verify effective lengths, section class, residual stresses, connection restraint, and combined loading.",
        ),
    }


class CSABasePlateInput(BaseModel):
    Pu: float = 1200        # kN
    M: float = 0            # kN-m
    plate_N: float = 550    # mm
    plate_B: float = 550    # mm
    column_d: float = 310   # mm
    column_bf: float = 250  # mm
    plate_t: float = 25     # mm
    Fy_plate: float = 300
    fc: float = 30
    anchor_count: int = 4
    anchor_dia: float = 24
    anchor_Fu: float = 830


@router.post("/csa-baseplate")
def csa_baseplate(inp: CSABasePlateInput):
    phi_c = 0.65
    phi_s = 0.80
    A1 = inp.plate_N * inp.plate_B
    q_avg = inp.Pu * 1000 / A1
    e = inp.M * 1e6 / (inp.Pu * 1000) if inp.Pu else 0
    q_max = q_avg * (1 + 6 * abs(e) / inp.plate_N)
    bearing_cap = 0.85 * phi_c * inp.fc
    m = (inp.plate_N - 0.95 * inp.column_d) / 2
    n = (inp.plate_B - 0.80 * inp.column_bf) / 2
    cant = max(m, n, 0)
    t_req = cant * math.sqrt(max(2 * q_max / (0.9 * inp.Fy_plate), 0))
    tension = max(inp.M * 1e6 / max(inp.plate_N - 75, 1) - inp.Pu * 1000 / 2, 0)
    anchor_area = math.pi * inp.anchor_dia**2 / 4
    anchor_res = phi_s * 0.75 * inp.anchor_Fu * anchor_area * inp.anchor_count / 1000
    ok = q_max <= bearing_cap and inp.plate_t >= t_req and tension / 1000 <= anchor_res
    return {
        "code": "CSA S16-19 / CSA A23.3 bearing workflow",
        "plate": f"{int(inp.plate_N)}x{int(inp.plate_B)}x{int(inp.plate_t)} mm",
        "bearing": {
            "q_max_MPa": round(q_max, 2),
            "bearing_capacity_MPa": round(bearing_cap, 2),
            "status": "SAFE" if q_max <= bearing_cap else "REVISE",
        },
        "plate_bending": {
            "cantilever_projection_mm": round(cant, 1),
            "required_thickness_mm": round(t_req, 1),
            "provided_thickness_mm": inp.plate_t,
            "status": "SAFE" if inp.plate_t >= t_req else "REVISE",
        },
        "anchors": {
            "tension_demand_kN": round(tension / 1000, 1),
            "anchor_resistance_kN": round(anchor_res, 1),
            "status": "SAFE" if tension / 1000 <= anchor_res else "REVISE",
        },
        "overall": "SAFE" if ok else "REVISE",
        "reference": "CSA S16-19 base plate preliminary design; verify anchors and concrete breakout separately.",
        "proof": proof_block(
            "CSA S16:19 / CSA A23.3:19",
            ["CSA S16 base plate design workflow", "CSA A23.3 concrete bearing provisions"],
            ["csa_s16", "csa_a23_3"],
            "Preliminary base plate check. Anchor rods, concrete breakout, grout, welds, and erection tolerances require separate project verification.",
        ),
    }


class CSABoltGroupInput(BaseModel):
    bolt_dia: float = 20
    bolt_grade_Fu: float = 830
    n_bolts: int = 4
    shear_planes: int = 1
    factored_shear: float = 180  # kN
    plate_thickness: float = 10
    plate_Fu: float = 450
    edge_distance: float = 40


@router.post("/csa-bolt-group")
def csa_bolt_group(inp: CSABoltGroupInput):
    phi = 0.80
    Ab = math.pi * inp.bolt_dia**2 / 4
    Vr_bolt = phi * 0.45 * inp.bolt_grade_Fu * Ab * inp.shear_planes / 1000
    Vr_group = Vr_bolt * inp.n_bolts
    bearing_per_bolt = phi * 2.4 * inp.bolt_dia * inp.plate_thickness * inp.plate_Fu / 1000
    bearing_group = bearing_per_bolt * inp.n_bolts
    edge_ok = inp.edge_distance >= 1.5 * inp.bolt_dia
    capacity = min(Vr_group, bearing_group)
    util = inp.factored_shear / capacity if capacity > 0 else 999
    return {
        "code": "CSA S16-19",
        "bolt": f"{int(inp.n_bolts)} x M{int(inp.bolt_dia)}",
        "shear": {"bolt_shear_kN_each": round(Vr_bolt, 1), "group_shear_kN": round(Vr_group, 1)},
        "bearing": {"bearing_kN_each": round(bearing_per_bolt, 1), "group_bearing_kN": round(bearing_group, 1), "edge_distance_ok": edge_ok},
        "capacity_kN": round(capacity, 1),
        "demand_kN": inp.factored_shear,
        "utilization_pct": round(util * 100, 1),
        "overall": "SAFE" if util <= 1 and edge_ok else "REVISE",
        "reference": "CSA S16-19 bolted connection shear and bearing workflow",
        "proof": proof_block(
            "CSA S16:19",
            ["CSA S16 bolted connection shear", "CSA S16 bolt bearing and edge distance provisions"],
            ["csa_s16"],
            "Preliminary bolt group check. Verify bolt holes, slip-critical requirements, prying, block shear, tear-out, and connection eccentricity.",
        ),
    }


class CSAWeldInput(BaseModel):
    weld_size: float = 6       # mm fillet leg
    weld_length: float = 200   # mm total effective length
    electrode_Fu: float = 490  # MPa
    factored_load: float = 120 # kN
    load_angle_deg: float = 0


@router.post("/csa-weld")
def csa_weld(inp: CSAWeldInput):
    phi = 0.67
    throat = 0.707 * inp.weld_size
    angle_factor = 1.0 + 0.5 * math.sin(math.radians(inp.load_angle_deg))**1.5
    resistance = phi * 0.67 * inp.electrode_Fu * throat * inp.weld_length * angle_factor / 1000
    util = inp.factored_load / resistance if resistance > 0 else 999
    return {
        "code": "CSA S16-19",
        "weld": f"{inp.weld_size} mm fillet x {inp.weld_length} mm",
        "effective_throat_mm": round(throat, 2),
        "angle_factor": round(angle_factor, 3),
        "resistance_kN": round(resistance, 1),
        "demand_kN": inp.factored_load,
        "utilization_pct": round(util * 100, 1),
        "overall": "SAFE" if util <= 1 else "REVISE",
        "reference": "CSA S16-19 fillet weld resistance workflow",
        "proof": proof_block(
            "CSA S16:19",
            ["CSA S16 welded connection resistance", "CSA S16 fillet weld provisions"],
            ["csa_s16"],
            "Preliminary fillet weld resistance check. Verify weld group eccentricity, base metal strength, access, inspection class, and electrode compatibility.",
        ),
    }


class CSAWebCripplingInput(BaseModel):
    section: str = "W310x97"
    Fy: float = 350
    factored_reaction: float = 450  # kN
    bearing_length: float = 100      # mm
    d: float = 310                  # mm
    tw: float = 9.9                 # mm
    tf: float = 15.4                # mm
    end_reaction: bool = True
    stiffeners: bool = False


@router.post("/csa-web-crippling")
def csa_web_crippling(inp: CSAWebCripplingInput):
    phi = 0.90
    N = inp.bearing_length
    k = inp.tf + 8
    coeff = 1.6 if inp.end_reaction else 2.4
    stiffener_factor = 1.75 if inp.stiffeners else 1.0
    Cr = phi * coeff * inp.tw**2 * inp.Fy * (1 + 3 * N / max(inp.d, 1)) * (1 + k / max(N, 1)) * stiffener_factor / 1000
    util = inp.factored_reaction / Cr if Cr > 0 else 999
    return {
        "code": "CSA S16-19",
        "section": inp.section,
        "web_crippling": {
            "reaction_kN": inp.factored_reaction,
            "resistance_kN": round(Cr, 1),
            "bearing_length_mm": inp.bearing_length,
            "stiffeners_included": inp.stiffeners,
            "utilization_pct": round(util * 100, 1),
        },
        "overall": "SAFE" if util <= 1 else "REVISE",
        "reference": "CSA S16-19 web bearing/crippling preliminary workflow",
        "assumptions": "Preliminary concentrated reaction check. Confirm final S16 clause factors for exact shape and loading condition.",
        "proof": proof_block(
            "CSA S16:19",
            ["CSA S16 concentrated load, web yielding, and web crippling provisions"],
            ["csa_s16"],
            "Preliminary concentrated reaction check. Confirm exact S16 factors for shape, support condition, bearing length, stiffeners, and load position.",
        ),
    }


# ── CSA O86 Wood Beam Design ──────────────────────────────────────────────────

class CSAWoodBeamInput(BaseModel):
    species: str = "SPF"        # Species combination
    grade: str = "No.1"         # Grade
    width: float = 89           # mm
    depth: float = 235          # mm
    span: float = 4.0           # m
    Mf: float = 15.0            # kN·m factored moment
    Vf: float = 12.0            # kN factored shear
    service_condition: str = "dry"   # dry / wet
    load_duration: str = "standard"  # short/standard/long/permanent

# Species reference design values (MPa) — CSA O86-19 Table 6.3
WOOD_VALUES = {
    ("SPF","No.1"): {"fb":11.8, "fv":1.5,  "E":9500},
    ("SPF","No.2"): {"fb":9.0,  "fv":1.5,  "E":9000},
    ("SPF","SS"):   {"fb":15.1, "fv":1.5,  "E":10000},
    ("DF","No.1"):  {"fb":14.0, "fv":1.9,  "E":11000},
    ("DF","No.2"):  {"fb":10.5, "fv":1.9,  "E":10500},
    ("DF","SS"):    {"fb":18.3, "fv":1.9,  "E":12500},
    ("HF","No.1"):  {"fb":10.0, "fv":1.6,  "E":10000},
    ("HF","No.2"):  {"fb":8.0,  "fv":1.6,  "E":9500},
}

# Duration of load factor KD
KD_FACTORS = {"short":1.15, "standard":1.0, "long":0.80, "permanent":0.65}

# Service condition factor KS (wet)
KS_WET = {"fb":0.84, "fv":0.97, "E":0.84}

@router.post("/csa-wood-beam")
def csa_wood_beam(inp: CSAWoodBeamInput):
    key = (inp.species, inp.grade)
    vals = WOOD_VALUES.get(key, WOOD_VALUES[("SPF","No.1")])

    phi_b = 0.9  # bending
    phi_v = 0.9  # shear

    KD = KD_FACTORS.get(inp.load_duration, 1.0)
    KS_b = 0.84 if inp.service_condition == "wet" else 1.0
    KS_v = 0.97 if inp.service_condition == "wet" else 1.0

    # Size factor KZ (CSA O86 Cl.5.4.4)
    d = inp.depth
    KZ_b = min((140/d)**0.29, 1.3)

    # Section properties
    S = round(inp.width * d**2 / 6, 0)   # mm³ elastic section modulus
    Ib = inp.width * d                     # shear area approximation

    # Factored bending resistance
    fb_d = vals["fb"] * KD * KS_b * KZ_b
    Mr = round(phi_b * fb_d * S / 1e6, 2)  # kN·m

    # Factored shear resistance
    fv_d = vals["fv"] * KD * KS_v
    Vr = round(phi_v * fv_d * Ib / 1.5 / 1000, 2)  # kN (rectangular section = 1.5×Avg shear)

    flexure_ok = Mr >= inp.Mf
    shear_ok   = Vr >= inp.Vf

    return {
        "code": "CSA O86-19",
        "section": f"{int(inp.width)}×{int(inp.depth)} mm",
        "species_grade": f"{inp.species} {inp.grade}",
        "design_values_MPa": {"fb": vals["fb"], "fv": vals["fv"], "E_MPa": vals["E"]},
        "factors": {"KD": KD, "KS_b": KS_b, "KZ_b": round(KZ_b,3)},
        "flexure": {
            "Mf_kNm": inp.Mf,
            "Mr_kNm": Mr,
            "S_mm3": int(S),
            "utilization_pct": round(inp.Mf / Mr * 100, 1) if Mr > 0 else 999,
            "flexure_status": "✓ SAFE" if flexure_ok else "✗ REVISE",
        },
        "shear": {
            "Vf_kN": inp.Vf,
            "Vr_kN": Vr,
            "utilization_pct": round(inp.Vf / Vr * 100, 1) if Vr > 0 else 999,
            "shear_status": "✓ SAFE" if shear_ok else "✗ REVISE",
        },
        "overall": "✓ SAFE" if flexure_ok and shear_ok else "✗ REVISE — see notes",
        "reference": "CSA O86-19 Cl.5",
        "proof": proof_block(
            "CSA O86:19",
            ["CSA O86 sawn timber member design", "CSA O86 modification factors"],
            ["csa_o86"],
            "Preliminary wood beam check. Verify species/grade stamp, service condition, duration, lateral support, notches, holes, and deflection.",
        ),
    }


class CSAWoodFastenerInput(BaseModel):
    fastener_type: str = "bolt"  # bolt, lag_screw, nail
    diameter: float = 12         # mm
    side_member_thickness: float = 38
    main_member_thickness: float = 89
    wood_specific_gravity: float = 0.42
    fastener_Fu: float = 400     # MPa
    n_fasteners: int = 4
    load_duration: str = "standard"
    service_condition: str = "dry"
    factored_load: float = 18    # kN


@router.post("/csa-wood-fastener")
def csa_wood_fastener(inp: CSAWoodFastenerInput):
    phi = 0.80
    KD = KD_FACTORS.get(inp.load_duration, 1.0)
    KS = 0.85 if inp.service_condition == "wet" else 1.0
    embed = 82 * inp.wood_specific_gravity  # MPa preliminary embedment basis
    d = inp.diameter
    t = min(inp.side_member_thickness, inp.main_member_thickness)
    type_factor = {"bolt": 1.0, "lag_screw": 0.85, "nail": 0.35}.get(inp.fastener_type, 1.0)
    bearing_mode = embed * d * t / 1000
    yielding_mode = 0.35 * d**2 * math.sqrt(inp.fastener_Fu * embed) / 1000
    resistance_each = phi * KD * KS * type_factor * min(bearing_mode, yielding_mode)
    group_resistance = resistance_each * inp.n_fasteners
    util = inp.factored_load / group_resistance if group_resistance > 0 else 999
    spacing_note = "Check end, edge, and spacing requirements separately"
    return {
        "code": "CSA O86-19",
        "fastener": f"{inp.n_fasteners} x {inp.fastener_type} {inp.diameter} mm",
        "single_fastener_resistance_kN": round(resistance_each, 2),
        "group_resistance_kN": round(group_resistance, 2),
        "demand_kN": inp.factored_load,
        "utilization_pct": round(util * 100, 1),
        "factors": {"KD": KD, "KS": KS, "type_factor": type_factor},
        "overall": "SAFE" if util <= 1 else "REVISE",
        "reference": "CSA O86-19 dowel-type fastener lateral resistance preliminary workflow",
        "assumptions": spacing_note,
        "proof": proof_block(
            "CSA O86:19",
            ["CSA O86 dowel-type fastener lateral resistance", "CSA O86 fastener spacing and detailing provisions"],
            ["csa_o86"],
            "Preliminary fastener resistance only. End distance, edge distance, row spacing, group effects, withdrawal, and moisture/service effects must be checked.",
        ),
    }


# ── NBC Load Combinations ─────────────────────────────────────────────────────

class LoadComboInput(BaseModel):
    D: float = 0.0   # kN/m dead load
    L: float = 0.0   # kN/m live load
    S: float = 0.0   # kN/m snow load
    W: float = 0.0   # kN/m wind load
    E: float = 0.0   # kN seismic

@router.post("/load-combinations")
def calc_load_combinations(inp: LoadComboInput):
    D, L, S, W, E = inp.D, inp.L, inp.S, inp.W, inp.E
    combos = [
        {"id":1, "desc":"1.4D",                     "value": round(1.4*D, 2)},
        {"id":2, "desc":"1.25D + 1.5L",             "value": round(1.25*D + 1.5*L, 2)},
        {"id":3, "desc":"1.25D + 1.5S + 0.5L",      "value": round(1.25*D + 1.5*S + 0.5*L, 2)},
        {"id":4, "desc":"1.25D + 1.4W + 0.5L",      "value": round(1.25*D + 1.4*W + 0.5*L, 2)},
        {"id":5, "desc":"0.9D + 1.4W",              "value": round(0.9*D + 1.4*W, 2)},
        {"id":6, "desc":"1.0D + 1.0E + 0.5L+0.25S", "value": round(1.0*D + 1.0*E + 0.5*L + 0.25*S, 2)},
        {"id":7, "desc":"1.25D + 1.5L + 0.5S",      "value": round(1.25*D + 1.5*L + 0.5*S, 2)},
    ]
    governing = max(combos, key=lambda x: x["value"])
    return {
        "combinations": combos,
        "governing": governing,
        "reference": "NBC 2020 Table 4.1.3.2",
        "proof": proof_block(
            "NBC 2020",
            ["NBC Division B Part 4, Table 4.1.3.2 load combinations"],
            ["nbc_2020"],
            "Load combinations are shown for common ultimate limit states. Verify the governing local edition, companion load rules, and serviceability combinations.",
        ),
    }
