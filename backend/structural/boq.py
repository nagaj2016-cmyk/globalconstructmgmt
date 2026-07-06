"""
Bill of Quantities (BOQ) Generator
Auto-generates BOQ from structural member data
Quantities: concrete (m³), formwork (m²), steel (kg)
Market rates (indicative, INR — update as needed)
"""
from typing import Dict, List, Optional
import math


# ── Indicative rates (INR) — adjust per location/market ──────────────────────
RATES = {
    "M20_concrete_m3":  6500,   # M20 concrete incl. batching + placing
    "M25_concrete_m3":  7000,
    "M30_concrete_m3":  7800,
    "M35_concrete_m3":  8500,
    "M40_concrete_m3":  9500,
    "formwork_slab_m2": 450,    # Slab soffit formwork
    "formwork_beam_m2": 550,    # Beam sides + soffit
    "formwork_col_m2":  600,    # Column shuttering
    "formwork_fdn_m2":  350,    # Foundation formwork
    "Fe415_steel_kg":   85,     # Cutting, bending, binding
    "Fe500_steel_kg":   88,
    "PCC_m3":           4200,   # Plain cement concrete (levelling)
    "excavation_m3":    350,    # Earth excavation
    "backfill_m3":      150,    # Backfilling + compaction
    "curing_m2":        25,     # Curing compound per m²
}

def concrete_grade_rate(grade: str) -> float:
    return RATES.get(f"{grade}_concrete_m3", RATES["M25_concrete_m3"])

def steel_rate(fy: int) -> float:
    return RATES.get(f"Fe{fy}_steel_kg", RATES["Fe415_steel_kg"])


def boq_beam(
    beam_id: str,
    span_m: float,
    b_mm: float,
    D_mm: float,
    n_spans: int,
    steel_kg: float,
    concrete_grade: str = "M25",
    fy: int = 415,
) -> Dict:
    b = b_mm / 1000
    d_overall = D_mm / 1000

    # Volume of concrete (deduct slab thickness if T-beam — simplified as rectangle)
    vol_concrete = span_m * b * d_overall * n_spans   # m³

    # Formwork: sides (2) + soffit (1) per beam
    form_sides = 2 * span_m * d_overall * n_spans
    form_soffit = span_m * b * n_spans
    form_total = form_sides + form_soffit

    rate_conc = concrete_grade_rate(concrete_grade)
    rate_steel = steel_rate(fy)

    return {
        "element": "Beam",
        "id": beam_id,
        "quantity": {
            "concrete_m3":  round(vol_concrete, 3),
            "formwork_m2":  round(form_total, 3),
            "steel_kg":     round(steel_kg, 2),
        },
        "rates_INR": {
            "concrete":     rate_conc,
            "formwork":     RATES["formwork_beam_m2"],
            "steel":        rate_steel,
        },
        "cost_INR": {
            "concrete":     round(vol_concrete * rate_conc, 0),
            "formwork":     round(form_total * RATES["formwork_beam_m2"], 0),
            "steel":        round(steel_kg * rate_steel, 0),
            "total":        round(vol_concrete * rate_conc + form_total * RATES["formwork_beam_m2"] + steel_kg * rate_steel, 0),
        }
    }


def boq_column(
    col_id: str,
    height_m: float,
    b_mm: float,
    D_mm: float,
    n_columns: int,
    steel_kg: float,
    concrete_grade: str = "M25",
    fy: int = 415,
) -> Dict:
    b = b_mm / 1000
    D = D_mm / 1000
    vol_concrete = height_m * b * D * n_columns
    form_total = 2 * (b + D) * height_m * n_columns
    rate_conc = concrete_grade_rate(concrete_grade)
    rate_steel = steel_rate(fy)

    return {
        "element": "Column",
        "id": col_id,
        "quantity": {
            "concrete_m3": round(vol_concrete, 3),
            "formwork_m2": round(form_total, 3),
            "steel_kg":    round(steel_kg, 2),
        },
        "rates_INR": {
            "concrete": rate_conc,
            "formwork": RATES["formwork_col_m2"],
            "steel":    rate_steel,
        },
        "cost_INR": {
            "concrete": round(vol_concrete * rate_conc, 0),
            "formwork": round(form_total * RATES["formwork_col_m2"], 0),
            "steel":    round(steel_kg * rate_steel, 0),
            "total":    round(vol_concrete * rate_conc + form_total * RATES["formwork_col_m2"] + steel_kg * rate_steel, 0),
        }
    }


