"""
RCC Beam Design — IS 456:2000
Singly / Doubly reinforced rectangular beams
Shear design per IS 456 Cl. 40
Deflection check per IS 456 Cl. 23.2
Units: N, mm throughout (converted from kN, m at input)
"""
import math
from typing import Dict, Optional

# ── Material constants ─────────────────────────────────────────────────────────
CONCRETE_GRADES = {
    "M15": 15, "M20": 20, "M25": 25, "M30": 30,
    "M35": 35, "M40": 40, "M45": 45, "M50": 50,
}
STEEL_GRADES = {
    "Fe250": {"fy": 250, "xu_d": 0.531, "Es": 200000},
    "Fe415": {"fy": 415, "xu_d": 0.479, "Es": 200000},
    "Fe500": {"fy": 500, "xu_d": 0.456, "Es": 200000},
    "Fe550": {"fy": 550, "xu_d": 0.444, "Es": 200000},
}

# IS 456 Table 19 — Design shear strength τc (N/mm²) for M20
# Key: (pt_rounded_to_0.25, fck)
# Simplified: τc = 0.85 * sqrt(0.8*fck) * (sqrt(1 + 5β) - 1) / (6β)
def shear_capacity_tc(pt: float, fck: float) -> float:
    """IS 456 Table 19: Design shear strength of concrete (N/mm²)."""
    if pt < 0.15: pt = 0.15
    if pt > 3.0: pt = 3.0
    β = max(0.8 * fck / (6.89 * pt), 1.0)
    τc = 0.85 * math.sqrt(0.8 * fck) * (math.sqrt(1 + 5 * β) - 1) / (6 * β)
    return round(τc, 3)

# IS 456 Table 20 — Max shear stress τc_max
def shear_max_tc(fck: float) -> float:
    if fck <= 20: return 2.8
    elif fck <= 25: return 3.1
    elif fck <= 30: return 3.5
    elif fck <= 35: return 3.7
    elif fck <= 40: return 4.0
    else: return 4.0


