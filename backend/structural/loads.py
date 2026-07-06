"""
Structural Load Calculator
IS 875 (Part 1) — Dead Loads
IS 875 (Part 2) — Live Loads
IS 875 (Part 3) — Wind Loads
IS 1893 (Part 1):2016 — Seismic Loads
All units: kN, m, kN/m²
"""
import math
from typing import Dict, List

# ── IS 875 Part 2 — Live Loads (kN/m²) ────────────────────────────────────────
LIVE_LOAD_TABLE = {
    "residential_rooms":      2.0,
    "residential_stairs":     3.0,
    "office_general":         2.5,
    "office_filing":          5.0,
    "commercial_retail":      4.0,
    "commercial_warehouse":   7.5,
    "assembly_fixed_seats":   3.0,
    "assembly_movable":       5.0,
    "hospital_wards":         2.0,
    "hospital_operation":     3.0,
    "educational_classroom":  3.0,
    "roof_access":            1.5,
    "roof_no_access":         0.75,
    "parking_light":          2.5,
    "parking_heavy":          5.0,
    "storage_general":        5.0,
    "industrial_light":       5.0,
    "industrial_heavy":       10.0,
}

# ── IS 875 Part 1 — Unit Weights (kN/m³) ──────────────────────────────────────
UNIT_WEIGHTS = {
    "concrete_rcc":           25.0,
    "concrete_pcc":           24.0,
    "steel":                  78.5,
    "brick_masonry":          19.2,
    "aac_block":               6.0,
    "fly_ash_brick":          18.0,
    "glass":                  26.5,
    "timber":                  8.0,
    "marble":                 26.5,
    "granite":                27.0,
    "ceramic_tiles":          19.2,
    "screed_mortar":          20.4,
    "plaster":                20.4,
    "soil_dry":               16.0,
    "soil_saturated":         20.0,
    "water":                   9.81,
}

# ── IS 875 Part 3 — Basic Wind Speed Vb (m/s) by city ─────────────────────────
WIND_SPEED_CITY = {
    "Mumbai":      44, "Delhi":       47, "Chennai":     50,
    "Kolkata":     50, "Bangalore":   33, "Ahmedabad":   39,
    "Hyderabad":   44, "Pune":        39, "Surat":       44,
    "Jaipur":      47, "Lucknow":     47, "Kanpur":      47,
    "Nagpur":      44, "Bhopal":      39, "Indore":      39,
    "Patna":       47, "Raipur":      39, "Bhubaneswar": 50,
    "Visakhapatnam":50,"Kochi":       39, "Coimbatore":  39,
    "Guwahati":    50, "Chandigarh":  47, "Amritsar":    47,
}

# Terrain category factor k2 (IS 875 Part 3 Table 2, height 10m)
K2_TERRAIN = {"1": 1.05, "2": 1.00, "3": 0.91, "4": 0.80}

# Topography factor k3
K3_TOPOGRAPHY = {"flat": 1.0, "gentle_slope": 1.036, "steep_hill": 1.073}

# Structure class importance factor k1
K1_RISK = {"A_temporary": 0.9, "B_general": 1.0, "C_important": 1.05, "D_critical": 1.1}

# ── IS 1893 (Part 1):2016 — Seismic Parameters ────────────────────────────────
SEISMIC_ZONE = {
    "II":  {"Z": 0.10, "description": "Low seismic zone"},
    "III": {"Z": 0.16, "description": "Moderate seismic zone"},
    "IV":  {"Z": 0.24, "description": "High seismic zone"},
    "V":   {"Z": 0.36, "description": "Very high seismic zone"},
}

CITY_SEISMIC_ZONE = {
    "Bangalore": "II",  "Coimbatore": "II",   "Chennai": "III",
    "Hyderabad": "II",  "Kochi": "III",        "Mumbai": "III",
    "Pune": "III",      "Ahmedabad": "III",    "Bhopal": "II",
    "Indore": "III",    "Nagpur": "II",        "Raipur": "II",
    "Bhubaneswar": "III","Kolkata": "III",      "Patna": "IV",
    "Delhi": "IV",      "Jaipur": "III",       "Lucknow": "III",
    "Kanpur": "III",    "Chandigarh": "IV",    "Amritsar": "IV",
    "Surat": "III",     "Guwahati": "V",       "Visakhapatnam": "III",
}

