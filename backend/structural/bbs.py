"""
Bar Bending Schedule (BBS) Generator
IS 2502:2014 — Bending and forming of bars for concrete reinforcement
Bend allowances, hook lengths, cut lengths, weights
Unit weight of steel: D²/162 kg/m (for deformed bars)
"""
import math
from typing import Dict, List, Optional


# ── Constants ─────────────────────────────────────────────────────────────────
def bar_weight_per_m(dia_mm: float) -> float:
    """Weight of deformed bar per meter (kg/m) = D²/162."""
    return round(dia_mm**2 / 162, 4)

def standard_hook_length(dia_mm: float) -> float:
    """Standard 180° hook = 9d per IS 2502 (used at beam ends)."""
    return 9 * dia_mm

def bend_deduction_90(dia_mm: float) -> float:
    """Deduction for one 90° bend = 2d per IS 2502."""
    return 2 * dia_mm

def bend_deduction_45(dia_mm: float) -> float:
    """Deduction for one 45° bend = 1d per IS 2502."""
    return 1 * dia_mm

def stirrup_cut_length(b_mm: float, d_mm: float, dia_mm: float, cover_mm: float = 25) -> float:
    """
    Cut length for rectangular stirrup with 135° hooks:
    2*(b-2c) + 2*(D-2c) + 2*(10d hook) - 3*(2d for 135° bend) × 2 bends
    Simplified: perimeter + 2*(10d) - deductions
    """
    clear_b = b_mm - 2 * cover_mm
    clear_d = d_mm - 2 * cover_mm
    perimeter = 2 * (clear_b + clear_d)
    hook = 2 * (10 * dia_mm)          # Two 135° hooks
    deductions = 3 * bend_deduction_90(dia_mm) * 2   # 2 bends per corner × 4 corners simplified
    cut = perimeter + hook
    return round(cut, 1)


