"""
RCC Slab Design — IS 456:2000
One-way and two-way slabs
Moment coefficients per IS 456 Tables 12 & 26
"""
import math
from typing import Dict, List, Tuple

# IS 456 Table 26 — Bending moment coefficients for two-way slabs
# αx and αy for simply supported (SS) and continuous edges (various cases)
# Key: (case, ly_lx_ratio) → (αx, αy)
# ly/lx ratios: 1.0 to 2.0 in steps of 0.1
# Case 1: All four edges discontinuous (SS on all)
# Case 2: Two short edges discontinuous
# Case 3: Two long edges discontinuous
# Case 4: One long edge continuous
# etc.
# Simplified: using Case 2 (two short edges disc.) — common for interior panels

TWO_WAY_SLAB_COEFF = {
    # ly/lx: (αx_neg, αx_pos, αy_neg, αy_pos) — negative at continuous, positive at midspan
    # From IS 456 Table 26, Case 2 (two short edges discontinuous)
    1.0: (0.037, 0.028, 0.037, 0.028),
    1.1: (0.043, 0.032, 0.039, 0.030),
    1.2: (0.048, 0.036, 0.041, 0.031),
    1.3: (0.057, 0.043, 0.044, 0.033),
    1.4: (0.062, 0.047, 0.046, 0.035),
    1.5: (0.067, 0.050, 0.048, 0.036),
    1.6: (0.071, 0.054, 0.050, 0.037),
    1.7: (0.075, 0.057, 0.051, 0.038),
    1.8: (0.079, 0.059, 0.053, 0.040),
    1.9: (0.082, 0.062, 0.054, 0.040),
    2.0: (0.084, 0.063, 0.056, 0.042),
}

def get_two_way_coeff(ly_lx: float) -> Tuple[float, float, float, float]:
    """Interpolate IS 456 Table 26 coefficients for given ly/lx ratio."""
    ly_lx = max(1.0, min(ly_lx, 2.0))
    low = round(math.floor(ly_lx * 10) / 10, 1)
    high = round(math.ceil(ly_lx * 10) / 10, 1)
    if low == high or low not in TWO_WAY_SLAB_COEFF:
        return TWO_WAY_SLAB_COEFF.get(low, TWO_WAY_SLAB_COEFF[1.0])
    c_low = TWO_WAY_SLAB_COEFF[low]
    c_high = TWO_WAY_SLAB_COEFF.get(high, c_low)
    t = (ly_lx - low) / (high - low) if high != low else 0
    return tuple(c_low[i] + t * (c_high[i] - c_low[i]) for i in range(4))


