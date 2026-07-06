"""
Phase 2 tests — project calc register, revision diff, design→BBS/BOQ loop.
All assertions check real endpoint output, not assumptions.
"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DEBUG", "true")

from main import app                       # noqa: E402
from database import SessionLocal          # noqa: E402
import models                              # noqa: E402
from auth import hash_password             # noqa: E402

client = TestClient(app)
BEAM_IN = {"span_m": 6, "Mu_kNm": 150, "Vu_kN": 120, "b_mm": 300, "fck": 25, "fy": 415}


def _demo():
    r = client.post("/auth/login", data={"username": "demo", "password": "demo123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _beam_calc(h, project_id=None, inp=None):
    inp = inp or BEAM_IN
    res = client.post("/structural/beam/design", headers=h, json=inp).json()
    return client.post("/calculations/", headers=h, json={
        "calculator": "RCC Beam — IS 456", "title": "Beam B12", "project_id": project_id,
        "code_basis": "IS 456:2000", "inputs": inp, "result": res}).json()


def test_project_register_rolls_up_status():
    h = _demo()
    pid = client.post("/projects/", headers=h, json={"name": "Register Test Project"}).json().get("id")
    _beam_calc(h, pid)
    _beam_calc(h, pid)
    reg = client.get(f"/calculations/register?project_id={pid}", headers=h).json()
    assert reg["total_calculations"] >= 2
    assert reg["totals"]["draft"] >= 2
    assert reg["awaiting_action"] >= 2
    # register must only report real status, never a fabricated utilization
    assert "utilization" not in reg["items"][0]


def test_revision_diff_detects_input_change():
    h = _demo()
    a = _beam_calc(h, inp=BEAM_IN)
    b = _beam_calc(h, inp={**BEAM_IN, "fck": 30, "Mu_kNm": 180})
    d = client.get(f"/calculations/{b['id']}/diff?against={a['id']}", headers=h).json()
    assert d["inputs_diff"]["changed"]["fck"] == {"from": 25, "to": 30}
    assert "Mu_kNm" in d["inputs_diff"]["changed"]


def test_design_to_bbs_boq_loop():
    h = _demo()
    calc = _beam_calc(h)
    q = client.post(f"/calculations/{calc['id']}/quantities", headers=h)
    assert q.status_code == 200, q.text
    body = q.json()
    # parsed from the stored "9 — #16" tension steel string
    assert body["derived_from"]["n_main_bars"] >= 2
    assert body["derived_from"]["main_bar_dia_mm"] in (12, 16, 20, 25, 32)
    assert body["bbs"]["total_steel_kg"] > 0
    assert body["boq"]["cost_INR"]["total"] > 0


def test_quantities_rejects_non_beam():
    h = _demo()
    rec = client.post("/calculations/", headers=h, json={
        "calculator": "RCC Column", "title": "C1", "inputs": {}, "result": {}}).json()
    assert client.post(f"/calculations/{rec['id']}/quantities", headers=h).status_code == 400


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