# Importance factor I (IS 1893 Table 8)
IMPORTANCE_FACTOR = {
    "residential":    1.0,
    "commercial":     1.0,
    "office":         1.0,
    "hospital":       1.5,
    "school":         1.5,
    "emergency":      1.5,
    "power_plant":    2.0,
}

# Soil type: Sa/g values (IS 1893 Figure 2, 5% damping)
def sa_g(soil_type: str, T: float) -> float:
    """Spectral acceleration coefficient Sa/g per IS 1893 (Part 1):2016 Fig 2."""
    if soil_type == "I":       # Rock or hard soil
        if T <= 0.10: return 1 + 15*T
        elif T <= 0.40: return 2.50
        elif T <= 4.00: return 1.00/T
        else: return 0.25
    elif soil_type == "II":    # Medium soil
        if T <= 0.10: return 1 + 15*T
        elif T <= 0.55: return 2.50
        elif T <= 4.00: return 1.375/T
        else: return 0.344
    else:                      # Soft soil (Type III)
        if T <= 0.10: return 1 + 15*T
        elif T <= 0.67: return 2.50
        elif T <= 4.00: return 1.675/T
        else: return 0.419


def calculate_dead_loads(
    slab_thickness_mm: float,
    floor_finish_kn_m2: float = 1.0,
    partition_kn_m2: float = 1.0,
    ceiling_kn_m2: float = 0.25,
    beam_width_mm: float = 0,
    beam_depth_mm: float = 0,
    wall_thickness_mm: float = 0,
    wall_height_m: float = 0,
    unit_weight_slab: float = 25.0
) -> Dict:
    """Calculate dead loads per unit area (kN/m²)."""
    slab_sw = (slab_thickness_mm / 1000) * unit_weight_slab
    total = slab_sw + floor_finish_kn_m2 + partition_kn_m2 + ceiling_kn_m2
    wall_load = 0.0
    if wall_thickness_mm > 0 and wall_height_m > 0:
        uw = UNIT_WEIGHTS["brick_masonry"]
        wall_load = (wall_thickness_mm / 1000) * wall_height_m * uw
    return {
        "slab_self_weight":  round(slab_sw, 3),
        "floor_finish":      round(floor_finish_kn_m2, 3),
        "partitions":        round(partition_kn_m2, 3),
        "ceiling_services":  round(ceiling_kn_m2, 3),
        "wall_load_kn_m":    round(wall_load, 3),
        "total_DL_kn_m2":    round(total, 3),
        "unit": "kN/m²"
    }


def calculate_wind_load(
    city: str,
    building_height_m: float,
    terrain_category: str = "2",
    structure_class: str = "B_general",
    topography: str = "flat",
    wall_cf: float = 0.8,
    internal_pressure: float = 0.2,
    custom_vb: float = None
) -> Dict:
    """
    Wind load per IS 875 (Part 3):2015.
    Returns design wind pressure pz (kN/m²).
    """
    Vb = custom_vb or WIND_SPEED_CITY.get(city, 47)
    k1 = K1_RISK.get(structure_class, 1.0)
    k3 = K3_TOPOGRAPHY.get(topography, 1.0)
    # k2: interpolate with height (simplified at 10m base, scale with sqrt(h/10))
    k2_base = K2_TERRAIN.get(terrain_category, 1.0)
    k2 = k2_base * (building_height_m / 10) ** 0.1 if building_height_m > 10 else k2_base

    Vz = Vb * k1 * k2 * k3         # Design wind speed (m/s)
    pz = 0.6 * Vz**2 / 1000        # Design wind pressure (kN/m²)
    Cpe = wall_cf
    Cpi = internal_pressure
    net_pressure = (Cpe + Cpi) * pz

    return {
        "basic_wind_speed_Vb":    Vb,
        "k1_risk_factor":         round(k1, 3),
        "k2_terrain_factor":      round(k2, 3),
        "k3_topography":          round(k3, 3),
        "design_wind_speed_Vz":   round(Vz, 2),
        "design_wind_pressure_pz":round(pz, 4),
        "net_wind_pressure":      round(net_pressure, 4),
        "unit": "kN/m²",
        "code": "IS 875 Part 3:2015"
    }