def design_one_way_slab(
    span_m: float,
    total_load_kN_m2: float,     # DL + LL (unfactored)
    fck: float = 25,
    fy: float = 415,
    support: str = "simply_supported",  # or "continuous" or "cantilever"
    cover_mm: float = 20,
    main_bar_dia_mm: float = 10,
    dist_bar_dia_mm: float = 8,
    slab_type: str = "floor",    # or "roof"
) -> Dict:
    """
    One-way slab design per IS 456:2000.
    Effective span, depth, Ast — full design.
    """
    lx = span_m * 1000  # mm

    # ── Depth from span/d ratio (IS 456 Cl. 23.2.1) ───────────────────────────
    basic_ratio = {"simply_supported": 20, "continuous": 26, "cantilever": 7}
    br = basic_ratio.get(support, 20)
    d_min = lx / br
    D = math.ceil((d_min + cover_mm + main_bar_dia_mm / 2) / 25) * 25
    d = D - cover_mm - main_bar_dia_mm / 2

    # ── Factored load ─────────────────────────────────────────────────────────
    wu = 1.5 * total_load_kN_m2   # kN/m² (UDL)
    wu_self = 1.5 * (D / 1000) * 25   # self-weight

    # ── Bending moment (per m width) ─────────────────────────────────────────
    wu_total = wu + wu_self
    if support == "simply_supported":
        Mu_pos = wu_total * span_m**2 / 8   # kN·m/m
        Mu_neg = 0.0
    elif support == "continuous":
        Mu_neg = wu_total * span_m**2 / 12
        Mu_pos = wu_total * span_m**2 / 16
    elif support == "cantilever":
        Mu_pos = 0.0
        Mu_neg = wu_total * span_m**2 / 2
    else:
        Mu_pos = wu_total * span_m**2 / 8
        Mu_neg = 0.0

    Mu = max(Mu_pos, Mu_neg) * 1e6   # N·mm per m width (b=1000mm)

    # ── Tension steel (Ast) ────────────────────────────────────────────────────
    b = 1000   # mm (per m width)
    xu_d_lim = 0.479 if fy == 415 else 0.456  # Fe415 / Fe500
    Mu_lim = 0.36 * xu_d_lim * (1 - 0.42 * xu_d_lim) * b * d**2 * fck / 1e6  # kN·m
    disc = max(0, 1 - (4.6 * Mu) / (fck * b * d**2))
    Ast = (0.5 * fck / fy) * b * d * (1 - math.sqrt(disc))

    # Min steel IS 456 Cl. 26.5.2.1
    if fy == 415 or fy == 500:
        Ast_min = 0.0012 * b * D   # 0.12% for HYSD
    else:
        Ast_min = 0.0015 * b * D   # 0.15% for mild steel
    Ast = max(Ast, Ast_min)

    # Bar spacing
    bar_area = math.pi * main_bar_dia_mm**2 / 4
    spacing = math.floor(bar_area / Ast * 1000)
    spacing = min(spacing, min(3*D, 300))   # IS 456 Cl. 26.3.3b
    spacing = max(spacing, 75)
    Ast_provided = bar_area / spacing * 1000

    # ── Distribution steel ────────────────────────────────────────────────────
    Ast_dist = 0.0012 * b * D if fy >= 415 else 0.0015 * b * D
    dist_bar_area = math.pi * dist_bar_dia_mm**2 / 4
    dist_spacing = math.floor(dist_bar_area / Ast_dist * 1000)
    dist_spacing = min(dist_spacing, min(5*D, 450))
    dist_spacing = max(dist_spacing, 75)

    # ── Shear check (IS 456 Cl. 40.2) ────────────────────────────────────────
    Vu = wu_total * span_m / 2 * 1000   # N/m
    tv = Vu / (b * d)
    # τc from table for pt
    pt = 100 * Ast_provided / (b * d)
    beta = max(0.8 * fck / (6.89 * pt), 1.0)
    tc = 0.85 * math.sqrt(0.8 * fck) * (math.sqrt(1 + 5 * beta) - 1) / (6 * beta)
    k = max(1.0, min(1.3 - 0.1 * D / 100, 1.3))  # depth factor IS 456 Cl. 40.2.1.1
    tc_k = tc * k
    shear_ok = tv <= tc_k

    return {
        "slab_type":        "One-way slab",
        "support":          support,
        "input": {
            "span_m":           span_m,
            "total_load_kN_m2": total_load_kN_m2,
            "fck":              fck,
            "fy":               fy,
        },
        "section": {
            "D_mm":             D,
            "d_mm":             round(d, 1),
            "cover_mm":         cover_mm,
        },
        "loads": {
            "factored_UDL_kN_m2":   round(wu_total, 3),
            "Mu_pos_kNm_per_m":     round(Mu_pos, 3),
            "Mu_neg_kNm_per_m":     round(Mu_neg, 3),
        },
        "main_steel": {
            "Ast_required_mm2_m":   round(Ast, 1),
            "Ast_min_mm2_m":        round(Ast_min, 1),
            "bar_dia_mm":           main_bar_dia_mm,
            "spacing_mm":           spacing,
            "Ast_provided_mm2_m":   round(Ast_provided, 1),
            "pt_percent":           round(pt, 3),
            "spec":                 f"#{main_bar_dia_mm} @ {spacing} c/c",
        },
        "distribution_steel": {
            "Ast_dist_mm2_m":       round(Ast_dist, 1),
            "bar_dia_mm":           dist_bar_dia_mm,
            "spacing_mm":           dist_spacing,
            "spec":                 f"#{dist_bar_dia_mm} @ {dist_spacing} c/c",
        },
        "shear": {
            "τv_N_mm2":            round(tv, 3),
            "τc_k_N_mm2":          round(tc_k, 3),
            "shear_ok":            shear_ok,
            "note":                "" if shear_ok else "Increase depth — shear exceeds capacity",
        },
        "code": "IS 456:2000"
    }