def generate_beam_bbs(
    beam_id: str,
    span_mm: float,
    b_mm: float,
    D_mm: float,
    cover_mm: float,
    main_bar_dia_mm: float,
    n_main_bars: int,
    stirrup_dia_mm: float,
    stirrup_spacing_mm: float,
    extra_top_dia_mm: float = 0,
    n_extra_top: int = 0,
    Ld_mm: float = 470,
) -> Dict:
    """BBS for a rectangular RCC beam."""
    rows = []
    total_weight = 0.0

    # ── Bottom main bars ──────────────────────────────────────────────────────
    cut_length = span_mm + 2 * Ld_mm   # Development length each side
    wt_per_m = bar_weight_per_m(main_bar_dia_mm)
    wt = n_main_bars * (cut_length / 1000) * wt_per_m
    total_weight += wt
    rows.append({
        "bar_mark": "1",
        "description": "Bottom main bars",
        "dia_mm": main_bar_dia_mm,
        "no_of_bars": n_main_bars,
        "cut_length_mm": round(cut_length),
        "weight_kg_m": wt_per_m,
        "total_weight_kg": round(wt, 2),
        "shape": "Straight with hooks",
    })

    # ── Top bars (hanger bars) — 2 nos of stirrup dia or main bar dia ─────────
    hanger_dia = max(12, stirrup_dia_mm * 2)
    cut_hanger = span_mm + 2 * Ld_mm
    wt_hanger = 2 * (cut_hanger / 1000) * bar_weight_per_m(hanger_dia)
    total_weight += wt_hanger
    rows.append({
        "bar_mark": "2",
        "description": "Top hanger bars",
        "dia_mm": hanger_dia,
        "no_of_bars": 2,
        "cut_length_mm": round(cut_hanger),
        "weight_kg_m": bar_weight_per_m(hanger_dia),
        "total_weight_kg": round(wt_hanger, 2),
        "shape": "Straight",
    })

    # ── Extra top bars (negative moment at supports) ─────────────────────────
    if n_extra_top > 0 and extra_top_dia_mm > 0:
        # Extra bars extend l/4 from supports
        extra_cut = span_mm / 4 + Ld_mm
        wt_extra = 2 * n_extra_top * (extra_cut / 1000) * bar_weight_per_m(extra_top_dia_mm)
        total_weight += wt_extra
        rows.append({
            "bar_mark": "3",
            "description": f"Extra top bars (at supports)",
            "dia_mm": extra_top_dia_mm,
            "no_of_bars": 2 * n_extra_top,
            "cut_length_mm": round(extra_cut),
            "weight_kg_m": bar_weight_per_m(extra_top_dia_mm),
            "total_weight_kg": round(wt_extra, 2),
            "shape": "L-shape (cranked)",
        })

    # ── Stirrups ──────────────────────────────────────────────────────────────
    # Dense zone at ends (IS 456 Cl. 26.5.1.5): l/4 or 2D, spacing = min(d/4, 8φmin, 100mm)
    d = D_mm - cover_mm - stirrup_dia_mm - main_bar_dia_mm / 2
    dense_len = max(span_mm / 4, 2 * D_mm)
    dense_sp = min(d / 4, 8 * main_bar_dia_mm, 100)
    dense_sp = max(dense_sp, 75)
    n_dense_one_end = math.ceil(dense_len / dense_sp) + 1
    n_dense = 2 * n_dense_one_end

    # Normal zone
    normal_len = span_mm - 2 * dense_len
    n_normal = max(0, math.ceil(normal_len / stirrup_spacing_mm) - 1)
    n_stirrups = n_dense + n_normal

    cut_stirrup = stirrup_cut_length(b_mm, D_mm, stirrup_dia_mm, cover_mm)
    wt_stirrups = n_stirrups * (cut_stirrup / 1000) * bar_weight_per_m(stirrup_dia_mm)
    total_weight += wt_stirrups
    rows.append({
        "bar_mark": "4",
        "description": f"Stirrups (2L-#{stirrup_dia_mm}): Dense @ {int(dense_sp)} (ends l/4), Normal @ {stirrup_spacing_mm}",
        "dia_mm": stirrup_dia_mm,
        "no_of_bars": n_stirrups,
        "cut_length_mm": round(cut_stirrup),
        "weight_kg_m": bar_weight_per_m(stirrup_dia_mm),
        "total_weight_kg": round(wt_stirrups, 2),
        "shape": "Rectangular closed stirrup",
    })

    return {
        "element": "Beam",
        "id": beam_id,
        "dimensions": f"{int(b_mm)}×{int(D_mm)} mm, L={int(span_mm)} mm",
        "bars": rows,
        "total_steel_kg": round(total_weight, 2),
        "code": "IS 2502:2014"
    }


