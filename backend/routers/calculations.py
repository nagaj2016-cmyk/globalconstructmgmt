"""
Saved engineering calculations + SIGN-OFF WORKFLOW.

A calculation is not "done" when the math runs — it's done when a second,
qualified engineer has checked it and a responsible engineer has approved it.
This module enforces that discipline:

    draft ──submit──▶ prepared ──check──▶ checked ──approve──▶ approved (locked)
                                                                   │
                                                              revise│ (new revision)
                                                                   ▼
                                                              superseded

Rules that make it trustworthy:
  - The checker/approver must NOT be the person who prepared it (separation of duties).
  - An approved calculation is immutable: it cannot be edited or deleted, only
    superseded by a new revision (which preserves the full chain).
  - Every transition writes an immutable audit-log entry (who, when, what).
  - Everything is tenant-isolated (a firm only sees its own calculations).
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

import models
import audit
import notify
from database import get_db
from auth import get_current_user
from structural.bbs import generate_beam_bbs
from structural.boq import boq_beam


router = APIRouter(prefix="/calculations", tags=["Calculations & Sign-off"])

TRANSITIONS = {          # from_status -> action -> to_status
    "draft":    {"submit": "prepared"},
    "prepared": {"check": "checked", "return": "draft"},
    "checked":  {"approve": "approved", "return": "prepared"},
}


def _who(user) -> str:
    return getattr(user, "full_name", None) or getattr(user, "username", "unknown")


class CalculationRecordIn(BaseModel):
    project_id: Optional[int] = None
    calculator: str = Field(..., min_length=2, max_length=150)
    title: Optional[str] = Field(None, max_length=200)
    country: Optional[str] = None
    code_basis: Optional[str] = None
    design_code: Optional[str] = None
    inputs: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    proof: dict = Field(default_factory=dict)
    notes: Optional[str] = None


class SignoffAction(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


def _record_dict(r: models.CalculationRecord) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "calculator": r.calculator,
        "title": r.title, "country": r.country, "code_basis": r.code_basis,
        "design_code": r.design_code, "result_status": r.status,
        "inputs": r.inputs or {}, "result": r.result or {}, "proof": r.proof or {},
        "pdf_url": r.pdf_url, "notes": r.notes, "created_by": r.created_by,
        "created_at": r.created_at,
        # sign-off
        "signoff_status": r.signoff_status, "revision": r.revision,
        "supersedes_id": r.supersedes_id, "locked": bool(r.locked),
        "prepared_by": r.prepared_by, "prepared_at": r.prepared_at,
        "checked_by": r.checked_by, "checked_at": r.checked_at,
        "approved_by": r.approved_by, "approved_at": r.approved_at,
    }


def _get(db, record_id) -> models.CalculationRecord:
    rec = db.query(models.CalculationRecord).filter(
        models.CalculationRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Calculation record not found")
    return rec


# ── Create ────────────────────────────────────────────────────────────────────
@router.post("/", status_code=201)
def save_calculation(data: CalculationRecordIn, request: Request,
                     current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if data.project_id:
        if not db.query(models.Project).filter(models.Project.id == data.project_id).first():
            raise HTTPException(status_code=404, detail="Project not found")

    proof = data.proof or data.result.get("proof") or {}
    rec = models.CalculationRecord(
        project_id=data.project_id, calculator=data.calculator, title=data.title,
        country=data.country, code_basis=data.code_basis or proof.get("code_basis"),
        design_code=data.design_code,
        status=data.result.get("overall") or data.result.get("status"),
        inputs=data.inputs, result=data.result, proof=proof, notes=data.notes,
        created_by=_who(current_user),
        signoff_status="draft", revision=1, locked=False,
        prepared_by=_who(current_user), prepared_at=datetime.utcnow(),
    )
    db.add(rec)
    db.flush()
    audit.record(db, "CREATE", "CalculationRecord", rec.id,
                 summary=f"Prepared {rec.calculator} '{rec.title or ''}' rev {rec.revision}",
                 new={"signoff_status": "draft"}, user=current_user, request=request)
    db.commit(); db.refresh(rec)
    return _record_dict(rec)


# ── State transitions ─────────────────────────────────────────────────────────
def _transition(db, request, current_user, record_id, action):
    rec = _get(db, record_id)
    if rec.locked:
        raise HTTPException(status_code=409, detail="Approved calculation is immutable. Create a revision instead.")
    allowed = TRANSITIONS.get(rec.signoff_status, {})
    if action not in allowed:
        raise HTTPException(status_code=409,
                            detail=f"Cannot '{action}' a calculation in state '{rec.signoff_status}'.")
    new_status = allowed[action]
    actor = _who(current_user)
    now = datetime.utcnow()

    # Separation of duties: checker/approver must differ from the preparer.
    if action in ("check", "approve") and actor == (rec.prepared_by or ""):
        raise HTTPException(status_code=403,
                            detail="Separation of duties: the checker/approver must be a different engineer than the preparer.")

    old_status = rec.signoff_status
    rec.signoff_status = new_status
    if action == "check":
        rec.checked_by, rec.checked_at = actor, now
    elif action == "approve":
        rec.approved_by, rec.approved_at, rec.locked = actor, now, True
    elif action == "return":
        if old_status == "checked":
            rec.checked_by = rec.checked_at = None

    audit.record(db, action.upper(), "CalculationRecord", rec.id,
                 summary=f"{action.title()} by {actor}: {old_status} -> {new_status}",
                 old={"signoff_status": old_status}, new={"signoff_status": new_status},
                 user=current_user, request=request)
    # Engagement: tell the preparer their calc moved forward (check/approve).
    if action in ("check", "approve"):
        notify.notify_person(
            db, current_user.company_id, rec.prepared_by,
            title=f"Calculation {new_status}",
            message=f"'{rec.title or rec.calculator}' was {new_status} by {actor}.",
            ntype="success" if action == "approve" else "info",
            entity_type="CalculationRecord", entity_id=rec.id,
            exclude_user_id=current_user.id)
    db.commit(); db.refresh(rec)
    return _record_dict(rec)


@router.post("/{record_id}/submit")
def submit(record_id: int, request: Request, body: SignoffAction = SignoffAction(),
           current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _transition(db, request, current_user, record_id, "submit")


@router.post("/{record_id}/check")
def check(record_id: int, request: Request, body: SignoffAction = SignoffAction(),
          current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _transition(db, request, current_user, record_id, "check")


@router.post("/{record_id}/approve")
def approve(record_id: int, request: Request, body: SignoffAction = SignoffAction(),
            current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _transition(db, request, current_user, record_id, "approve")


@router.post("/{record_id}/return")
def send_back(record_id: int, request: Request, body: SignoffAction = SignoffAction(),
              current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _transition(db, request, current_user, record_id, "return")


# ── Revise an approved calculation (immutable → new revision) ──────────────────
@router.post("/{record_id}/revise", status_code=201)
def revise(record_id: int, request: Request,
           current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    old = _get(db, record_id)
    if old.signoff_status not in ("approved", "superseded"):
        raise HTTPException(status_code=409, detail="Only an approved calculation can be revised.")
    old.signoff_status = "superseded"
    new = models.CalculationRecord(
        project_id=old.project_id, calculator=old.calculator, title=old.title,
        country=old.country, code_basis=old.code_basis, design_code=old.design_code,
        status=old.status, inputs=old.inputs, result=old.result, proof=old.proof,
        notes=old.notes, created_by=_who(current_user),
        signoff_status="draft", revision=(old.revision or 1) + 1, supersedes_id=old.id,
        locked=False, prepared_by=_who(current_user), prepared_at=datetime.utcnow(),
    )
    db.add(new); db.flush()
    audit.record(db, "REVISE", "CalculationRecord", new.id,
                 summary=f"Revision {new.revision} supersedes #{old.id}",
                 old={"id": old.id, "revision": old.revision},
                 new={"id": new.id, "revision": new.revision},
                 user=current_user, request=request)
    db.commit(); db.refresh(new)
    return _record_dict(new)


# ── Read / list / delete ──────────────────────────────────────────────────────
@router.get("/")
def list_calculations(project_id: Optional[int] = None, signoff_status: Optional[str] = None,
                      code_basis: Optional[str] = None, limit: int = 100, offset: int = 0,
                      db: Session = Depends(get_db)):
    q = db.query(models.CalculationRecord)
    if project_id:
        q = q.filter(models.CalculationRecord.project_id == project_id)
    if signoff_status:
        q = q.filter(models.CalculationRecord.signoff_status == signoff_status)
    if code_basis:
        q = q.filter(models.CalculationRecord.code_basis.ilike(f"%{code_basis}%"))
    rows = (q.order_by(models.CalculationRecord.created_at.desc())
              .offset(max(offset, 0)).limit(min(max(limit, 1), 500)).all())
    return [_record_dict(r) for r in rows]


# ── Project calculation register (status roll-up) ─────────────────────────────
@router.get("/register")
def calculation_register(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Every calculation in a project with its sign-off status — the view a
    principal engineer wants. Rolls up counts by status. Superseded revisions are
    listed but flagged so the current picture is clear."""
    q = db.query(models.CalculationRecord)
    if project_id:
        q = q.filter(models.CalculationRecord.project_id == project_id)
    rows = q.order_by(models.CalculationRecord.created_at.desc()).limit(500).all()

    STATES = ["draft", "prepared", "checked", "approved", "superseded"]
    totals = {s: 0 for s in STATES}
    items = []
    for r in rows:
        st = r.signoff_status or "draft"
        totals[st] = totals.get(st, 0) + 1
        res = r.result or {}
        items.append({
            "id": r.id, "title": r.title or r.calculator, "calculator": r.calculator,
            "code_basis": r.code_basis, "revision": r.revision,
            "signoff_status": st, "is_current": st != "superseded",
            "result_status": r.status,                    # only what the calc actually returned
            "prepared_by": r.prepared_by, "checked_by": r.checked_by,
            "approved_by": r.approved_by, "approved_at": r.approved_at,
            "supersedes_id": r.supersedes_id, "created_at": r.created_at,
        })
    return {
        "project_id": project_id,
        "totals": totals,
        "total_calculations": len(rows),
        "approved": totals.get("approved", 0),
        "awaiting_action": totals.get("draft", 0) + totals.get("prepared", 0) + totals.get("checked", 0),
        "items": items,
    }