def design_two_way_slab(
    lx_m: float,        # Shorter span
    ly_m: float,        # Longer span
    total_load_kN_m2: float,
    fck: float = 25,
    fy: float = 415,
    cover_mm: float = 20,
    main_bar_dia_mm: float = 10,
) -> Dict:
    """
    Two-way slab design per IS 456:2000 Cl. D-1.
    Moment coefficients from IS 456 Table 26.
    """
    lx = lx_m * 1000
    ly = ly_m * 1000
    ly_lx = ly_m / lx_m

    # Check: one-way if ly/lx > 2
    one_way_governs = ly_lx > 2.0

    # Depth from span/depth ratio (shorter span governs)
    br = 26   # Continuous (conservative)
    d_min = lx / br
    D = math.ceil((d_min + cover_mm + main_bar_dia_mm / 2) / 25) * 25
    d = D - cover_mm - main_bar_dia_mm / 2

    # Factored load
    wu_self = 1.5 * (D / 1000) * 25
    wu = 1.5 * total_load_kN_m2 + wu_self   # kN/m²

    # Moment coefficients (IS 456 Table 26)
    coeffs = get_two_way_coeff(min(ly_lx, 2.0))
    ax_neg, ax_pos, ay_neg, ay_pos = coeffs

    Mx_pos = ax_pos * wu * lx_m**2   # kN·m/m (short span, positive)
    Mx_neg = ax_neg * wu * lx_m**2   # kN·m/m (short span, negative)
    My_pos = ay_pos * wu * lx_m**2   # kN·m/m (long span, positive)
    My_neg = ay_neg * wu * lx_m**2   # kN·m/m (long span, negative)

    def calc_ast(Mu_kNm: float, d_eff: float) -> Tuple[float, float, int, float]:
        Mu_Nmm = Mu_kNm * 1e6
        b = 1000
        disc = max(0, 1 - (4.6 * Mu_Nmm) / (fck * b * d_eff**2))
        Ast = (0.5 * fck / fy) * b * d_eff * (1 - math.sqrt(disc))
        Ast_min = 0.0012 * b * D
        Ast = max(Ast, Ast_min)
        ba = math.pi * main_bar_dia_mm**2 / 4
        sp = min(math.floor(ba / Ast * 1000), min(3*D, 300))
        sp = max(sp, 75)
        Ast_prov = ba / sp * 1000
        return Ast, Ast_min, sp, Ast_prov

    # Shorter span steel (d)
    ax_pos_Ast, ax_min, sx_pos_sp, sx_pos_prov = calc_ast(Mx_pos, d)
    ax_neg_Ast, _,     sx_neg_sp, sx_neg_prov = calc_ast(Mx_neg, d)

    # Longer span steel (d - dia of shorter span bar)
    dy = d - main_bar_dia_mm
    ay_pos_Ast, ay_min, sy_pos_sp, sy_pos_prov = calc_ast(My_pos, dy)
    ay_neg_Ast, _,     sy_neg_sp, sy_neg_prov = calc_ast(My_neg, dy)

    return {
        "slab_type":    "Two-way slab",
        "one_way_governs": one_way_governs,
        "note": "Use one-way design if ly/lx > 2.0" if one_way_governs else "",
        "input": {
            "lx_m":             lx_m,
            "ly_m":             ly_m,
            "ly_lx_ratio":      round(ly_lx, 3),
            "total_load_kN_m2": total_load_kN_m2,
            "fck":              fck, "fy": fy,
        },
        "section": {
            "D_mm":     D,
            "d_mm":     round(d, 1),
            "dy_mm":    round(dy, 1),
            "cover_mm": cover_mm,
        },
        "moment_coefficients": {
            "αx_pos": round(ax_pos, 4),
            "αx_neg": round(ax_neg, 4),
            "αy_pos": round(ay_pos, 4),
            "αy_neg": round(ay_neg, 4),
            "table":  "IS 456 Table 26, Case 2 (two short edges discontinuous)"
        },
        "moments_kNm_m": {
            "Mx_positive": round(Mx_pos, 3),
            "Mx_negative": round(Mx_neg, 3),
            "My_positive": round(My_pos, 3),
            "My_negative": round(My_neg, 3),
        },
        "short_span_steel": {
            "positive":  {"Ast_mm2_m": round(ax_pos_Ast,1), "spacing_mm": sx_pos_sp, "spec": f"#{main_bar_dia_mm} @ {sx_pos_sp} c/c"},
            "negative":  {"Ast_mm2_m": round(ax_neg_Ast,1), "spacing_mm": sx_neg_sp, "spec": f"#{main_bar_dia_mm} @ {sx_neg_sp} c/c"},
        },
        "long_span_steel": {
            "positive":  {"Ast_mm2_m": round(ay_pos_Ast,1), "spacing_mm": sy_pos_sp, "spec": f"#{main_bar_dia_mm} @ {sy_pos_sp} c/c"},
            "negative":  {"Ast_mm2_m": round(ay_neg_Ast,1), "spacing_mm": sy_neg_sp, "spec": f"#{main_bar_dia_mm} @ {sy_neg_sp} c/c"},
        },
        "factored_load_kN_m2": round(wu, 3),
        "code": "IS 456:2000 Cl. D-1"
    }
