#!/usr/bin/env python3
"""
NagaForge — end-to-end DEMO walkthrough (real code, real artifacts).

Drives the actual API in-process (no server needed) through the full
engineer workflow and writes real artifacts you can open and show:

    1. Create a project
    2. Run a real IS 456 beam design
    3. Save it as a calculation (prepared)
    4. Sign-off: submit -> check -> approve  (separation of duties enforced)
    5. Generate the submission-grade calc-sheet PDF
    6. View the project calculation register
    7. Revise the approved calc -> new revision + revision diff
    8. Design -> quantities loop: bar-bending schedule + BOQ
    9. Pull the immutable audit trail

Run:
    cd backend && DATABASE_URL=sqlite:////tmp/naga_demo.db DEBUG=true \
        python ../scripts/demo_walkthrough.py

Every printed value comes from the live API response — nothing is hard-coded.
"""
import json
import os
import sys
from pathlib import Path

# Make backend importable and default to a throwaway DB so the demo is repeatable.
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/naga_demo.db")
os.environ.setdefault("DEBUG", "true")

ART = HERE.parent / "demo_artifacts"
ART.mkdir(exist_ok=True)

from fastapi.testclient import TestClient      # noqa: E402
from main import app                           # noqa: E402
from database import SessionLocal              # noqa: E402
import models                                  # noqa: E402
from auth import hash_password                 # noqa: E402