def generate_column_bbs(
    col_id: str,
    height_mm: float,
    b_mm: float,
    D_mm: float,
    cover_mm: float,
    main_bar_dia_mm: float,
    n_main_bars: int,
    tie_dia_mm: float,
    tie_spacing_mm: float,
    overlap_len_mm: float = 0,   # Lap splice length if applicable
) -> Dict:
    """BBS for a rectangular RCC column."""
    rows = []
    total_weight = 0.0

    # ── Vertical main bars ────────────────────────────────────────────────────
    Ld = round(main_bar_dia_mm * 0.87 * 415 / (4 * 1.4 * 1.6), 0)  # approx Fe415, M25
    if overlap_len_mm == 0:
        overlap_len_mm = max(Ld, 40 * main_bar_dia_mm)   # IS 456 Cl. 26.2.5
    cut_main = height_mm + overlap_len_mm   # Includes one lap splice per storey
    wt_main = n_main_bars * (cut_main / 1000) * bar_weight_per_m(main_bar_dia_mm)
    total_weight += wt_main
    rows.append({
        "bar_mark": "1",
        "description": f"Vertical main bars (incl. {int(overlap_len_mm)}mm lap)",
        "dia_mm": main_bar_dia_mm,
        "no_of_bars": n_main_bars,
        "cut_length_mm": round(cut_main),
        "weight_kg_m": bar_weight_per_m(main_bar_dia_mm),
        "total_weight_kg": round(wt_main, 2),
        "shape": "Straight",
    })

    # ── Lateral ties ──────────────────────────────────────────────────────────
    cut_tie = stirrup_cut_length(b_mm, D_mm, tie_dia_mm, cover_mm)
    n_ties = math.ceil(height_mm / tie_spacing_mm) + 1
    # Extra ties at splice zone (3 ties at 75mm or 150mm)
    n_splice_ties = 3
    n_ties += n_splice_ties
    wt_ties = n_ties * (cut_tie / 1000) * bar_weight_per_m(tie_dia_mm)
    total_weight += wt_ties
    rows.append({
        "bar_mark": "2",
        "description": f"Lateral ties (incl. {n_splice_ties} extra at splice)",
        "dia_mm": tie_dia_mm,
        "no_of_bars": n_ties,
        "cut_length_mm": round(cut_tie),
        "weight_kg_m": bar_weight_per_m(tie_dia_mm),
        "total_weight_kg": round(wt_ties, 2),
        "shape": "Rectangular closed tie",
    })

    return {
        "element": "Column",
        "id": col_id,
        "dimensions": f"{int(b_mm)}×{int(D_mm)} mm, H={int(height_mm)} mm",
        "bars": rows,
        "total_steel_kg": round(total_weight, 2),
        "code": "IS 2502:2014"
    }


def generate_slab_bbs(
    slab_id: str,
    lx_mm: float,
    ly_mm: float,
    D_mm: float,
    cover_mm: float,
    main_dia_mm: float,
    main_spacing_mm: float,
    dist_dia_mm: float,
    dist_spacing_mm: float,
) -> Dict:
    """BBS for a two-way slab panel."""
    rows = []
    total_weight = 0.0

    # ── Short span bars (X-direction) ─────────────────────────────────────────
    cut_x = lx_mm - 2 * cover_mm + 2 * standard_hook_length(main_dia_mm)
    n_x = math.ceil(ly_mm / main_spacing_mm) + 1
    wt_x = n_x * (cut_x / 1000) * bar_weight_per_m(main_dia_mm)
    total_weight += wt_x
    rows.append({
        "bar_mark": "1",
        "description": f"Short span (Lx) — main bars",
        "dia_mm": main_dia_mm,
        "no_of_bars": n_x,
        "cut_length_mm": round(cut_x),
        "spacing_mm": main_spacing_mm,
        "weight_kg_m": bar_weight_per_m(main_dia_mm),
        "total_weight_kg": round(wt_x, 2),
        "shape": "Straight with hooks",
    })

    # ── Long span bars (Y-direction) ─────────────────────────────────────────
    cut_y = ly_mm - 2 * cover_mm + 2 * standard_hook_length(main_dia_mm)
    n_y = math.ceil(lx_mm / dist_spacing_mm) + 1
    wt_y = n_y * (cut_y / 1000) * bar_weight_per_m(dist_dia_mm)
    total_weight += wt_y
    rows.append({
        "bar_mark": "2",
        "description": "Long span (Ly) — distribution bars",
        "dia_mm": dist_dia_mm,
        "no_of_bars": n_y,
        "cut_length_mm": round(cut_y),
        "spacing_mm": dist_spacing_mm,
        "weight_kg_m": bar_weight_per_m(dist_dia_mm),
        "total_weight_kg": round(wt_y, 2),
        "shape": "Straight with hooks",
    })

    # ── Cranked / crank bars at supports (alternate bars cranked) ────────────
    crank_dia = main_dia_mm
    crank_cut = lx_mm - 2 * cover_mm + 2 * (standard_hook_length(crank_dia) + 0.45 * D_mm)
    n_crank = math.ceil(n_x / 2)
    wt_crank = n_crank * (crank_cut / 1000) * bar_weight_per_m(crank_dia)
    total_weight += wt_crank
    rows.append({
        "bar_mark": "3",
        "description": "Cranked (bent-up) bars at supports",
        "dia_mm": crank_dia,
        "no_of_bars": n_crank,
        "cut_length_mm": round(crank_cut),
        "weight_kg_m": bar_weight_per_m(crank_dia),
        "total_weight_kg": round(wt_crank, 2),
        "shape": "Cranked at 45°",
    })

    area_m2 = (lx_mm / 1000) * (ly_mm / 1000)
    return {
        "element": "Slab",
        "id": slab_id,
        "dimensions": f"Lx={int(lx_mm)} × Ly={int(ly_mm)} mm, D={D_mm} mm",
        "area_m2": round(area_m2, 2),
        "bars": rows,
        "total_steel_kg": round(total_weight, 2),
        "steel_kg_per_m2": round(total_weight / area_m2, 2),
        "code": "IS 2502:2014"
    }


