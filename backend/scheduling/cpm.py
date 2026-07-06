"""
Critical Path Method (CPM) engine
Performs forward pass, backward pass, float calculation, and critical path identification.
Input: list of activities with id, name, duration_days, predecessors (list of ids)
"""
from typing import List, Dict, Any


def calculate_cpm(activities: List[Dict]) -> Dict[str, Any]:
    """
    Run full CPM analysis.
    Returns activities enriched with ES, EF, LS, LF, TF, FF, is_critical
    plus project_duration and critical_path list.
    """
    if not activities:
        return {"activities": [], "project_duration": 0, "critical_path": []}

    # Build working map
    act = {a["id"]: {**a, "ES": 0.0, "EF": 0.0, "LS": 0.0, "LF": 0.0,
                      "TF": 0.0, "FF": 0.0, "is_critical": False}
           for a in activities}

    valid_ids = set(act.keys())

    # ── Topological sort (DFS post-order) ──────────────────────────────────────
    visited, order = set(), []
    def dfs(nid):
        if nid in visited:
            return
        visited.add(nid)
        for p in act[nid].get("predecessors", []):
            if p in act:
                dfs(p)
        order.append(nid)

    for nid in act:
        dfs(nid)

    # ── Forward pass ───────────────────────────────────────────────────────────
    for nid in order:
        a = act[nid]
        preds = [act[p] for p in a.get("predecessors", []) if p in valid_ids]
        a["ES"] = max((p["EF"] for p in preds), default=0.0)
        a["EF"] = a["ES"] + a["duration_days"]

    project_duration = max(a["EF"] for a in act.values())

    # ── Backward pass ──────────────────────────────────────────────────────────
    for nid in reversed(order):
        a = act[nid]
        successors = [act[s] for s in act if nid in act[s].get("predecessors", [])]
        a["LF"] = min((s["LS"] for s in successors), default=project_duration)
        a["LS"] = a["LF"] - a["duration_days"]
        a["TF"] = round(a["LF"] - a["EF"], 4)

    # ── Float & critical flag ──────────────────────────────────────────────────
    for nid in order:
        a = act[nid]
        successors = [act[s] for s in act if nid in act[s].get("predecessors", [])]
        a["FF"] = max(0.0, min((s["ES"] for s in successors), default=project_duration) - a["EF"])
        a["is_critical"] = abs(a["TF"]) < 0.001   # float == 0

    # ── Critical path (ordered chain) ─────────────────────────────────────────
    critical_ids = [a["id"] for a in act.values() if a["is_critical"]]
    critical_path = sorted(critical_ids, key=lambda nid: act[nid]["ES"])

    result_activities = []
    for a in act.values():
        result_activities.append({
            "id": a["id"],
            "name": a["name"],
            "wbs_code": a.get("wbs_code", ""),
            "duration_days": a["duration_days"],
            "cost_budget": a.get("cost_budget", 0),
            "predecessors": a.get("predecessors", []),
            "ES": round(a["ES"], 2),
            "EF": round(a["EF"], 2),
            "LS": round(a["LS"], 2),
            "LF": round(a["LF"], 2),
            "TF": round(a["TF"], 2),
            "FF": round(a["FF"], 2),
            "is_critical": a["is_critical"],
            "percent_complete": a.get("percent_complete", 0),
            "actual_cost": a.get("actual_cost", 0),
        })

    # Sort by early start for display
    result_activities.sort(key=lambda x: (x["ES"], x["id"]))

    return {
        "activities": result_activities,
        "project_duration": round(project_duration, 2),
        "critical_path": critical_path,
        "critical_path_names": [act[i]["name"] for i in critical_path],
        "num_activities": len(activities),
        "num_critical": len(critical_ids),
    }


def gantt_data(cpm_result: Dict) -> Dict:
    """Convert CPM result to Gantt-friendly data (start day, duration, colour)."""
    rows = []
    for a in cpm_result["activities"]:
        rows.append({
            "id": a["id"],
            "name": a["name"],
            "wbs_code": a.get("wbs_code", ""),
            "start": a["ES"],
            "duration": a["duration_days"],
            "finish": a["EF"],
            "float": a["TF"],
            "is_critical": a["is_critical"],
            "percent_complete": a.get("percent_complete", 0),
            "color": "#ef4444" if a["is_critical"] else "#3b82f6",
        })
    return {
        "rows": rows,
        "project_duration": cpm_result["project_duration"],
        "critical_path": cpm_result["critical_path"],
    }
