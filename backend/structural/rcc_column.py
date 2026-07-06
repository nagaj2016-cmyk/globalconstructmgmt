"""
RCC Column Design — IS 456:2000
Short axially loaded columns (Cl. 39.3)
Short columns with uniaxial bending (interaction diagram)
Slenderness, eccentricity, lateral ties per IS 456
"""
import math
from typing import Dict

CONCRETE_GRADES = {"M20": 20, "M25": 25, "M30": 30, "M35": 35, "M40": 40}
STEEL_GRADES    = {"Fe415": 415, "Fe500": 500, "Fe550": 550}

# Effective length factors (IS 456 Table 28)
EFF_LENGTH_FACTOR = {
    "both_fixed":       0.65,
    "one_fixed_pinned": 0.80,
    "both_pinned":      1.00,
    "one_fixed_free":   2.00,
    "one_pin_one_free": 1.20,
}


def check_slenderness(b_mm: float, D_mm: float, eff_len_mm: float) -> Dict:
    """IS 456 Cl. 25.1.2 — Slenderness classification."""
    lex_D = eff_len_mm / D_mm
    ley_b = eff_len_mm / b_mm
    is_short = lex_D <= 12 and ley_b <= 12
    return {
        "lex_D": round(lex_D, 2),
        "ley_b": round(ley_b, 2),
        "is_short_column": is_short,
        "classification": "Short Column" if is_short else "Slender Column (additional design needed)"
    }


def min_eccentricity(b_mm: float, D_mm: float, l_mm: float) -> Dict:
    """IS 456 Cl. 25.4 — Minimum eccentricity."""
    ex = max(l_mm / 500 + D_mm / 30, 20)
    ey = max(l_mm / 500 + b_mm / 30, 20)
    return {"ex_mm": round(ex, 1), "ey_mm": round(ey, 1)}


def design_column_axial(
    Pu_kN: float,
    height_m: float,
    b_mm: float = 300,
    D_mm: float = 300,
    fck: float = 25,
    fy: float = 415,
    end_condition: str = "both_fixed",
    cover_mm: float = 40,
    bar_dia_mm: float = 16,
) -> Dict:
    """
    Short axially loaded column design per IS 456 Cl. 39.3:
    Pu = 0.4·fck·Ac + 0.67·fy·Asc
    """
    Pu = Pu_kN * 1000  # N
    l  = height_m * 1000  # mm
    k  = EFF_LENGTH_FACTOR.get(end_condition, 0.65)
    le = k * l

    slender = check_slenderness(b_mm, D_mm, le)
    ecc     = min_eccentricity(b_mm, D_mm, l)

    Ag = b_mm * D_mm

    # Required Asc from: Pu = 0.4*fck*(Ag-Asc) + 0.67*fy*Asc
    Asc = (Pu - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck)

    # Min / Max steel (IS 456 Cl. 26.5.3)
    Asc_min = 0.008 * Ag   # 0.8%
    Asc_max = 0.060 * Ag   # 6% (during construction), 4% preferred
    Asc_pref = 0.04 * Ag   # 4% preferred

    warning = ""
    if Asc < 0:
        Asc = Asc_min
        warning = "Section adequate without steel; using minimum steel 0.8%"
    elif Asc > Asc_pref:
        warning = f"Steel > 4% ({round(100*Asc/Ag,2)}%). Consider increasing section."

    Asc = max(Asc, Asc_min)

    # Bar selection
    bar_area = math.pi * bar_dia_mm**2 / 4
    n_bars = math.ceil(Asc / bar_area)
    n_bars = max(n_bars, 4)   # IS 456 Cl. 26.5.3.1b: min 4 bars for rectangular
    n_bars = n_bars if n_bars % 2 == 0 else n_bars + 1  # Even number
    Asc_provided = n_bars * bar_area
    p_provided = 100 * Asc_provided / Ag

    # Actual capacity with provided steel
    Ac = Ag - Asc_provided
    Pu_actual = 0.4 * fck * Ac + 0.67 * fy * Asc_provided
    utilization = round(Pu * 100 / Pu_actual, 1)

    # ── Lateral ties (IS 456 Cl. 26.5.3.2) ───────────────────────────────────
    tie_dia = max(6, bar_dia_mm / 4)
    tie_dia = 6 if tie_dia <= 6 else 8 if tie_dia <= 8 else 10
    tie_spacing = min(
        min(b_mm, D_mm),        # Least lateral dimension
        16 * bar_dia_mm,         # 16× main bar dia
        300                      # 300 mm max
    )

    return {
        "input": {
            "Pu_kN":        Pu_kN,
            "height_m":     height_m,
            "fck_N_mm2":    fck,
            "fy_N_mm2":     fy,
            "end_condition": end_condition,
        },
        "section": {
            "b_mm":          b_mm,
            "D_mm":          D_mm,
            "Ag_mm2":        Ag,
        },
        "slenderness":        slender,
        "eccentricity":       ecc,
        "steel_design": {
            "Asc_required_mm2":  round(Asc, 1),
            "Asc_min_mm2":       round(Asc_min, 1),
            "Asc_max_mm2":       round(Asc_max, 1),
            "bars":              f"{n_bars} — #{int(bar_dia_mm)} (evenly distributed)",
            "Asc_provided_mm2":  round(Asc_provided, 1),
            "p_provided_percent": round(p_provided, 3),
        },
        "capacity": {
            "Pu_applied_kN":     Pu_kN,
            "Pu_capacity_kN":    round(Pu_actual / 1000, 2),
            "utilization_pct":   utilization,
            "adequate":          Pu_actual >= Pu,
        },
        "lateral_ties": {
            "tie_dia_mm":        tie_dia,
            "tie_spacing_mm":    int(tie_spacing),
            "spec":              f"#{tie_dia} @ {int(tie_spacing)} c/c",
        },
        "warning": warning,
        "code": "IS 456:2000 Cl. 39.3"
    }