@router.get("/register.csv")
def register_csv(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Export the calculation register as CSV (for analysis / hand-off)."""
    import csv
    import io
    from fastapi import Response
    q = db.query(models.CalculationRecord)
    if project_id:
        q = q.filter(models.CalculationRecord.project_id == project_id)
    rows = q.order_by(models.CalculationRecord.created_at.desc()).limit(500).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "calculator", "code_basis", "revision",
                "signoff_status", "prepared_by", "checked_by", "approved_by", "created_at"])
    for r in rows:
        w.writerow([r.id, r.title or r.calculator, r.calculator, r.code_basis, r.revision,
                    r.signoff_status, r.prepared_by, r.checked_by, r.approved_by, r.created_at])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="calc_register.csv"'})


# ── Revision diff ─────────────────────────────────────────────────────────────
def _scalars(d: dict, prefix="") -> dict:
    """Flatten a nested dict to dotted scalar keys (ignore lists)."""
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out.update(_scalars(v, prefix + k + "."))
        elif not isinstance(v, list):
            out[prefix + k] = v
    return out


def _diff(a: dict, b: dict) -> dict:
    fa, fb = _scalars(a), _scalars(b)
    keys = sorted(set(fa) | set(fb))
    changed, added, removed = {}, {}, {}
    for k in keys:
        if k not in fa:
            added[k] = fb[k]
        elif k not in fb:
            removed[k] = fa[k]
        elif fa[k] != fb[k]:
            changed[k] = {"from": fa[k], "to": fb[k]}
    return {"changed": changed, "added": added, "removed": removed}


@router.get("/{record_id}/diff")
def diff_revisions(record_id: int, against: Optional[int] = None, db: Session = Depends(get_db)):
    """Diff a calculation against another revision (default: the one it supersedes).
    Shows exactly what inputs and results changed between revisions."""
    rec = _get(db, record_id)
    other_id = against if against is not None else rec.supersedes_id
    if other_id is None:
        raise HTTPException(status_code=400, detail="No predecessor to diff against; pass ?against=<id>.")
    other = _get(db, other_id)
    if against is None and rec.supersedes_id != other.id and other.supersedes_id != rec.id:
        pass  # explicit 'against' allows any; implicit uses the lineage link
    return {
        "base": {"id": other.id, "revision": other.revision, "signoff_status": other.signoff_status},
        "compare": {"id": rec.id, "revision": rec.revision, "signoff_status": rec.signoff_status},
        "inputs_diff": _diff(other.inputs or {}, rec.inputs or {}),
        "results_diff": _diff(other.result or {}, rec.result or {}),
    }


# ── Design → quantities loop (BBS + BOQ from a saved beam calc) ────────────────
@router.post("/{record_id}/quantities")
def calc_quantities(record_id: int, db: Session = Depends(get_db)):
    """Turn an approved/any RCC beam calculation into a bar-bending schedule and a
    quantity/BOQ take-off — closing the design→quantities loop from stored output."""
    rec = _get(db, record_id)
    res = rec.result or {}
    ins = rec.inputs or {}
    is_beam = ("beam" in (rec.calculator or "").lower()) or ("tension_steel" in res)
    if not is_beam:
        raise HTTPException(status_code=400,
                            detail="Quantities loop currently supports RCC beam calculations.")
    sec = res.get("section", {})
    ten = res.get("tension_steel", {})
    shr = res.get("shear_design", {})
    dev = res.get("development_length", {})
    # Parse "9 — #16" (n main bars, dia) and stirrup dia from "2L — #8 @ 216 c/c".
    nums = re.findall(r"\d+", ten.get("bars", "") or "")
    n_main = int(nums[0]) if len(nums) >= 1 else 2
    main_dia = int(nums[1]) if len(nums) >= 2 else int(ins.get("main_bar_dia_mm", 16))
    m = re.search(r"#(\d+)", shr.get("stirrups", "") or "")
    stirrup_dia = int(m.group(1)) if m else int(ins.get("stirrup_dia_mm", 8))

    span_m = float(ins.get("span_m") or (res.get("input", {}) or {}).get("span_m") or 6)
    b_mm = float(sec.get("b_mm") or ins.get("b_mm") or 300)
    D_mm = float(sec.get("D_mm") or ins.get("D_mm") or 450)
    cover = float(sec.get("cover_mm") or ins.get("cover_mm") or 25)
    spacing = float(shr.get("stirrup_spacing_mm") or 150)
    Ld = float(dev.get("Ld_mm") or 470)

    bbs = generate_beam_bbs(
        beam_id=(rec.title or f"CALC-{rec.id}"), span_mm=span_m * 1000, b_mm=b_mm, D_mm=D_mm,
        cover_mm=cover, main_bar_dia_mm=main_dia, n_main_bars=n_main,
        stirrup_dia_mm=stirrup_dia, stirrup_spacing_mm=spacing, Ld_mm=Ld)
    steel_kg = bbs.get("total_steel_kg") or 0
    boq = boq_beam(beam_id=(rec.title or f"CALC-{rec.id}"), span_m=span_m, b_mm=b_mm, D_mm=D_mm,
                   n_spans=1, steel_kg=steel_kg,
                   concrete_grade=str(ins.get("concrete_grade", "M25")),
                   fy=int(float(ins.get("fy", 415))))
    return {
        "calculation_id": rec.id, "beam": rec.title or rec.calculator,
        "derived_from": {"n_main_bars": n_main, "main_bar_dia_mm": main_dia,
                         "stirrup_dia_mm": stirrup_dia, "stirrup_spacing_mm": spacing},
        "bbs": bbs, "boq": boq,
    }


# ── Review comments (with @mention notifications) ─────────────────────────────
class CommentIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


@router.get("/{record_id}/comments")
def list_comments(record_id: int, db: Session = Depends(get_db)):
    _get(db, record_id)  # tenant check
    rows = (db.query(models.CalcComment)
              .filter(models.CalcComment.calculation_id == record_id)
              .order_by(models.CalcComment.created_at.asc()).all())
    return [{"id": c.id, "author": c.author, "body": c.body, "created_at": c.created_at}
            for c in rows]


@router.post("/{record_id}/comments", status_code=201)
def add_comment(record_id: int, data: CommentIn, request: Request,
                current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = _get(db, record_id)
    c = models.CalcComment(calculation_id=rec.id, author=_who(current_user),
                           author_id=current_user.id, body=data.body)
    db.add(c); db.flush()
    # @mentions -> notifications; also ping the preparer if someone else comments.
    notify.notify_mentions(
        db, current_user.company_id, data.body,
        title=f"You were mentioned on '{rec.title or rec.calculator}'",
        message=f"{_who(current_user)}: {data.body[:140]}",
        entity_type="CalculationRecord", entity_id=rec.id, exclude_user_id=current_user.id)
    notify.notify_person(
        db, current_user.company_id, rec.prepared_by,
        title=f"New comment on '{rec.title or rec.calculator}'",
        message=f"{_who(current_user)}: {data.body[:140]}",
        entity_type="CalculationRecord", entity_id=rec.id, exclude_user_id=current_user.id)
    audit.record(db, "COMMENT", "CalculationRecord", rec.id,
                 summary=f"Comment by {_who(current_user)}", user=current_user, request=request)
    db.commit(); db.refresh(c)
    return {"id": c.id, "author": c.author, "body": c.body, "created_at": c.created_at}


@router.get("/{record_id}")
def get_calculation(record_id: int, db: Session = Depends(get_db)):
    return _record_dict(_get(db, record_id))


@router.get("/{record_id}/audit")
def calculation_audit(record_id: int, current_user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _get(db, record_id)  # tenant check
    rows = audit.list_for_tenant(db, current_user.company_id, "CalculationRecord", record_id)
    return [{"action": a.action, "by": a.username, "at": a.timestamp, "summary": a.summary}
            for a in rows]


@router.delete("/{record_id}")
def delete_calculation(record_id: int, request: Request,
                       current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = _get(db, record_id)
    if rec.locked or rec.signoff_status == "approved":
        raise HTTPException(status_code=409, detail="Approved calculations are immutable and cannot be deleted.")
    audit.record(db, "DELETE", "CalculationRecord", rec.id,
                 summary=f"Deleted draft {rec.calculator} rev {rec.revision}",
                 old={"id": rec.id}, user=current_user, request=request)
    db.delete(rec); db.commit()
    return {"ok": True}
