# NagaForge — Demo Walkthrough

This demo shows the **trust core**: a structural calculation taken from design →
independent check → approval → sealed calc sheet → quantities, with an immutable
audit trail. Every figure below is produced by the real API — reproduce it with:

```bash
cd backend
DATABASE_URL=sqlite:////tmp/naga_demo.db DEBUG=true python ../scripts/demo_walkthrough.py
```

The script writes real artifacts to `demo_artifacts/`:
`calc_sheet.pdf`, `register.json`, `revision_diff.json`, `quantities.json`,
`audit_trail.json`, `transcript.txt`.

## The story (as an engineer experiences it)

**1. Sign in.** Demo workspace, isolated tenant (a firm only ever sees its own data).

**2. Create a project** — Riverside Tower, India, code basis IS 456:2000.

**3. Run a real beam design** (`POST /structural/beam/design`).
Inputs: span 6 m, Mu 150 kN·m, Vu 120 kN, b 300 mm, M25, Fe415.
Output (live): *Doubly Reinforced*, Ast ≈ **1651 mm²** → **9 – #16**, stirrups **2L – #8 @ 250 c/c**,
each result carrying an official proof source: **Bureau of Indian Standards (Government of India)**.

**4. Save + sign-off** (`/calculations/…/submit → check → approve`).
The workflow enforces what a firm actually needs:

- The preparer tries to check their own calc → **HTTP 403** (separation of duties).
- A second engineer checks it; a third approves it.
- Once approved it is **locked/immutable** — attempting to delete it → **HTTP 409**.

**5. Generate the submission-grade calc sheet** (`POST /reports/calc-sheet/{id}`).
A branded PDF with an **APPROVED** ribbon, full design trace, the official BIS source,
the legal note, and a **Prepared / Checked / Approved** certification block with names
and timestamps. (See `demo_artifacts/calc_sheet.pdf`.)

**6. Project calculation register** (`GET /calculations/register?project_id=…`).
The view a principal engineer wants: every calc rolled up by sign-off status
(`draft / prepared / checked / approved / superseded`). It reports only real
status — no invented "utilization" number.

**7. Revise → revision diff** (`/calculations/{id}/revise`, `/{id}/diff`).
Revising an approved calc creates revision 2 and supersedes revision 1 (the chain is
preserved). The diff shows exactly what changed between revisions — e.g. `fck: 25 → 30`.

**8. Design → quantities loop** (`POST /calculations/{id}/quantities`).
The saved beam design flows straight to a **bar-bending schedule** and **BOQ**:
parsed 9 × #16 main bars + #8 stirrups → **153.1 kg** steel → **BOQ total ₹20,724**.
Design and quantities stay linked, from one source of truth.

**9. Engagement layer** (`POST /calculations/{id}/comments`, `GET /notifications`,
`GET /library/sections`, `GET /calculations/register.csv`).
A review comment mentioning `@checker` instantly creates a notification in the
checker's inbox ("You were mentioned on 'Beam B12 — Level 3'"). Sign-off events
notify the preparer ("Calculation approved"). The section library serves 16 IS /
10 AISC sections for calculator dropdowns, and the register exports to CSV.

**10. Immutable audit trail** (`GET /calculations/{id}/audit`).
Every step recorded — CREATE, SUBMIT, CHECK, APPROVE, COMMENT — with who and when.

## Presentation

`presentation.html` is an auto-advancing slide deck built entirely from the
verified numbers above — open it full-screen in a browser and screen-record it
for a video walkthrough.

## Why this matters commercially

A pure calculator library computes a number. NagaForge turns that number into a
**checked, approved, audit-trailed, submission-ready calc sheet** — the deliverable
an authority accepts and a firm can stamp. That, plus verified national code sources
(IS / SANS / ECP / Eurocode / AISC / CSA) and multi-country coverage, is the wedge no
competitor serves for emerging-market consulting engineers.

## Honesty notes (kept with the facts)

- Calculators are **preliminary design aids**; every sheet states the responsible
  licensed engineer must verify and seal it. Maturity is tracked per calculator:
  India / US (AISC) / Canada (CSA) calculators have validation fixtures; EU / Australia /
  Africa packs are marked `draft` until they get the same. A build-time governance
  test blocks marking any calculator "verified" without a fixture.
- The demo uses SQLite; production runs on PostgreSQL (same code, verified via
  dialect compilation).
- Reviewers in the demo must share the demo tenant flag; real firms use ordinary
  users and never hit that.
