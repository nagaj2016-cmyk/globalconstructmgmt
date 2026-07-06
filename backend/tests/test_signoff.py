"""
Sign-off workflow + audit trail tests — the trust core.

Verifies the state machine, separation of duties, immutability of approved
calculations, revision chaining, and that every step is audit-logged.
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


def _mk_user(username, full_name, role="engineer", company_short="SODEMO"):
    db = SessionLocal()
    try:
        company = db.query(models.Company).filter_by(short_name=company_short).first()
        if not company:
            company = models.Company(name="Signoff Demo Co", short_name=company_short,
                                     country="India")
            db.add(company); db.commit(); db.refresh(company)
        u = db.query(models.User).filter_by(username=username).first()
        if not u:
            db.add(models.User(company_id=company.id, username=username, full_name=full_name,
                               role=role, hashed_password=hash_password("pw12345"),
                               is_active=True))
            db.commit()
        return company.id
    finally:
        db.close()


def _tok(username):
    r = client.post("/auth/login", data={"username": username, "password": "pw12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def setup_module(_):
    cid = _mk_user("prep_eng", "Asha Preparer")
    _mk_user("check_eng", "Bala Checker")
    _mk_user("appr_eng", "Chitra Approver", role="admin")
    globals()["_CID"] = cid


def test_full_signoff_lifecycle_and_separation_of_duties():
    prep, check, appr = _tok("prep_eng"), _tok("check_eng"), _tok("appr_eng")

    # 1. Prepare (create) a calculation
    r = client.post("/calculations/", headers=prep, json={
        "calculator": "RCC Beam", "title": "Beam B12 — L3",
        "code_basis": "IS 456:2000", "country": "India",
        "inputs": {"span_m": 6, "Mu_kNm": 150}, "result": {"overall": "PASS"},
    })
    assert r.status_code == 201, r.text
    rec = r.json()
    rid = rec["id"]
    assert rec["signoff_status"] == "draft"
    assert rec["prepared_by"] == "Asha Preparer"

    # 2. Submit for check
    assert client.post(f"/calculations/{rid}/submit", headers=prep).json()["signoff_status"] == "prepared"

    # 3. Separation of duties: preparer cannot check their own calc
    assert client.post(f"/calculations/{rid}/check", headers=prep).status_code == 403

    # 4. A different engineer checks it
    r = client.post(f"/calculations/{rid}/check", headers=check)
    assert r.json()["signoff_status"] == "checked"
    assert r.json()["checked_by"] == "Bala Checker"

    # 5. Approve (by a third) → locked/immutable
    r = client.post(f"/calculations/{rid}/approve", headers=appr)
    assert r.json()["signoff_status"] == "approved"
    assert r.json()["locked"] is True

    # 6. Immutability: cannot delete or re-transition an approved calc
    assert client.delete(f"/calculations/{rid}", headers=appr).status_code == 409
    assert client.post(f"/calculations/{rid}/submit", headers=prep).status_code == 409

    # 7. Revision: creates a new draft that supersedes the approved one
    r = client.post(f"/calculations/{rid}/revise", headers=prep)
    assert r.status_code == 201
    new = r.json()
    assert new["revision"] == 2 and new["supersedes_id"] == rid
    assert new["signoff_status"] == "draft"
    # old one is now superseded
    assert client.get(f"/calculations/{rid}", headers=prep).json()["signoff_status"] == "superseded"

    # 8. Audit trail records every step (CREATE, SUBMIT, CHECK, APPROVE, REVISE)
    trail = client.get(f"/calculations/{rid}/audit", headers=appr).json()
    actions = {e["action"] for e in trail}
    assert {"CREATE", "SUBMIT", "CHECK", "APPROVE"}.issubset(actions), actions


def test_cannot_check_before_submit():
    prep, check = _tok("prep_eng"), _tok("check_eng")
    rid = client.post("/calculations/", headers=prep, json={
        "calculator": "RCC Column", "inputs": {}, "result": {}}).json()["id"]
    # still draft — checking is not allowed until submitted
    assert client.post(f"/calculations/{rid}/check", headers=check).status_code == 409


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
