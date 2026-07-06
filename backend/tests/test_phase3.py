"""
Phase 3 (engagement) tests — comments, @mention + sign-off notifications,
section library, register CSV export. All assertions check real output.
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


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _login(u, p="demo123"):
    return client.post("/auth/login", data={"username": u, "password": p}).json()["access_token"]


def setup_module(_):
    demo = _login("demo")
    cid = client.get("/auth/me", headers=_hdr(demo)).json()["company_id"]
    db = SessionLocal()
    try:
        for u, fn in [("p3checker", "P3 Checker"), ("p3approver", "P3 Approver")]:
            if not db.query(models.User).filter_by(username=u).first():
                db.add(models.User(company_id=cid, username=u, full_name=fn, role="engineer",
                                   is_demo=True, hashed_password=hash_password("demo123"),
                                   is_active=True))
        db.commit()
    finally:
        db.close()


def _beam(h):
    res = client.post("/structural/beam/design", headers=h,
                      json={"span_m": 6, "Mu_kNm": 150, "Vu_kN": 120}).json()
    return client.post("/calculations/", headers=h,
                       json={"calculator": "RCC Beam", "title": "Beam P3",
                             "inputs": {"span_m": 6}, "result": res}).json()["id"]


def test_comment_mention_creates_notification():
    demo = _login("demo")
    rid = _beam(_hdr(demo))
    r = client.post(f"/calculations/{rid}/comments", headers=_hdr(demo),
                    json={"body": "@p3checker please verify shear spacing"})
    assert r.status_code == 201
    chk = _login("p3checker")
    feed = client.get("/notifications/?unread_only=true", headers=_hdr(chk)).json()
    assert feed["unread_count"] >= 1
    assert any("mention" in i["type"] or "Beam P3" in i["title"] for i in feed["items"])
    # comment is listed
    comments = client.get(f"/calculations/{rid}/comments", headers=_hdr(demo)).json()
    assert comments and comments[-1]["body"].startswith("@p3checker")


def test_signoff_notifies_preparer():
    demo = _login("demo")
    chk, appr = _login("p3checker"), _login("p3approver")
    rid = _beam(_hdr(demo))
    client.post(f"/calculations/{rid}/submit", headers=_hdr(demo))
    client.post(f"/calculations/{rid}/check", headers=_hdr(chk))
    client.post(f"/calculations/{rid}/approve", headers=_hdr(appr))
    feed = client.get("/notifications/", headers=_hdr(demo)).json()
    titles = [i["title"] for i in feed["items"]]
    assert "Calculation approved" in titles
    assert "Calculation checked" in titles


def test_mark_read():
    demo = _login("demo")
    before = client.get("/notifications/", headers=_hdr(demo)).json()["unread_count"]
    client.post("/notifications/read-all", headers=_hdr(demo))
    after = client.get("/notifications/", headers=_hdr(demo)).json()["unread_count"]
    assert after == 0 and before >= 0


def test_section_library():
    h = _hdr(_login("demo"))
    is_lib = client.get("/library/sections?system=IS", headers=h).json()
    assert is_lib["count"] == 16 and is_lib["sections"][0]["name"].startswith("ISMB")
    aisc = client.get("/library/sections?system=AISC", headers=h).json()
    assert aisc["count"] == 10
    assert client.get("/library/sections?system=ZZ", headers=h).status_code == 404


def test_register_csv_export():
    h = _hdr(_login("demo"))
    r = client.get("/calculations/register.csv", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert r.text.splitlines()[0].startswith("id,title,calculator")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