def generate_footing_bbs(
    footing_id: str,
    L_mm: float,
    B_mm: float,
    D_mm: float,
    cover_mm: float,
    bar_dia_mm: float,
    spacing_mm: float,
) -> Dict:
    """BBS for isolated square footing."""
    rows = []
    total_weight = 0.0

    for direction, label in [("X", "X-direction"), ("Y", "Y-direction")]:
        cut = L_mm - 2 * cover_mm + 2 * standard_hook_length(bar_dia_mm)
        n = math.ceil(B_mm / spacing_mm) + 1
        wt = n * (cut / 1000) * bar_weight_per_m(bar_dia_mm)
        total_weight += wt
        rows.append({
            "bar_mark": direction,
            "description": f"Bottom bars — {label}",
            "dia_mm": bar_dia_mm,
            "no_of_bars": n,
            "cut_length_mm": round(cut),
            "spacing_mm": spacing_mm,
            "weight_kg_m": bar_weight_per_m(bar_dia_mm),
            "total_weight_kg": round(wt, 2),
            "shape": "Straight with hooks",
        })

    area_m2 = (L_mm / 1000) * (B_mm / 1000)
    return {
        "element": "Isolated Footing",
        "id": footing_id,
        "dimensions": f"L={int(L_mm)} × B={int(B_mm)} mm, D={D_mm} mm",
        "area_m2": round(area_m2, 2),
        "bars": rows,
        "total_steel_kg": round(total_weight, 2),
        "code": "IS 2502:2014"
    }


def consolidate_bbs(elements: List[Dict]) -> Dict:
    """Consolidate BBS for multiple elements into a summary schedule."""
    summary = {}  # dia → {count, length, weight}
    for elem in elements:
        for bar in elem.get("bars", []):
            dia = bar["dia_mm"]
            if dia not in summary:
                summary[dia] = {"dia_mm": dia, "total_bars": 0, "total_length_m": 0, "total_weight_kg": 0}
            summary[dia]["total_bars"] += bar["no_of_bars"]
            summary[dia]["total_length_m"] += round(bar["no_of_bars"] * bar["cut_length_mm"] / 1000, 2)
            summary[dia]["total_weight_kg"] += bar["total_weight_kg"]

    by_dia = sorted(summary.values(), key=lambda x: x["dia_mm"])
    for row in by_dia:
        row["total_length_m"] = round(row["total_length_m"], 2)
        row["total_weight_kg"] = round(row["total_weight_kg"], 2)

    grand_total_kg = round(sum(r["total_weight_kg"] for r in by_dia), 2)
    return {
        "schedule_by_diameter": by_dia,
        "grand_total_steel_kg": grand_total_kg,
        "grand_total_tonnes": round(grand_total_kg / 1000, 3),
    }
