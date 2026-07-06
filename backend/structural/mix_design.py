"""
Concrete Mix Design — IS 10262:2019
Method of concrete mix design as per latest BIS code
All values per IS 10262:2019 tables
"""
import math
from typing import Dict

# ── Standard deviation (IS 10262:2019 Table 1) ────────────────────────────────
STD_DEVIATION = {
    "M10": 3.5, "M15": 3.5, "M20": 4.0,
    "M25": 4.0, "M30": 5.0, "M35": 5.0,
    "M40": 6.0, "M45": 6.0, "M50": 6.0,
}

# ── Max W/C ratio (IS 456:2000 Table 5 — exposure conditions) ─────────────────
MAX_WC_RATIO = {
    "mild":         0.55,
    "moderate":     0.50,
    "severe":       0.45,
    "very_severe":  0.45,
    "extreme":      0.40,
}

# ── Min cement content kg/m³ (IS 456 Table 5) ─────────────────────────────────
MIN_CEMENT = {
    "mild":         300,
    "moderate":     300,
    "severe":       320,
    "very_severe":  340,
    "extreme":      360,
}

# ── Water content (IS 10262:2019 Table 2) — for 20mm nominal max aggregate ────
# Slump 25–50mm, 20mm aggregate → 186 kg/m³
# Adjustments: +3% for 10mm agg, -3% for 40mm agg
# +6 kg for every 25mm increase in slump beyond 50mm
BASE_WATER_CONTENT = {10: 208, 20: 186, 40: 165}   # for slump 25-50mm

# ── Volume of coarse aggregate per unit volume of concrete (IS 10262 Table 3) ─
# Keys: (zone, W/C ratio, nominal agg size)
# Zone of fine aggregate: I (coarse) to IV (fine)
# Values: volume of dry-rodded coarse aggregate per m³ of concrete
COARSE_AGG_VOLUME = {
    ("I",  0.40): 0.78, ("I",  0.45): 0.77, ("I",  0.50): 0.76, ("I",  0.55): 0.75,
    ("II", 0.40): 0.76, ("II", 0.45): 0.75, ("II", 0.50): 0.74, ("II", 0.55): 0.73,
    ("III",0.40): 0.74, ("III",0.45): 0.73, ("III",0.50): 0.72, ("III",0.55): 0.71,
    ("IV", 0.40): 0.72, ("IV", 0.45): 0.71, ("IV", 0.50): 0.70, ("IV", 0.55): 0.69,
}

def get_coarse_agg_volume(fa_zone: str, wc: float, agg_size: int) -> float:
    """Lookup + interpolate coarse aggregate volume from IS 10262 Table 3."""
    wc_rounded = round(round(wc / 0.05) * 0.05, 2)
    wc_rounded = max(0.40, min(wc_rounded, 0.55))
    vol = COARSE_AGG_VOLUME.get((fa_zone, wc_rounded), 0.73)
    # Adjustment for aggregate size (IS 10262 Table 3 footnote)
    if agg_size == 10:
        vol -= 0.03
    elif agg_size == 40:
        vol += 0.03
    return round(vol, 3)