def boq_slab(
    slab_id: str,
    lx_m: float,
    ly_m: float,
    D_mm: float,
    n_panels: int,
    steel_kg: float,
    concrete_grade: str = "M25",
    fy: int = 415,
) -> Dict:
    area = lx_m * ly_m * n_panels
    vol_concrete = area * D_mm / 1000
    form_total = area  # Soffit only
    rate_conc = concrete_grade_rate(concrete_grade)
    rate_steel = steel_rate(fy)

    return {
        "element": "Slab",
        "id": slab_id,
        "quantity": {
            "concrete_m3": round(vol_concrete, 3),
            "formwork_m2": round(form_total, 3),
            "steel_kg":    round(steel_kg, 2),
        },
        "rates_INR": {
            "concrete": rate_conc,
            "formwork": RATES["formwork_slab_m2"],
            "steel":    rate_steel,
        },
        "cost_INR": {
            "concrete": round(vol_concrete * rate_conc, 0),
            "formwork": round(form_total * RATES["formwork_slab_m2"], 0),
            "steel":    round(steel_kg * rate_steel, 0),
            "total":    round(vol_concrete * rate_conc + form_total * RATES["formwork_slab_m2"] + steel_kg * rate_steel, 0),
        }
    }


def boq_footing(
    fdn_id: str,
    L_m: float,
    B_m: float,
    D_mm: float,
    n_footings: int,
    steel_kg: float,
    pcc_depth_mm: float = 75,
    concrete_grade: str = "M25",
    fy: int = 415,
) -> Dict:
    area = L_m * B_m * n_footings
    depth_m = D_mm / 1000
    vol_rcc = area * depth_m
    vol_pcc = area * pcc_depth_mm / 1000
    excavation_depth = depth_m + pcc_depth_mm / 1000 + 0.3   # 300mm extra
    vol_excavation = L_m * B_m * excavation_depth * n_footings * 1.25  # 25% working space
    form_total = 2 * (L_m + B_m) * depth_m * n_footings

    rate_conc = concrete_grade_rate(concrete_grade)
    rate_steel = steel_rate(fy)

    total_cost = (
        vol_rcc * rate_conc +
        vol_pcc * RATES["PCC_m3"] +
        form_total * RATES["formwork_fdn_m2"] +
        steel_kg * rate_steel +
        vol_excavation * RATES["excavation_m3"]
    )

    return {
        "element": "Isolated Footing",
        "id": fdn_id,
        "quantity": {
            "rcc_concrete_m3":  round(vol_rcc, 3),
            "pcc_concrete_m3":  round(vol_pcc, 3),
            "excavation_m3":    round(vol_excavation, 3),
            "formwork_m2":      round(form_total, 3),
            "steel_kg":         round(steel_kg, 2),
        },
        "cost_INR": {
            "rcc":          round(vol_rcc * rate_conc, 0),
            "pcc":          round(vol_pcc * RATES["PCC_m3"], 0),
            "excavation":   round(vol_excavation * RATES["excavation_m3"], 0),
            "formwork":     round(form_total * RATES["formwork_fdn_m2"], 0),
            "steel":        round(steel_kg * rate_steel, 0),
            "total":        round(total_cost, 0),
        }
    }


def generate_structural_boq(elements: List[Dict]) -> Dict:
    """
    Consolidate all BOQ items into a single abstract.
    Each element should have 'quantity' and 'cost_INR' keys.
    """
    totals = {
        "concrete_m3": 0, "formwork_m2": 0, "steel_kg": 0,
        "excavation_m3": 0, "pcc_m3": 0,
    }
    total_cost = 0.0
    items = []

    for elem in elements:
        q = elem.get("quantity", {})
        c = elem.get("cost_INR", {})
        totals["concrete_m3"] += q.get("concrete_m3", 0) + q.get("rcc_concrete_m3", 0)
        totals["formwork_m2"] += q.get("formwork_m2", 0)
        totals["steel_kg"] += q.get("steel_kg", 0)
        totals["excavation_m3"] += q.get("excavation_m3", 0)
        totals["pcc_m3"] += q.get("pcc_concrete_m3", 0)
        total_cost += c.get("total", 0)
        items.append({
            "element": elem.get("element"),
            "id": elem.get("id"),
            "total_cost_INR": c.get("total", 0),
        })

    gst_18pct = round(total_cost * 0.18, 0)
    return {
        "items": items,
        "summary_quantities": {
            "total_concrete_m3":    round(totals["concrete_m3"], 2),
            "total_pcc_m3":         round(totals["pcc_m3"], 2),
            "total_formwork_m2":    round(totals["formwork_m2"], 2),
            "total_steel_kg":       round(totals["steel_kg"], 2),
            "total_steel_tonnes":   round(totals["steel_kg"] / 1000, 3),
            "total_excavation_m3":  round(totals["excavation_m3"], 2),
        },
        "cost_summary_INR": {
            "subtotal":             round(total_cost, 0),
            "GST_18pct":            gst_18pct,
            "grand_total":          round(total_cost + gst_18pct, 0),
            "grand_total_lakhs":    round((total_cost + gst_18pct) / 100000, 2),
        },
        "disclaimer": "Rates are indicative. Final cost depends on local market rates, site conditions, and contractor quotes."
    }