def design_beam(
    span_m: float,
    Mu_kNm: float,
    Vu_kN: float,
    beam_type: str = "simply_supported",  # or "cantilever" or "continuous"
    b_mm: float = 230,
    D_mm: float = None,        # If None, will be estimated
    fck: float = 25,           # N/mm²
    fy: float = 415,           # N/mm²
    cover_mm: float = 25,
    stirrup_dia_mm: float = 8,
    main_bar_dia_mm: float = 16,
    d_prime_mm: float = 50,    # effective cover to compression steel
) -> Dict:
    """
    Complete RCC beam design per IS 456:2000.
    Returns all design details, steel areas, stirrup spacing.
    """
    Mu = Mu_kNm * 1e6         # N·mm
    Vu = Vu_kN * 1e3          # N
    span = span_m * 1000       # mm

    steel = STEEL_GRADES.get(f"Fe{int(fy)}", STEEL_GRADES["Fe415"])
    xu_d_lim = steel["xu_d"]

    # ── Effective depth ────────────────────────────────────────────────────────
    if D_mm is None:
        # Span/depth ratio heuristic (IS 456 Cl. 23.2 for modification)
        span_d_ratio = {"simply_supported": 20, "cantilever": 7, "continuous": 26}
        d_min = span / span_d_ratio.get(beam_type, 20)
        D_mm = math.ceil((d_min + cover_mm + stirrup_dia_mm + main_bar_dia_mm / 2) / 25) * 25
    d = D_mm - cover_mm - stirrup_dia_mm - main_bar_dia_mm / 2

    # ── Limiting moment ────────────────────────────────────────────────────────
    Mu_lim = 0.36 * xu_d_lim * (1 - 0.42 * xu_d_lim) * b_mm * d**2 * fck / 1e6  # kN·m

    singly = Mu_kNm <= Mu_lim
    doubly_reinforced = not singly

    # ── Tension steel (Ast) ────────────────────────────────────────────────────
    if singly:
        discriminant = 1 - (4.6 * Mu) / (fck * b_mm * d**2)
        if discriminant < 0:
            discriminant = 0
        Ast = (0.5 * fck / fy) * b_mm * d * (1 - math.sqrt(discriminant))
        Asc = 0.0
        design_type = "Singly Reinforced"
    else:
        # Limiting Ast
        Ast_lim = (0.5 * fck / fy) * b_mm * d * (1 - math.sqrt(1 - (4.6 * Mu_lim * 1e6) / (fck * b_mm * d**2)))
        Mu2 = (Mu_kNm - Mu_lim) * 1e6   # N·mm
        fsc = min(0.87 * fy, 353)        # Simplified: stress in comp steel ≈ 0.87fy (IS SP-16)
        Asc = Mu2 / ((fsc - 0.446 * fck) * (d - d_prime_mm))
        Ast2 = Mu2 / (0.87 * fy * (d - d_prime_mm))
        Ast = Ast_lim + Ast2
        design_type = "Doubly Reinforced"

    # ── Min / Max steel checks ─────────────────────────────────────────────────
    Ast_min = 0.85 * b_mm * d / fy
    Ast_max = 0.04 * b_mm * D_mm
    Ast = max(Ast, Ast_min)
    Ast = min(Ast, Ast_max)

    # ── Bar selection ──────────────────────────────────────────────────────────
    def bars_needed(area, dia):
        bar_area = math.pi * dia**2 / 4
        return math.ceil(area / bar_area), round(bar_area, 1)

    n_main, a_bar = bars_needed(Ast, main_bar_dia_mm)
    Ast_provided = n_main * a_bar
    pt_provided = 100 * Ast_provided / (b_mm * d)

    n_comp, a_comp_bar = bars_needed(Asc, main_bar_dia_mm) if doubly_reinforced else (0, 0)
    Asc_provided = n_comp * a_comp_bar

    # ── Shear design ───────────────────────────────────────────────────────────
    τv = Vu / (b_mm * d)                    # N/mm²
    τc = shear_capacity_tc(pt_provided, fck)
    τc_max = shear_max_tc(fck)

    if τv > τc_max:
        shear_warning = "INCREASE BEAM SIZE — τv exceeds τc_max"
    else:
        shear_warning = ""

    if τv > τc:
        Vus = (τv - τc) * b_mm * d          # N (shear carried by stirrups)
        Asv = math.pi * stirrup_dia_mm**2 / 4 * 2   # 2-legged stirrup
        sv = round(0.87 * fy * Asv * d / Vus, 0)
        sv_min = round(0.87 * fy * Asv / (0.4 * b_mm), 0)  # IS 456 Cl. 26.5.1.6
        sv_provide = min(sv, 300)           # Max spacing = 0.75d or 300mm
        sv_provide = max(sv_provide, 75)    # Min practical spacing
        shear_mode = "Stirrups required"
    else:
        sv_provide = round(0.75 * d)        # Nominal stirrups
        sv_provide = min(sv_provide, 300)
        Asv = math.pi * stirrup_dia_mm**2 / 4 * 2
        shear_mode = "Nominal stirrups (IS 456 Cl. 26.5.1.6)"

    # ── Deflection check (basic span/d check) ─────────────────────────────────
    basic_ratio = {"simply_supported": 20, "cantilever": 7, "continuous": 26}
    br = basic_ratio.get(beam_type, 20)
    fs = 0.58 * fy * Ast / Ast_provided    # Service stress in steel
    kt = 1.0                                # Simplified (no full modification)
    permitted_d = span / (br * kt)
    deflection_ok = d >= permitted_d

    # ── Development length ─────────────────────────────────────────────────────
    # IS 456 Cl. 26.2.1: Ld = φ * σs / (4 * τbd)
    # τbd for M20: 1.2 N/mm², M25: 1.4, M30: 1.5 (IS 456 Table 5, × 1.6 for deformed bars)
    τbd_base = {15: 1.0, 20: 1.2, 25: 1.4, 30: 1.5, 35: 1.7, 40: 1.9}.get(int(fck), 1.4)
    τbd = τbd_base * 1.6                    # Deformed bars
    Ld = round(main_bar_dia_mm * 0.87 * fy / (4 * τbd), 0)

    return {
        "design_type":          design_type,
        "beam_type":            beam_type,
        "input": {
            "span_m":           span_m,
            "Mu_kNm":           Mu_kNm,
            "Vu_kN":            Vu_kN,
            "fck_N_mm2":        fck,
            "fy_N_mm2":         fy,
        },
        "section": {
            "b_mm":             b_mm,
            "D_mm":             D_mm,
            "d_mm":             round(d, 1),
            "cover_mm":         cover_mm,
        },
        "moment_capacity": {
            "Mu_lim_kNm":       round(Mu_lim, 2),
            "applied_Mu_kNm":   Mu_kNm,
            "is_singly":        singly,
        },
        "tension_steel": {
            "Ast_required_mm2": round(Ast, 1),
            "Ast_min_mm2":      round(Ast_min, 1),
            "bars":             f"{n_main} — #{int(main_bar_dia_mm)}",
            "Ast_provided_mm2": Ast_provided,
            "pt_percent":       round(pt_provided, 3),
        },
        "compression_steel": {
            "required":         doubly_reinforced,
            "Asc_mm2":          round(Asc, 1) if doubly_reinforced else 0,
            "bars":             f"{n_comp} — #{int(main_bar_dia_mm)}" if doubly_reinforced else "None",
        },
        "shear_design": {
            "τv_N_mm2":         round(τv, 3),
            "τc_N_mm2":         round(τc, 3),
            "τc_max_N_mm2":     τc_max,
            "mode":             shear_mode,
            "stirrups":         f"2L — #{int(stirrup_dia_mm)} @ {int(sv_provide)} c/c",
            "stirrup_spacing_mm": int(sv_provide),
            "warning":          shear_warning,
        },
        "deflection": {
            "basic_span_d_ratio": br,
            "d_provided_mm":    round(d, 1),
            "d_required_mm":    round(permitted_d, 1),
            "ok":               deflection_ok,
        },
        "development_length": {
            "Ld_mm":            int(Ld),
            "bar_dia_mm":       main_bar_dia_mm,
        },
        "code": "IS 456:2000",
        "warnings": [shear_warning] if shear_warning else []
    }
