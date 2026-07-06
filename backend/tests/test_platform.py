"""
Smoke tests for the platform hardening:
  - RBAC (role cannot reach a module it lacks)
  - Tenant isolation (a fresh real user sees no demo data)
  - Demo controls (only the demo account can load/reset)
  - DB-driven i18n (bundles + country proofs, nothing hardcoded)

Run:  cd backend && DATABASE_URL=sqlite:////tmp/nf_test.db DEBUG=true pytest -q
"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DEBUG", "true")

from main import app  # noqa: E402  (import after env is set)
from config import settings  # noqa: E402
from database import SessionLocal  # noqa: E402
import models  # noqa: E402
from auth import hash_password  # noqa: E402

client = TestClient(app)


def _login(username, password):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()["user"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── i18n is DB-driven ─────────────────────────────────────────────────────────
def test_locales_and_bundles_from_db():
    locales = client.get("/i18n/locales").json()
    codes = {l["code"] for l in locales}
    assert {"en", "fr", "hi", "ar"}.issubset(codes)

    hi = client.get("/i18n/hi").json()
    assert hi["strings"]["nav"]["projects"] == "परियोजनाएँ"
    ar = client.get("/i18n/ar").json()
    assert ar["direction"] == "rtl"


def test_country_codepacks_have_official_proofs():
    ca = client.get("/i18n/country/CA").json()
    disciplines = {p["discipline"] for p in ca["code_packs"]}
    assert {"concrete", "steel", "loads"}.issubset(disciplines)
    # every code pack must carry at least one official government/publisher source
    for pack in ca["code_packs"]:
        assert pack["sources"], f"{pack['code_name']} missing proof source"
        for s in pack["sources"]:
            assert s["url"].startswith("http")
            assert s["authority"]


# ── Demo account controls + isolation ─────────────────────────────────────────
def test_demo_load_reset_and_isolation():
    tok, user = _login(settings.DEMO_USERNAME, settings.DEMO_PASSWORD)
    assert user["is_demo"] is True

    # Start from a clean demo tenant so this test is order-independent
    # (other test files may have created data in the demo workspace first).
    client.post("/demo-data/reset", headers=_hdr(tok))
    r = client.post("/demo-data/load", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    projects = client.get("/projects", headers=_hdr(tok)).json()
    assert len(projects) >= 2

    # A fresh real user in their OWN company must see NONE of the demo data.
    db = SessionLocal()
    try:
        company = models.Company(name="Acme Real Co", short_name="ACME", country="India")
        db.add(company); db.commit(); db.refresh(company)
        if not db.query(models.User).filter_by(username="realuser").first():
            db.add(models.User(company_id=company.id, username="realuser",
                               full_name="Real User", role="admin",
                               hashed_password=hash_password("real123"),
                               is_active=True, is_demo=False, is_platform_admin=False))
            db.commit()
    finally:
        db.close()

    rtok, ruser = _login("realuser", "real123")
    assert ruser["is_demo"] is False
    real_projects = client.get("/projects", headers=_hdr(rtok)).json()
    assert real_projects == [] or len(real_projects) == 0

    # Dashboard aggregates must also be tenant-isolated.
    demo_dash = client.get("/dashboard", headers=_hdr(tok)).json()
    real_dash = client.get("/dashboard", headers=_hdr(rtok)).json()
    assert demo_dash["total_projects"] >= 2
    assert real_dash["total_projects"] == 0

    # real user cannot touch demo controls
    assert client.post("/demo-data/load", headers=_hdr(rtok)).status_code == 403

    # reset clears demo workspace
    assert client.post("/demo-data/reset", headers=_hdr(tok)).status_code == 200
    assert client.get("/projects", headers=_hdr(tok)).json() == []


# ── RBAC enforced centrally ───────────────────────────────────────────────────
def test_rbac_blocks_module_without_capability():
    db = SessionLocal()
    try:
        company = db.query(models.Company).filter_by(short_name="ACME").first()
        if not db.query(models.User).filter_by(username="worker1").first():
            db.add(models.User(company_id=company.id, username="worker1",
                               full_name="Ground Worker", role="worker",
                               hashed_password=hash_password("work123"),
                               is_active=True))
            db.commit()
    finally:
        db.close()

    wtok, _ = _login("worker1", "work123")
    # 'worker' has only dashboard/tasks — finance must be forbidden
    assert client.get("/finance/invoices", headers=_hdr(wtok)).status_code == 403
    # unauthenticated is rejected before RBAC
    assert client.get("/finance/invoices").status_code == 401


def test_no_data_route_is_publicly_reachable():
    """Guard against prefix-less routers leaking data (regression: /invoices,
    /expenses were reachable with no token). Every data API must require auth."""
    from main import app, PUBLIC_PATHS, PUBLIC_PREFIXES, PROTECTED_API_PREFIXES
    frontend = {"/", "/app", "/app/", "/index.html", "/landing.html", "/demo",
                "/demo.html", "/walkthrough", "/walkthrough.html", "/linkedin",
                "/linkedin-demo", "/showcase", "/api/info", "/dashboard", "/seed",
                "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/favicon.ico"}

    def covered(p):
        return (p in PUBLIC_PATHS or any(p.startswith(x) for x in PUBLIC_PREFIXES)
                or any(p.startswith(x) for x in PROTECTED_API_PREFIXES))

    leaks = []
    for r in app.routes:
        p = getattr(r, "path", "")
        methods = {m for m in (getattr(r, "methods", set()) or set())
                   if m in {"GET", "POST", "PUT", "DELETE", "PATCH"}}
        if not p.startswith("/") or not methods:
            continue
        if p in frontend or p.startswith("/uploads") or p.startswith("/i18n"):
            continue
        if not covered(p):
            leaks.append(p)
    assert not leaks, f"Unprotected data routes: {sorted(set(leaks))}"


def test_no_verified_codepack_without_validation_fixture():
    """Governance: a code pack may only be 'verified'/'production' if a validation
    fixture exists for that (country, discipline). This test fails the build if
    someone promotes a calculator's maturity without proving it against a
    published worked example — the single most important guardrail for an
    engineering product."""
    # (country, discipline) pairs covered by tests/test_calculators.py
    VALIDATED = {
        ("IN", "concrete"),   # beam, column, slab, footing
        ("IN", "steel"),      # IS 800 plastic moment + shear
        ("IN", "loads"),      # dead, wind, seismic
        ("IN", "seismic"),    # IS 1893 base shear
        # US/Canada calculators have fixtures too but their packs remain 'draft'
        # (simplified LTB), so they need not be listed until promoted.
    }
    from platform_models import CodePack
    db = SessionLocal()
    try:
        offenders = [
            (p.country_code, p.discipline, p.code_name)
            for p in db.query(CodePack).filter(
                CodePack.maturity.in_(["verified", "production"])).all()
            if (p.country_code, p.discipline) not in VALIDATED
        ]
    finally:
        db.close()
    assert not offenders, (
        "Code packs marked verified/production WITHOUT a validation fixture: "
        f"{offenders}. Either add a worked-example test or set maturity='draft'.")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