c = TestClient(app)


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(u, p):
    r = c.post("/auth/login", data={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def step(n, title):
    print(f"\n{'='*70}\n  STEP {n}: {title}\n{'='*70}")


def ensure_reviewers(company_id):
    db = SessionLocal()
    try:
        for u, fn, role in [("checker", "R. Krishnan (Checker)", "engineer"),
                            ("approver", "S. Mehta, P.E. (Approver)", "admin")]:
            x = db.query(models.User).filter_by(username=u).first()
            if not x:
                db.add(models.User(company_id=company_id, username=u, full_name=fn, role=role,
                                   is_demo=True, hashed_password=hash_password("demo123"),
                                   is_active=True))
            else:
                x.is_demo = True
                x.company_id = company_id
        db.commit()
    finally:
        db.close()


def main():
    transcript = []

    def log(msg):
        print(msg)
        transcript.append(msg)

    step(1, "Sign in to the demo workspace")
    prep = login("demo", "demo123")
    me = c.get("/auth/me", headers=h(prep)).json()
    log(f"Signed in as {me['full_name']} (company_id={me['company_id']}, demo={me['is_demo']})")
    ensure_reviewers(me["company_id"])
    chk, appr = login("checker", "demo123"), login("approver", "demo123")

    step(2, "Create a project")
    pid = c.post("/projects/", headers=h(prep),
                 json={"name": "Riverside Tower — Demo", "project_code": "DEMO-RT",
                       "country": "India", "design_code": "IS 456:2000"}).json()["id"]
    log(f"Project #{pid} created.")

    step(3, "Run a real IS 456:2000 beam design")
    beam_in = {"span_m": 6, "Mu_kNm": 150, "Vu_kN": 120, "b_mm": 300, "fck": 25, "fy": 415}
    res = c.post("/structural/beam/design", headers=h(prep), json=beam_in).json()
    log(f"Design type : {res['design_type']}")
    log(f"Ast required: {res['tension_steel']['Ast_required_mm2']} mm2  -> bars {res['tension_steel']['bars']}")
    log(f"Stirrups    : {res['shear_design']['stirrups']}")
    log(f"Proof source: {res['proof']['sources'][0]['label']} ({res['proof']['sources'][0]['authority']})")

    step(4, "Save as a calculation + sign-off (submit -> check -> approve)")
    calc = c.post("/calculations/", headers=h(prep), json={
        "calculator": "RCC Beam — IS 456:2000", "title": "Beam B12 — Level 3",
        "project_id": pid, "code_basis": "IS 456:2000", "country": "India",
        "inputs": beam_in, "result": res}).json()
    rid = calc["id"]
    log(f"Prepared calc #{rid} by {calc['prepared_by']} (status={calc['signoff_status']})")
    c.post(f"/calculations/{rid}/submit", headers=h(prep))
    # separation of duties: preparer cannot check their own work
    denied = c.post(f"/calculations/{rid}/check", headers=h(prep))
    log(f"Preparer tries to self-check -> HTTP {denied.status_code} (blocked: separation of duties)")
    st = c.post(f"/calculations/{rid}/check", headers=h(chk)).json()
    log(f"Checked by {st['checked_by']} (status={st['signoff_status']})")
    st = c.post(f"/calculations/{rid}/approve", headers=h(appr)).json()
    log(f"Approved by {st['approved_by']} (status={st['signoff_status']}, locked={st['locked']})")
    # immutability
    dele = c.delete(f"/calculations/{rid}", headers=h(appr))
    log(f"Try to delete an approved calc -> HTTP {dele.status_code} (immutable)")

    step(5, "Generate the submission-grade calc-sheet PDF")
    pdf = c.post(f"/reports/calc-sheet/{rid}", headers=h(prep))
    (ART / "calc_sheet.pdf").write_bytes(pdf.content)
    log(f"calc_sheet.pdf written ({len(pdf.content)} bytes, header={pdf.content[:5]})")

    step(6, "Project calculation register")
    reg = c.get(f"/calculations/register?project_id={pid}", headers=h(prep)).json()
    (ART / "register.json").write_text(json.dumps(reg, indent=2, default=str))
    log(f"Register totals: {reg['totals']}  (approved={reg['approved']})")

    step(7, "Revise the approved calc -> revision diff")
    new = c.post(f"/calculations/{rid}/revise", headers=h(prep)).json()
    nid = new["id"]
    log(f"Revision {new['revision']} (calc #{nid}) supersedes #{rid}")
    # A separate re-run with changed inputs to demonstrate a real diff:
    beam2 = {**beam_in, "fck": 30, "Mu_kNm": 180}
    res2 = c.post("/structural/beam/design", headers=h(prep), json=beam2).json()
    alt = c.post("/calculations/", headers=h(prep), json={
        "calculator": "RCC Beam — IS 456:2000", "title": "Beam B12 — Level 3",
        "project_id": pid, "code_basis": "IS 456:2000", "inputs": beam2, "result": res2}).json()
    diff = c.get(f"/calculations/{alt['id']}/diff?against={rid}", headers=h(prep)).json()
    (ART / "revision_diff.json").write_text(json.dumps(diff, indent=2, default=str))
    log(f"Inputs changed: {list(diff['inputs_diff']['changed'].keys())}")
    log(f"  fck: {diff['inputs_diff']['changed'].get('fck')}")

    step(8, "Design -> quantities loop (BBS + BOQ)")
    q = c.post(f"/calculations/{rid}/quantities", headers=h(prep)).json()
    (ART / "quantities.json").write_text(json.dumps(q, indent=2, default=str))
    log(f"Derived reinforcement: {q['derived_from']}")
    log(f"BBS total steel : {q['bbs']['total_steel_kg']} kg")
    log(f"BOQ total cost  : INR {q['boq']['cost_INR']['total']}")

    step(9, "Engagement — comment @mention + notifications + section library")
    cm = c.post(f"/calculations/{rid}/comments", headers=h(prep),
                json={"body": "@checker please double-check the shear spacing."})
    log(f"Comment posted (HTTP {cm.status_code}); @checker mentioned.")
    inbox = c.get("/notifications/?unread_only=true", headers=h(chk)).json()
    log(f"Checker inbox: {inbox['unread_count']} unread -> '{inbox['items'][0]['title']}'")
    lib = c.get("/library/sections?system=IS", headers=h(prep)).json()
    log(f"Section library (IS 808): {lib['count']} sections available for dropdowns")
    csv = c.get("/calculations/register.csv", headers=h(prep))
    (ART / "calc_register.csv").write_bytes(csv.content)
    log(f"Register exported to CSV ({len(csv.content)} bytes)")

    step(10, "Immutable audit trail")
    trail = c.get(f"/calculations/{rid}/audit", headers=h(appr)).json()
    (ART / "audit_trail.json").write_text(json.dumps(trail, indent=2, default=str))
    for e in trail:
        log(f"  {str(e['at'])[:19]}  {e['action']:8} by {e['by']}")

    (ART / "transcript.txt").write_text("\n".join(transcript))
    print(f"\nAll artifacts written to: {ART}")
    print("Files:", ", ".join(sorted(p.name for p in ART.iterdir())))


if __name__ == "__main__":
    main()