def calculate_seismic_load(
    city: str,
    total_seismic_weight_kn: float,
    building_height_m: float,
    num_floors: int,
    soil_type: str = "II",
    response_reduction: float = 5.0,
    building_use: str = "residential",
    damping_percent: float = 5.0,
    custom_zone: str = None
) -> Dict:
    """
    Seismic base shear per IS 1893 (Part 1):2016.
    VB = Ah * W
    Ah = (Z/2 * Sa/g) / (R/I)
    """
    zone = custom_zone or CITY_SEISMIC_ZONE.get(city, "III")
    Z = SEISMIC_ZONE[zone]["Z"]
    I = IMPORTANCE_FACTOR.get(building_use, 1.0)
    R = response_reduction

    # Fundamental natural period: Ta = 0.075 * h^0.75 (RC frame)
    Ta = 0.075 * (building_height_m ** 0.75)

    # Damping correction: multiply Sa/g by factor
    damp_factor = {2: 1.4, 5: 1.0, 10: 0.8, 15: 0.7, 20: 0.6}.get(int(damping_percent), 1.0)
    sag = sa_g(soil_type, Ta) * damp_factor

    Ah = (Z / 2) * sag / (R / I)
    Ah = max(Ah, Z / 2 / R)   # Minimum Ah = Z/(2R) as per IS 1893

    VB = Ah * total_seismic_weight_kn

    # Vertical distribution of seismic force (IS 1893 Cl. 7.7.1)
    # Qi = VB * (Wi * hi²) / Σ(Wj * hj²)
    floor_height = building_height_m / num_floors
    floors = []
    sum_wh2 = 0
    wi = total_seismic_weight_kn / num_floors
    for i in range(1, num_floors + 1):
        hi = floor_height * i
        sum_wh2 += wi * hi**2
    for i in range(1, num_floors + 1):
        hi = floor_height * i
        Qi = VB * (wi * hi**2) / sum_wh2
        floors.append({"floor": i, "height_m": round(hi, 2), "seismic_force_kn": round(Qi, 2)})

    return {
        "zone": zone,
        "zone_factor_Z":        Z,
        "importance_factor_I":  I,
        "response_reduction_R": R,
        "natural_period_Ta_s":  round(Ta, 3),
        "Sa_g":                 round(sag, 4),
        "Ah":                   round(Ah, 5),
        "base_shear_VB_kn":     round(VB, 2),
        "floor_distribution":   floors,
        "code": "IS 1893 Part 1:2016"
    }


def load_combination(DL: float, LL: float, WL: float = 0, EQ: float = 0) -> Dict:
    """
    IS 456:2000 + IS 1893 load combinations (factored).
    Returns governing factored load.
    """
    combos = {
        "1.5(DL+LL)":        round(1.5 * (DL + LL), 3),
        "1.2(DL+LL+WL)":     round(1.2 * (DL + LL + WL), 3),
        "1.2(DL+LL+EQ)":     round(1.2 * (DL + LL + EQ), 3),
        "1.5(DL+WL)":        round(1.5 * (DL + WL), 3),
        "1.5(DL+EQ)":        round(1.5 * (DL + EQ), 3),
        "0.9DL+1.5WL":       round(0.9 * DL + 1.5 * WL, 3),
        "0.9DL+1.5EQ":       round(0.9 * DL + 1.5 * EQ, 3),
    }
    governing = max(combos, key=lambda k: combos[k])
    return {
        "combinations": combos,
        "governing_combo": governing,
        "governing_load_kn_m2": combos[governing],
        "code": "IS 456:2000 + IS 1893:2016"
    }