def design_mix(
    grade: str = "M25",
    exposure: str = "moderate",
    nominal_agg_size_mm: int = 20,    # 10, 20, or 40 mm
    fa_zone: str = "II",              # IS 383 zone: I, II, III, IV
    slump_mm: int = 75,               # Target workability
    cement_sg: float = 3.15,          # Specific gravity of cement (OPC)
    fa_sg: float = 2.65,              # Specific gravity of fine aggregate
    ca_sg: float = 2.70,              # Specific gravity of coarse aggregate
    admixture_percent: float = 0.0,   # % by weight of cement
    flyash_percent: float = 0.0,      # % fly ash (mineral admixture)
    air_percent: float = 1.0,         # Entrapped air %
) -> Dict:
    """
    IS 10262:2019 mix design procedure.
    Returns mix proportions by mass and volume.
    """
    fck = int(grade.replace("M", ""))
    s = STD_DEVIATION.get(grade, 5.0)

    # ── Step 1: Target mean compressive strength ──────────────────────────────
    f_target = fck + 1.65 * s   # N/mm²

    # ── Step 2: W/C ratio ─────────────────────────────────────────────────────
    # From IS 10262 Fig 1 (relationship between strength and W/C)
    # Approximate: f'c = 49.7 - 32.4 * W/C (Abrams' calibrated for Indian materials)
    wc_calc = (49.7 - f_target) / 32.4
    wc_max = MAX_WC_RATIO.get(exposure, 0.50)
    wc = min(wc_calc, wc_max)
    wc = max(wc, 0.30)   # Practical minimum

    # ── Step 3: Water content ─────────────────────────────────────────────────
    base_water = BASE_WATER_CONTENT.get(nominal_agg_size_mm, 186)
    # Slump adjustment: +6 kg per 25mm above 50mm
    slump_extra = max(0, (slump_mm - 50) / 25 * 6)
    water_content = base_water + slump_extra
    # Admixture water reduction (typical SP gives 20% reduction)
    if admixture_percent > 0:
        water_content *= 0.80
    water_content = round(water_content, 1)

    # ── Step 4: Cement content ────────────────────────────────────────────────
    cement_content = water_content / wc
    cement_min = MIN_CEMENT.get(exposure, 300)
    if cement_content < cement_min:
        cement_content = cement_min
        wc = water_content / cement_content   # Recalculate actual W/C
    # Max cement limit (IS 456 Cl. 8.2.4.2)
    cement_content = min(cement_content, 450)

    # Fly ash replacement
    if flyash_percent > 0:
        flyash_mass = cement_content * flyash_percent / 100
        cement_mass = cement_content - flyash_mass
    else:
        flyash_mass = 0
        cement_mass = cement_content

    # ── Step 5: Coarse aggregate volume ───────────────────────────────────────
    vol_ca_bulk = get_coarse_agg_volume(fa_zone, wc, nominal_agg_size_mm)
    # Bulk density of CA assumed 1600 kg/m³
    ca_bulk_density = 1600   # kg/m³
    ca_mass_loose = vol_ca_bulk * ca_bulk_density   # kg/m³ of concrete (loose)
    # Convert to absolute volume
    vol_ca_abs = ca_mass_loose / (ca_sg * 1000)

    # ── Step 6: Fine aggregate ────────────────────────────────────────────────
    vol_cement = cement_content / (cement_sg * 1000)
    vol_flyash = flyash_mass / (2.2 * 1000)   # SG of fly ash ≈ 2.2
    vol_water = water_content / 1000
    vol_air = air_percent / 100

    vol_fa = 1.0 - (vol_cement + vol_flyash + vol_water + vol_ca_abs + vol_air)
    fa_mass = vol_fa * fa_sg * 1000

    # ── Proportions ────────────────────────────────────────────────────────────
    ratio_c = 1
    ratio_fa = round(fa_mass / cement_content, 2)
    ratio_ca = round(ca_mass_loose / cement_content, 2)

    # ── Yield (volume of concrete per batch) ─────────────────────────────────
    total_vol = vol_cement + vol_flyash + vol_water + vol_ca_abs + vol_fa + vol_air

    # ── Material per m³ of concrete ──────────────────────────────────────────
    scale = 1.0 / total_vol   # Scale to 1 m³
    cement_per_m3   = round(cement_mass * scale, 1)
    flyash_per_m3   = round(flyash_mass * scale, 1)
    water_per_m3    = round(water_content * scale, 1)
    fa_per_m3       = round(fa_mass * scale, 1)
    ca_per_m3       = round(ca_mass_loose * scale, 1)

    # ── Trial mix for 50L ────────────────────────────────────────────────────
    trial = 0.050   # m³
    return {
        "grade": grade,
        "target_strength_N_mm2": round(f_target, 2),
        "exposure": exposure,
        "input": {
            "nominal_aggregate_mm": nominal_agg_size_mm,
            "fa_zone": fa_zone,
            "slump_mm": slump_mm,
            "admixture_pct": admixture_percent,
            "flyash_pct": flyash_percent,
            "air_content_pct": air_percent,
        },
        "design_parameters": {
            "wc_ratio":          round(wc, 3),
            "water_content_kg_m3": water_content,
            "cement_content_kg_m3": round(cement_content, 1),
        },
        "mix_proportions_per_m3": {
            "cement_kg":         cement_per_m3,
            "fly_ash_kg":        flyash_per_m3,
            "water_kg":          water_per_m3,
            "fine_aggregate_kg": fa_per_m3,
            "coarse_aggregate_kg": ca_per_m3,
            "total_mass_kg":     round(cement_per_m3 + flyash_per_m3 + water_per_m3 + fa_per_m3 + ca_per_m3, 1),
        },
        "mix_ratio": {
            "C:FA:CA":           f"1 : {ratio_fa} : {ratio_ca}",
            "water_cement_ratio": round(wc, 3),
        },
        "trial_mix_50L": {
            "cement_kg":         round(cement_per_m3 * trial, 2),
            "fly_ash_kg":        round(flyash_per_m3 * trial, 2),
            "water_kg":          round(water_per_m3 * trial, 2),
            "fine_aggregate_kg": round(fa_per_m3 * trial, 2),
            "coarse_aggregate_kg": round(ca_per_m3 * trial, 2),
        },
        "compliance_checks": {
            "wc_max":            wc_max,
            "wc_ok":             wc <= wc_max,
            "cement_min_kg_m3":  cement_min,
            "cement_ok":         cement_per_m3 >= cement_min,
            "cement_max_ok":     cement_per_m3 <= 450,
        },
        "code": "IS 10262:2019"
    }
