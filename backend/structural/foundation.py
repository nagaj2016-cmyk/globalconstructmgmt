"""
Isolated Footing Design — IS 456:2000
Pad / spread footing under single column
Includes: size, depth, one-way & two-way shear, steel
"""
import math
from typing import Dict


def design_isolated_footing(
    Pu_kN: float,           # Factored column load
    Mu_kNm: float = 0.0,    # Moment at base (if any)
    fck: float = 25,        # Concrete grade
    fy: float = 415,        # Steel grade
    sbc_kN_m2: float = 150, # Safe Bearing Capacity of soil
    col_b_mm: float = 300,  # Column width
    col_D_mm: float = 300,  # Column depth (= width for square)
    cover_mm: float = 50,   # Cover to main steel
    bar_dia_mm: float = 12,
    gamma_soil_kN_m3: float = 18.0,  # Unit weight of soil
    depth_of_foundation_m: float = 1.5,
) -> Dict:
    """
    Square isolated footing design per IS 456:2000.
    Steps: size → depth → shear check → steel design
    """
    Pu = Pu_kN * 1000      # N
    self_wt_factor = 1.10  # 10% extra for self-weight of footing + soil
    P_gross = Pu_kN * self_wt_factor / 1.5   # Unfactored gross load (kN)

    # ── Footing plan size ─────────────────────────────────────────────────────
    A_req = P_gross / sbc_kN_m2   # m²
    L = math.ceil(math.sqrt(A_req) * 10) / 10   # Round up to 0.1m
    B = L   # Square footing
    A_prov = L * B

    # ── Net upward soil pressure (factored) ──────────────────────────────────
    q_net = Pu_kN / A_prov   # kN/m² (factored)
    q_net_N_mm2 = q_net / 1000   # N/mm²

    # ── Critical sections ─────────────────────────────────────────────────────
    L_mm = L * 1000
    B_mm = B * 1000
    # Projection beyond column face
    px = (L_mm - col_b_mm) / 2   # in x-direction

    # ── Effective depth from punching shear (IS 456 Cl. 31.6.1) ─────────────
    # Punching shear perimeter at d/2 from column face
    # Vp = qu * (L² - (c+d)²) — iterative but we estimate d first
    # Estimate: d ≥ Vp / (τcp * perimeter)
    # τcp = ks * τc = 1.0 * 0.25*sqrt(fck) for β=1 (square column)
    tc_punch = 0.25 * math.sqrt(fck)   # N/mm²
    # Start with d_est and iterate
    for d_trial in range(200, 1200, 25):
        d = d_trial
        # Critical perimeter at d/2 from column face
        perim = 2 * (col_b_mm + d + col_D_mm + d)   # mm
        # Area within punching perimeter
        A_punching_m2 = (col_b_mm + d)**2 / 1e6
        Vp = q_net_N_mm2 * (L_mm * B_mm - (col_b_mm + d)**2)  # N
        tau_v_punch = Vp / (perim * d)
        if tau_v_punch <= tc_punch:
            break

    D_foot = d + cover_mm + bar_dia_mm  # Overall depth
    D_foot = math.ceil(D_foot / 50) * 50   # Round to 50mm

    d = D_foot - cover_mm - bar_dia_mm / 2

    # ── Bending moment at column face (IS 456 Cl. 34.4) ──────────────────────
    Mu_face = q_net_N_mm2 * B_mm * px**2 / 2   # N·mm (per unit width × B)
    # Per meter width: Mu_m = q_net_N_mm2 * 1000 * px² / 2
    Mu_m = q_net_N_mm2 * 1000 * px**2 / 2   # N·mm per 1000mm strip

    # ── Steel design (per m width) ────────────────────────────────────────────
    b_strip = 1000
    disc = max(0, 1 - (4.6 * Mu_m) / (fck * b_strip * d**2))
    Ast = (0.5 * fck / fy) * b_strip * d * (1 - math.sqrt(disc))
    Ast_min = 0.0012 * b_strip * D_foot   # 0.12% for HYSD
    Ast = max(Ast, Ast_min)

    bar_area = math.pi * bar_dia_mm**2 / 4
    spacing = math.floor(bar_area / Ast * 1000)
    spacing = min(spacing, min(3 * D_foot, 300))
    spacing = max(spacing, 75)
    Ast_provided = bar_area / spacing * 1000

    # ── One-way shear check at 'd' from column face ───────────────────────────
    x_shear = px - d   # Distance from edge to d-from-column-face
    Vu_one = q_net_N_mm2 * B_mm * max(x_shear, 0)   # N
    tau_v_one = Vu_one / (B_mm * d)
    pt = 100 * Ast_provided / (b_strip * d)
    beta = max(0.8 * fck / (6.89 * pt), 1.0)
    tc_one = 0.85 * math.sqrt(0.8 * fck) * (math.sqrt(1 + 5 * beta) - 1) / (6 * beta)
    shear_ok = tau_v_one <= tc_one

    # ── Total steel quantity ─────────────────────────────────────────────────
    n_bars_x = math.floor(B_mm / spacing) + 1
    n_bars_y = math.floor(L_mm / spacing) + 1
    bar_len = L_mm - 2 * cover_mm + 2 * 9 * bar_dia_mm  # with hooks
    total_steel_kg = (n_bars_x + n_bars_y) * bar_len / 1000 * (bar_dia_mm**2 / 162)

    # ── Development length ────────────────────────────────────────────────────
    tbd_base = {15: 1.0, 20: 1.2, 25: 1.4, 30: 1.5, 35: 1.7, 40: 1.9}.get(int(fck), 1.4)
    tbd = tbd_base * 1.6
    Ld = round(bar_dia_mm * 0.87 * fy / (4 * tbd), 0)
    avail_length = px - cover_mm
    dev_ok = avail_length >= Ld

    return {
        "input": {
            "Pu_kN":                Pu_kN,
            "Mu_kNm":               Mu_kNm,
            "fck":                  fck,
            "fy":                   fy,
            "sbc_kN_m2":            sbc_kN_m2,
            "col_size_mm":          f"{int(col_b_mm)} × {int(col_D_mm)}",
        },
        "footing_size": {
            "L_m":                  L,
            "B_m":                  B,
            "D_mm":                 D_foot,
            "d_mm":                 round(d, 1),
            "projection_mm":        round(px, 1),
            "area_m2":              round(A_prov, 2),
        },
        "soil_pressure": {
            "q_net_kN_m2":          round(q_net, 2),
            "sbc_kN_m2":            sbc_kN_m2,
            "adequate":             q_net <= sbc_kN_m2,
        },
        "punching_shear": {
            "τv_N_mm2":            round(tau_v_punch, 3),
            "τc_punch_N_mm2":      round(tc_punch, 3),
            "ok":                  tau_v_punch <= tc_punch,
        },
        "bending_moment": {
            "Mu_kNm_per_m":        round(Mu_m / 1e6, 3),
        },
        "steel_design": {
            "Ast_required_mm2_m":   round(Ast, 1),
            "bar_dia_mm":           bar_dia_mm,
            "spacing_mm":           spacing,
            "Ast_provided_mm2_m":   round(Ast_provided, 1),
            "pt_percent":           round(pt, 3),
            "spec_x":               f"#{bar_dia_mm} @ {spacing} c/c (X-dir)",
            "spec_y":               f"#{bar_dia_mm} @ {spacing} c/c (Y-dir)",
            "n_bars_x":             n_bars_x,
            "n_bars_y":             n_bars_y,
            "total_steel_kg":       round(total_steel_kg, 1),
        },
        "one_way_shear": {
            "τv_N_mm2":            round(tau_v_one, 3),
            "τc_N_mm2":            round(tc_one, 3),
            "ok":                  shear_ok,
            "note":                "" if shear_ok else "Increase depth for one-way shear",
        },
        "development_length": {
            "Ld_mm":                int(Ld),
            "available_mm":         round(avail_length, 1),
            "ok":                   dev_ok,
            "note":                 "" if dev_ok else "Provide hooks — dev. length insufficient",
        },
        "code": "IS 456:2000 Cl. 34"
    }
