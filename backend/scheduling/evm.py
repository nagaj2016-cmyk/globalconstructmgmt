"""
Earned Value Management (EVM) — IS / PMBOK standard KPIs
PV, EV, AC, SV, CV, SPI, CPI, EAC, ETC, VAC, TCPI, S-curve
"""
from typing import List, Dict, Any


def calculate_evm(
    bac: float,             # Budget at Completion (total planned budget)
    pv: float,              # Planned Value (budgeted cost of work scheduled to date)
    ev: float,              # Earned Value (budgeted cost of work performed)
    ac: float,              # Actual Cost (actual cost incurred)
    planned_duration: float,  # total planned duration (days)
    elapsed_time: float,      # days elapsed so far
) -> Dict[str, Any]:

    # ── Variances ──────────────────────────────────────────────────────────────
    sv  = ev - pv          # Schedule Variance  (–ve = behind schedule)
    cv  = ev - ac          # Cost Variance      (–ve = over budget)

    # ── Performance Indices ────────────────────────────────────────────────────
    spi = ev / pv  if pv > 0 else 0.0   # Schedule Performance Index
    cpi = ev / ac  if ac > 0 else 0.0   # Cost Performance Index

    # ── Forecasts ──────────────────────────────────────────────────────────────
    eac  = bac / cpi               if cpi > 0 else bac    # Estimate at Completion
    etc  = eac - ac                                        # Estimate to Complete
    vac  = bac - eac                                       # Variance at Completion

    # TCPI — efficiency needed on remaining work to meet original BAC
    tcpi = (bac - ev) / (bac - ac) if (bac - ac) > 0 else 0.0

    # Time EAC
    time_eac = planned_duration / spi if spi > 0 else planned_duration
    time_svar = planned_duration - time_eac   # –ve means project will run over

    # Percent complete
    pct_complete = ev / bac * 100 if bac > 0 else 0.0
    pct_schedule = pv / bac * 100 if bac > 0 else 0.0

    # ── Status flag ────────────────────────────────────────────────────────────
    if cpi >= 1.0 and spi >= 1.0:
        status, status_color = "ahead", "#10b981"
    elif cpi < 0.85 or spi < 0.85:
        status, status_color = "critical", "#ef4444"
    elif cpi < 0.95 or spi < 0.95:
        status, status_color = "at_risk", "#f59e0b"
    else:
        status, status_color = "on_track", "#3b82f6"

    return {
        "inputs": {
            "bac": round(bac, 0),
            "pv":  round(pv, 0),
            "ev":  round(ev, 0),
            "ac":  round(ac, 0),
            "planned_duration_days": planned_duration,
            "elapsed_days": elapsed_time,
        },
        "variances": {
            "sv":  round(sv, 0),
            "cv":  round(cv, 0),
            "sv_pct": round(sv / bac * 100, 1) if bac > 0 else 0,
            "cv_pct": round(cv / bac * 100, 1) if bac > 0 else 0,
        },
        "indices": {
            "spi": round(spi, 3),
            "cpi": round(cpi, 3),
            "tcpi": round(tcpi, 3),
        },
        "forecasts": {
            "eac":          round(eac, 0),
            "etc":          round(etc, 0),
            "vac":          round(vac, 0),
            "time_eac_days": round(time_eac, 1),
            "time_variance_days": round(time_svar, 1),
        },
        "progress": {
            "pct_complete":  round(pct_complete, 1),
            "pct_scheduled": round(pct_schedule, 1),
        },
        "status": status,
        "status_color": status_color,
        "summary": {
            "schedule": "Behind Schedule" if sv < 0 else ("Ahead of Schedule" if sv > 0 else "On Schedule"),
            "cost":     "Over Budget"      if cv < 0 else ("Under Budget"      if cv > 0 else "On Budget"),
            "overall":  status.replace("_", " ").title(),
        },
        "interpretation": {
            "cpi": f"Every ₹1 spent returns ₹{round(cpi, 2)} of value" if cpi > 0 else "N/A",
            "spi": f"Working at {round(spi*100,1)}% of planned schedule rate" if spi > 0 else "N/A",
            "tcpi": f"Need CPI ≥ {round(tcpi,2)} on remaining work to meet budget" if tcpi > 0 else "N/A",
            "eac": f"Project will cost approx ₹{round(eac/100000,2)} Lakhs total" if eac > 0 else "N/A",
        }
    }


def build_s_curve(snapshots: List[Dict], bac: float) -> Dict:
    """
    Build S-curve arrays from EVM snapshots.
    Returns planned_values, earned_values, actual_costs, labels for Chart.js.
    """
    if not snapshots:
        return {"labels": [], "pv": [], "ev": [], "ac": []}

    sorted_snaps = sorted(snapshots, key=lambda s: s["snapshot_date"])
    labels = [str(s["snapshot_date"]) for s in sorted_snaps]
    pv_vals = [s["pv"] for s in sorted_snaps]
    ev_vals = [s["ev"] for s in sorted_snaps]
    ac_vals = [s["ac"] for s in sorted_snaps]

    # Add BAC reference line
    bac_line = [bac] * len(sorted_snaps)

    return {
        "labels": labels,
        "pv":     pv_vals,
        "ev":     ev_vals,
        "ac":     ac_vals,
        "bac":    bac_line,
        "bac_value": bac,
    }