def design_column_uniaxial(
    Pu_kN: float,
    Mu_kNm: float,
    height_m: float,
    b_mm: float = 300,
    D_mm: float = 400,
    fck: float = 25,
    fy: float = 415,
    end_condition: str = "both_fixed",
    cover_mm: float = 40,
    bar_dia_mm: float = 16,
) -> Dict:
    """
    Column with uniaxial bending — P-M interaction approach (IS 456 Cl. 39.6).
    Uses simplified SP-16 chart approach via non-dimensional parameters.
    """
    Pu = Pu_kN * 1000   # N
    Mu = Mu_kNm * 1e6   # N·mm
    Ag = b_mm * D_mm

    # Non-dimensional parameters for SP-16 chart
    Pu_fck_Ag = Pu / (fck * Ag)
    Mu_fck_Ag_D = Mu / (fck * Ag * D_mm)
    d_D = cover_mm / D_mm

    # Simplified: estimate pt from interaction using linear approx
    # (Full chart lookup not implemented — use lower bound estimate)
    # For design: pt = (Pu/(0.4*fck*Ag) + Mu/(0.4*fck*Ag*D_mm/2) - 1) * fck / fy * 100
    # Rough estimate using capacity equation with moment
    pt_est = max(
        (Pu_fck_Ag + 2 * Mu_fck_Ag_D - 0.4) / (0.67 * fy / fck - 0.4) * 100,
        0.8
    )
    pt_est = min(pt_est, 6.0)

    Asc_req = pt_est * Ag / 100
    bar_area = math.pi * bar_dia_mm**2 / 4
    n_bars = max(4, math.ceil(Asc_req / bar_area))
    n_bars = n_bars if n_bars % 2 == 0 else n_bars + 1
    Asc_provided = n_bars * bar_area
    p_provided = 100 * Asc_provided / Ag

    tie_spacing = min(min(b_mm, D_mm), 16 * bar_dia_mm, 300)

    return {
        "input": {
            "Pu_kN": Pu_kN, "Mu_kNm": Mu_kNm,
            "fck": fck, "fy": fy,
            "b_mm": b_mm, "D_mm": D_mm,
        },
        "sp16_params": {
            "Pu_fckAg":      round(Pu_fck_Ag, 4),
            "Mu_fckAgD":     round(Mu_fck_Ag_D, 4),
            "d_D_ratio":     round(d_D, 3),
        },
        "steel_design": {
            "pt_required_pct":   round(pt_est, 2),
            "Asc_required_mm2":  round(Asc_req, 1),
            "bars":              f"{n_bars} — #{int(bar_dia_mm)}",
            "Asc_provided_mm2":  round(Asc_provided, 1),
            "p_provided_pct":    round(p_provided, 3),
        },
        "lateral_ties": {
            "spec": f"#8 @ {int(tie_spacing)} c/c",
            "spacing_mm": int(tie_spacing),
        },
        "note": "Verify against IS SP-16 interaction charts for final design.",
        "code": "IS 456:2000 Cl. 39.6"
    }
