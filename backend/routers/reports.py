"""
Phase 14 -- PDF Report Generation
Uses fpdf2 (pip install fpdf2).
Endpoints return PDF bytes with content-type application/pdf.

Reports:
  POST /reports/steel          -- IS 800 / AISC steel design calculation sheet
  POST /reports/structural     -- IS 456 structural calculation sheet
  POST /reports/qc/cube        -- QC cube test report
  POST /reports/safety/incident -- Safety incident report
  GET  /reports/project/{id}   -- Project progress report (reads DB)
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
import math
import os
from proof_sources import proof_block
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models

router = APIRouter(prefix="/reports", tags=["Reports / PDF"])

# ─── FPDF2 helper ──────────────────────────────────────────────────────────────

def _get_pdf():
    try:
        from fpdf import FPDF
        return FPDF
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="fpdf2 not installed. Run: pip install fpdf2"
        )


def _safe(text: str) -> str:
    """Replace characters outside Latin-1 range so fpdf2 built-in fonts work."""
    return (str(text)
        .replace("—", "-").replace("–", "-")   # em / en dash
        .replace("‘", "'").replace("’", "'")   # smart quotes
        .replace("“", '"').replace("”", '"')
        .replace("…", "...")                          # ellipsis
        .replace("×", "x").replace("≥", ">=").replace("≤", "<=")
        .replace("²", "2").replace("³", "3")   # superscripts
        .replace("τ", "tau ").replace("φ", "phi ").replace("σ", "sigma ")
        .replace("γ", "gamma ").replace("Δ", "delta ").replace("β", "beta ")
        .replace("λ", "lambda ").replace("π", "pi ").replace("μ", "mu ")
        .replace("·", ".").replace("→", "->")
        .encode("latin-1", errors="replace").decode("latin-1"))


def _fmt(v) -> str:
    """Human-friendly value formatting — kill float noise like 1809.8999999999."""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        r = round(v, 3)
        return str(int(r)) if r == int(r) else f"{r:g}"
    return str(v)


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Common PDF builder helpers ────────────────────────────────────────────────

BRAND_COLOR = (37, 99, 235)   # #2563eb blue
PASS_COLOR  = (22, 163, 74)   # green
FAIL_COLOR  = (220, 38, 38)   # red
GRAY        = (100, 116, 139)
LIGHT_GRAY  = (241, 245, 249)
DARK        = (15, 23, 42)


def _build_header(pdf, title: str, subtitle: str, ref_no: str):
    FPDF = type(pdf)
    # Header bar
    pdf.set_fill_color(*BRAND_COLOR)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_xy(10, 6)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 8, "NagaForge", ln=0)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(10, 16)
    pdf.cell(130, 5, "Enterprise Construction Management Platform", ln=0)
    # Ref box
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(*BRAND_COLOR)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_xy(145, 6)
    pdf.cell(55, 6, _safe(ref_no), align="C", border=1)
    pdf.set_xy(145, 13)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(55, 5, datetime.now().strftime("%d %b %Y  %H:%M"), align="C")

    # Title section
    pdf.set_xy(10, 32)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 7, _safe(title), ln=1)
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, _safe(subtitle), ln=1)
    pdf.set_draw_color(*BRAND_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.ln(4)


def _section_title(pdf, text: str):
    pdf.set_fill_color(*LIGHT_GRAY)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(190, 7, _safe(f"  {text}"), fill=True, ln=1)
    pdf.ln(1)


def _kv_row(pdf, label: str, value: str, unit: str = "", pass_fail: str = ""):
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(75, 6, _safe(label))
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(75, 6, _safe(f"{value}  {unit}"))
    if pass_fail:
        color = PASS_COLOR if pass_fail.upper() == "PASS" else FAIL_COLOR
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(30, 6, _safe(f"  {pass_fail}  "), fill=True, align="C")
    pdf.ln()


def _table_header(pdf, cols: list, widths: list):
    pdf.set_fill_color(*BRAND_COLOR)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_x(10)
    for col, w in zip(cols, widths):
        pdf.cell(w, 7, _safe(str(col)), border=1, fill=True, align="C")
    pdf.ln()


def _table_row(pdf, values: list, widths: list, fill=False):
    pdf.set_fill_color(*LIGHT_GRAY)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(10)
    for val, w in zip(values, widths):
        pdf.cell(w, 6, _safe(str(val)), border=1, fill=fill, align="C")
    pdf.ln()


def _footer(pdf):
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5,
        "Generated by NagaForge | This report is for engineering reference only. "
        "Always verify with a licensed engineer before construction.",
        align="C")
    pdf.set_xy(-30, -15)
    pdf.cell(20, 5, f"Page {pdf.page_no()}", align="R")


def _proof_for_code(code: str, report_type: str = "structural"):
    code_u = (code or "").upper()
    if "IS 800" in code_u:
        return proof_block(
            "IS 800:2007",
            ["IS 800 steel member and connection design", "IS 808 section properties", "IS 2062 steel grades"],
            ["india_bis"],
            "PDF generated from user-entered design inputs and calculated results. Verify section properties, load combinations, detailing, and local authority requirements.",
        )
    if "AISC" in code_u:
        return proof_block(
            "AISC 360",
            ["AISC 360 steel member design"],
            ["aisc_360"],
            "PDF generated from user-entered design inputs and calculated results. Verify local adoption, load combinations, bracing, and official section properties.",
        )
    if "CSA" in code_u or "NBCC" in code_u or "NBC" in code_u:
        return proof_block(
            "NBC Canada / CSA",
            ["NBC Division B Part 4", "Applicable CSA material standard"],
            ["nbc_2020", "csa_a23_3", "csa_s16"],
            "PDF generated from user-entered design inputs and calculated results. Verify local amendments and project-specific climate/seismic data.",
        )
    if report_type == "qc":
        return proof_block(
            "IS 516 / IS 456",
            ["IS 516 concrete strength testing", "IS 456 concrete acceptance criteria"],
            ["india_bis"],
            "Cube report uses entered test loads and project sample data. Verify lab calibration, sample curing, age, and acceptance criteria in the project specification.",
        )
    return proof_block(
        "IS 456:2000",
        ["IS 456 reinforced concrete design", "Applicable Indian Standards for loads and detailing"],
        ["india_bis", "india_nbc"],
        "PDF generated from user-entered design inputs and calculated results. Verify final design with the engineer of record and local authority requirements.",
    )


def _proof_section(pdf, proof: dict):
    if not proof:
        return
    _section_title(pdf, "Proof & Official Sources")
    _kv_row(pdf, "Code Basis", proof.get("code_basis", ""))
    if proof.get("maturity"):
        _kv_row(pdf, "Maturity", proof.get("maturity", ""))
    clauses = "; ".join(proof.get("clauses", []))
    if clauses:
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(190, 4.5, _safe(f"Clauses / tables: {clauses}"))
    for src in proof.get("sources", []):
        pdf.set_x(10)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*BRAND_COLOR)
        pdf.multi_cell(190, 4.5, _safe(f"{src.get('label', '')} - {src.get('authority', '')}"))
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GRAY)
        pdf.multi_cell(190, 4, _safe(src.get("url", "")))
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRAY)
    if proof.get("assumptions"):
        pdf.multi_cell(190, 4, _safe(f"Assumptions: {proof.get('assumptions')}"))
        pdf.set_x(10)
    pdf.multi_cell(190, 4, _safe(proof.get("validation_status", "")))
    pdf.set_x(10)
    pdf.multi_cell(190, 4, _safe(proof.get("legal_note", "")))
    pdf.ln(2)


# ══════════════════════════════════════════════════════════════════════════════
#  1. STEEL DESIGN REPORT
# ══════════════════════════════════════════════════════════════════════════════

class SteelReportReq(BaseModel):
    code:        str   = Field("IS 800:2007", description="Design code")
    section:     str   = Field("ISMB300")
    element_type:str   = Field("Beam", description="Beam / Column / Connection")
    project:     str   = Field("Project Name")
    engineer:    str   = Field("Engineer Name")
    # Input parameters
    span_m:      Optional[float] = None
    Md_kNm:      Optional[float] = None
    Vd_kN:       Optional[float] = None
    P_kN:        Optional[float] = None
    Leff_m:      Optional[float] = None
    grade:       str   = Field("E250")
    # Results (pass through from /steel/beam endpoint)
    results:     dict  = Field(default_factory=dict)


@router.post("/steel")
def steel_report(req: SteelReportReq):
    """Generate a steel design calculation PDF report."""
    FPDF = _get_pdf()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    ref = f"STL-{datetime.now().strftime('%Y%m%d-%H%M')}"
    _build_header(pdf,
        f"Steel {req.element_type} Design -- {req.section}",
        f"{req.code}  |  Grade: {req.grade}  |  Project: {req.project}",
        ref)

    # Project info
    _section_title(pdf, "Project Information")
    _kv_row(pdf, "Project", req.project)
    _kv_row(pdf, "Engineer", req.engineer)
    _kv_row(pdf, "Design Code", req.code)
    _kv_row(pdf, "Steel Grade", req.grade)
    _kv_row(pdf, "Section", req.section)
    pdf.ln(2)

    # Input parameters
    _section_title(pdf, "Design Input Parameters")
    if req.span_m:   _kv_row(pdf, "Span",               f"{req.span_m:.2f}", "m")
    if req.Md_kNm:   _kv_row(pdf, "Moment Demand (Md)", f"{req.Md_kNm:.1f}", "kNm")
    if req.Vd_kN:    _kv_row(pdf, "Shear Demand (Vd)",  f"{req.Vd_kN:.1f}",  "kN")
    if req.P_kN:     _kv_row(pdf, "Axial Demand (P)",   f"{req.P_kN:.1f}",   "kN")
    if req.Leff_m:   _kv_row(pdf, "Effective Length",   f"{req.Leff_m:.2f}", "m")
    pdf.ln(2)

    # Results
    if req.results:
        _section_title(pdf, "Design Checks & Results")
        r = req.results

        # Section properties if present
        if "section_properties" in r:
            sp = r["section_properties"]
            pdf.set_x(10)
            pdf.set_font("Helvetica", "BI", 9)
            pdf.set_text_color(*GRAY)
            pdf.cell(0, 6, "Section Properties", ln=1)
            for k, v in sp.items():
                _kv_row(pdf, k.replace("_"," ").title(), str(round(v, 4)) if isinstance(v, float) else str(v))

        pdf.ln(2)
        # Checks
        checks = r.get("checks", {})
        if checks:
            pdf.set_x(10)
            pdf.set_font("Helvetica", "BI", 9)
            pdf.set_text_color(*GRAY)
            pdf.cell(0, 6, "Design Checks", ln=1)
            _table_header(pdf, ["Check", "Demand", "Capacity", "Ratio", "Status"],
                          [55, 35, 35, 30, 30])
            for i, (chk, val) in enumerate(checks.items()):
                if isinstance(val, dict):
                    demand   = str(round(val.get("demand",   0), 3))
                    capacity = str(round(val.get("capacity", 0), 3))
                    ratio    = str(round(val.get("ratio",    0), 3))
                    status   = val.get("status", "")
                else:
                    demand = capacity = ratio = "-"
                    status = str(val)
                # color status cell manually
                _table_row(pdf,
                    [chk.replace("_"," ").title(), demand, capacity, ratio, status],
                    [55, 35, 35, 30, 30], fill=(i % 2 == 0))

        # Overall result
        overall = r.get("overall", r.get("result", r.get("status", "")))
        pdf.ln(4)
        ok = str(overall).upper() in ("PASS", "OK", "ADEQUATE")
        color = PASS_COLOR if ok else FAIL_COLOR
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_x(60)
        pdf.cell(90, 12, f"OVERALL: {str(overall).upper()}", fill=True, align="C", ln=1)

    _proof_section(pdf, req.results.get("proof") if req.results else _proof_for_code(req.code, "steel"))
    _footer(pdf)
    filename = f"steel_{req.section}_{req.element_type.lower()}_{ref}.pdf"
    return _pdf_response(bytes(pdf.output()), filename)


# ══════════════════════════════════════════════════════════════════════════════
#  2. QC CUBE TEST REPORT
# ══════════════════════════════════════════════════════════════════════════════

class CubeTest(BaseModel):
    sample_id:   str
    date_cast:   str
    date_tested: str
    age_days:    int
    location:    str
    grade:       str        # e.g. M25
    w1_kg: float; w2_kg: float; w3_kg: float
    area_mm2:    float = 22500.0   # 150×150 cube
    fck:         float = 25.0      # MPa

class QCReportReq(BaseModel):
    project:   str = "Project Name"
    site:      str = "Site Location"
    engineer:  str = "QC Engineer"
    tests:     List[CubeTest] = Field(default_factory=list)


@router.post("/qc/cube")
def qc_cube_report(req: QCReportReq):
    """IS 516:2018 Cube Compressive Strength Test Report."""
    FPDF = _get_pdf()
    pdf = FPDF(orientation="L")   # landscape -- more columns
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    ref = f"QC-{datetime.now().strftime('%Y%m%d-%H%M')}"
    _build_header(pdf,
        "Concrete Cube Compressive Strength Test Report",
        f"IS 516:2018  |  Project: {req.project}  |  Site: {req.site}",
        ref)

    _section_title(pdf, "Test Results")

    cols   = ["Sample ID", "Date Cast", "Date Tested", "Age\n(days)", "Location",
              "Grade", "W1 (kg)", "W2 (kg)", "W3 (kg)", "Avg. Str\n(MPa)", "fck+4\n(MPa)", "Min Str\n(MPa)", "Status"]
    widths = [22, 22, 22, 12, 28, 12, 14, 14, 14, 20, 16, 16, 20]

    _table_header(pdf, cols, widths)

    pass_count = fail_count = 0
    for i, t in enumerate(req.tests):
        # IS 516 strength from load: strength = load / area
        # Here weight columns are treated as compressive loads in kN
        loads = [t.w1_kg, t.w2_kg, t.w3_kg]
        # Convert kg-force to kN: 1 kgf = 0.00981 kN; strength = load_kN*1000 / area_mm2 MPa
        strengths = [w * 0.00981 * 1000 / t.area_mm2 for w in loads]
        avg_str  = sum(strengths) / len(strengths)
        min_str  = min(strengths)
        req_avg  = t.fck + 4.0     # IS 456 Cl. 16.1 -- mean ≥ fck + 4
        req_min  = t.fck - 4.0     # individual ≥ fck - 4

        status = "PASS" if (avg_str >= req_avg and min_str >= req_min) else "FAIL"
        if status == "PASS": pass_count += 1
        else: fail_count += 1

        _table_row(pdf, [
            t.sample_id, t.date_cast, t.date_tested, str(t.age_days),
            t.location[:14], t.grade,
            f"{t.w1_kg:.0f}", f"{t.w2_kg:.0f}", f"{t.w3_kg:.0f}",
            f"{avg_str:.1f}", f"{req_avg:.1f}", f"{min_str:.1f}", status
        ], widths, fill=(i % 2 == 0))

    pdf.ln(4)
    _section_title(pdf, "Summary")
    total = len(req.tests)
    _kv_row(pdf, "Total Samples Tested", str(total))
    _kv_row(pdf, "Pass",  str(pass_count), "", "PASS")
    _kv_row(pdf, "Fail",  str(fail_count), "", "FAIL" if fail_count else "")
    if total:
        _kv_row(pdf, "Pass Rate", f"{100*pass_count/total:.1f}", "%")

    pdf.ln(4)
    # Signature block
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(60, 5, "QC Engineer:  ___________________")
    pdf.cell(60, 5, "Site Manager:  ___________________")
    pdf.cell(60, 5, "Date:  ___________________")

    pdf.ln(8)
    _proof_section(pdf, _proof_for_code("IS 516", "qc"))
    _footer(pdf)
    return _pdf_response(bytes(pdf.output()), f"qc_cube_{ref}.pdf")


# ══════════════════════════════════════════════════════════════════════════════
#  3. SAFETY INCIDENT REPORT
# ══════════════════════════════════════════════════════════════════════════════

class SafetyIncidentReportReq(BaseModel):
    incident_no:       str = "INC-0001"
    project:           str = "Project Name"
    location:          str = "Site Location"
    date_of_incident:  str = ""
    time_of_incident:  str = ""
    reported_by:       str = ""
    injured_person:    str = ""
    incident_type:     str = "Near Miss"
    severity:          str = "Low"
    description:       str = ""
    immediate_cause:   str = ""
    root_cause:        str = ""
    corrective_actions: str = ""
    preventive_actions: str = ""
    days_lost:         int = 0
    witnesses:         str = ""
    medical_treatment: str = "None"


@router.post("/safety/incident")
def safety_incident_report(req: SafetyIncidentReportReq):
    """Safety Incident Report (HIRARC)."""
    FPDF = _get_pdf()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    _build_header(pdf,
        f"Safety Incident Report  --  {req.incident_no}",
        f"Project: {req.project}  |  Type: {req.incident_type}  |  Severity: {req.severity}",
        req.incident_no)

    # Severity color band
    sev_colors = {"Critical": (220,38,38), "High": (234,88,12),
                  "Medium": (202,138,4), "Low": (22,163,74)}
    sc = sev_colors.get(req.severity, GRAY)
    pdf.set_fill_color(*sc)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(190, 8, f"  SEVERITY: {req.severity.upper()}  --  {req.incident_type.upper()}", fill=True, ln=1)
    pdf.ln(2)

    _section_title(pdf, "Incident Details")
    _kv_row(pdf, "Incident No.",        req.incident_no)
    _kv_row(pdf, "Project",             req.project)
    _kv_row(pdf, "Location",            req.location)
    _kv_row(pdf, "Date",                req.date_of_incident or datetime.now().strftime("%d %b %Y"))
    _kv_row(pdf, "Time",                req.time_of_incident or "--")
    _kv_row(pdf, "Reported By",         req.reported_by)
    _kv_row(pdf, "Injured Person",      req.injured_person or "None")
    _kv_row(pdf, "Days Lost",           str(req.days_lost))
    _kv_row(pdf, "Medical Treatment",   req.medical_treatment)
    _kv_row(pdf, "Witnesses",           req.witnesses or "--")
    pdf.ln(2)

    def _multiline_field(label: str, text: str, h: int = 20):
        _section_title(pdf, label)
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(190, 5, _safe(text or "--"))
        pdf.ln(1)

    _multiline_field("Description of Incident",  req.description)
    _multiline_field("Immediate Cause",           req.immediate_cause)
    _multiline_field("Root Cause",                req.root_cause)
    _multiline_field("Corrective Actions",        req.corrective_actions)
    _multiline_field("Preventive Actions",        req.preventive_actions)

    # Sign-off
    pdf.ln(4)
    _section_title(pdf, "Sign-off")
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(65, 5, "Safety Officer:  ___________________")
    pdf.cell(65, 5, "Site Manager:    ___________________")
    pdf.cell(55, 5, "Date Closed:  ___________________")

    pdf.ln(8)
    _proof_section(pdf, proof_block(
        "Site safety incident reporting",
        ["Local occupational health and safety law", "Project safety plan and client reporting procedure"],
        ["india_bis"],
        "Safety reports are management records. Applicable national, state/provincial, municipal, and client safety reporting laws must be followed for formal compliance.",
    ))
    _footer(pdf)
    return _pdf_response(bytes(pdf.output()), f"incident_{req.incident_no}.pdf")


# ══════════════════════════════════════════════════════════════════════════════
#  4. PROJECT PROGRESS REPORT
# ══════════════════════════════════════════════════════════════════════════════

class TaskSummary(BaseModel):
    name:       str
    status:     str
    assignee:   str = ""
    due_date:   str = ""
    progress:   int = 0

class ProjectProgressReq(BaseModel):
    project_name:    str = "Project Name"
    project_code:    str = "PRJ-001"
    client:          str = "Client Name"
    pm:              str = "Project Manager"
    report_date:     str = ""
    start_date:      str = ""
    end_date:        str = ""
    overall_progress: int = 0
    budget_total:    float = 0.0
    spent_to_date:   float = 0.0
    spi:             float = 1.0
    cpi:             float = 1.0
    earned_value:    float = 0.0
    planned_value:   float = 0.0
    tasks:           List[TaskSummary] = Field(default_factory=list)
    risks:           str = ""
    next_steps:      str = ""
    issues:          str = ""


@router.post("/project/progress")
def project_progress_report(req: ProjectProgressReq):
    """Project Progress Report with EVM metrics."""
    FPDF = _get_pdf()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    ref = f"PPR-{datetime.now().strftime('%Y%m%d-%H%M')}"
    _build_header(pdf,
        f"Project Progress Report -- {req.project_code}",
        f"{req.project_name}  |  Client: {req.client}  |  PM: {req.pm}",
        ref)

    # Progress bar
    pdf.set_x(10)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, f"Overall Progress: {req.overall_progress}%", ln=1)
    pdf.set_x(10)
    bar_w = 190
    pdf.set_fill_color(226, 232, 240)
    pdf.rect(10, pdf.get_y(), bar_w, 6, "F")
    progress_w = bar_w * req.overall_progress / 100
    color = PASS_COLOR if req.overall_progress >= 80 else (202,138,4) if req.overall_progress >= 50 else FAIL_COLOR
    pdf.set_fill_color(*color)
    pdf.rect(10, pdf.get_y(), progress_w, 6, "F")
    pdf.ln(9)

    # Key dates
    _section_title(pdf, "Project Overview")
    _kv_row(pdf, "Project Code",  req.project_code)
    _kv_row(pdf, "Client",        req.client)
    _kv_row(pdf, "Project Manager", req.pm)
    _kv_row(pdf, "Report Date",   req.report_date or datetime.now().strftime("%d %b %Y"))
    _kv_row(pdf, "Start Date",    req.start_date or "--")
    _kv_row(pdf, "Planned End",   req.end_date or "--")
    pdf.ln(2)

    # EVM Metrics
    _section_title(pdf, "Earned Value Metrics")
    _table_header(pdf, ["Metric", "Value", "Interpretation"], [60, 40, 88])

    def _evm_row(metric, value, interp, idx):
        _table_row(pdf, [metric, value, interp], [60, 40, 88], fill=(idx % 2 == 0))

    _evm_row("Budget at Completion (BAC)", f"₹{req.budget_total:,.0f}", "Total approved budget", 0)
    _evm_row("Spent to Date (AC)",  f"₹{req.spent_to_date:,.0f}", "Actual cost incurred", 1)
    _evm_row("Planned Value (PV)",  f"₹{req.planned_value:,.0f}", "Work scheduled by now", 2)
    _evm_row("Earned Value (EV)",   f"₹{req.earned_value:,.0f}",  "Value of work done", 3)
    spi_text = "On schedule" if req.spi >= 1.0 else "Behind schedule"
    cpi_text = "Under budget" if req.cpi >= 1.0 else "Over budget"
    _evm_row("Schedule Perf. Index (SPI)", f"{req.spi:.3f}", spi_text, 4)
    _evm_row("Cost Perf. Index (CPI)", f"{req.cpi:.3f}", cpi_text, 5)
    if req.cpi > 0:
        eac = req.budget_total / req.cpi
        _evm_row("Est. At Completion (EAC)", f"₹{eac:,.0f}", "Forecast final cost", 6)
    pdf.ln(2)

    # Task summary
    if req.tasks:
        _section_title(pdf, "Task Status Summary")
        _table_header(pdf, ["Task", "Status", "Assignee", "Due Date", "Progress"],
                      [70, 30, 40, 30, 20])
        status_colors = {"Completed": "✓", "In Progress": "►", "Pending": "○", "Blocked": "✗"}
        for i, t in enumerate(req.tasks):
            _table_row(pdf, [
                t.name[:35], t.status, t.assignee[:18], t.due_date, f"{t.progress}%"
            ], [70, 30, 40, 30, 20], fill=(i % 2 == 0))
        pdf.ln(2)

    # Narrative sections
    def _narr(title, text):
        if text:
            _section_title(pdf, title)
            pdf.set_x(10)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(190, 5, text)
            pdf.ln(1)

    _narr("Issues & Blockers",  req.issues)
    _narr("Key Risks",          req.risks)
    _narr("Next Steps",         req.next_steps)

    # Sign-off
    pdf.ln(4)
    _section_title(pdf, "Approvals")
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(65, 5, "Project Manager:  ___________________")
    pdf.cell(65, 5, "Client:           ___________________")
    pdf.cell(55, 5, "Date:  ___________________")

    pdf.ln(8)
    _proof_section(pdf, proof_block(
        "Project controls / Earned Value Management",
        ["Project progress report generated from project records", "Contract and client reporting requirements govern acceptance"],
        ["india_bis"],
        "Progress, SPI, CPI, and forecasts are management indicators based on entered project data. Contract documents and client reporting rules govern formal submission.",
    ))
    _footer(pdf)
    return _pdf_response(bytes(pdf.output()), f"progress_{req.project_code}_{ref}.pdf")


# ══════════════════════════════════════════════════════════════════════════════
#  5. STRUCTURAL CALCULATION SHEET (IS 456)
# ══════════════════════════════════════════════════════════════════════════════

class StructuralCalcReq(BaseModel):
    element_type:  str   = Field("Beam", description="Beam/Column/Slab/Foundation")
    code:          str   = "IS 456:2000"
    project:       str   = "Project Name"
    engineer:      str   = "Engineer Name"
    concrete_grade:str   = "M25"
    steel_grade:   str   = "Fe415"
    inputs:        dict  = Field(default_factory=dict)
    results:       dict  = Field(default_factory=dict)
    notes:         str   = ""


@router.post("/structural")
def structural_calc_report(req: StructuralCalcReq):
    """IS 456:2000 structural element calculation sheet."""
    FPDF = _get_pdf()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    ref = f"STR-{datetime.now().strftime('%Y%m%d-%H%M')}"
    _build_header(pdf,
        f"Structural Calculation Sheet -- RC {req.element_type}",
        f"{req.code}  |  {req.concrete_grade} / {req.steel_grade}  |  Project: {req.project}",
        ref)

    _section_title(pdf, "Material Properties")
    _kv_row(pdf, "Concrete Grade", req.concrete_grade)
    _kv_row(pdf, "Steel Grade", req.steel_grade)
    fck_map = {"M15":15,"M20":20,"M25":25,"M30":30,"M35":35,"M40":40,"M45":45,"M50":50}
    fy_map  = {"Fe250":250,"Fe415":415,"Fe500":500,"Fe550":550,"Fe600":600}
    fck = fck_map.get(req.concrete_grade, 25)
    fy  = fy_map.get(req.steel_grade, 415)
    _kv_row(pdf, "fck (char. comp. strength)", f"{fck}", "MPa")
    _kv_row(pdf, "fy (yield strength)",        f"{fy}",  "MPa")
    _kv_row(pdf, "γc (partial safety factor)", "1.5",    "(IS 456 Cl.36.4.2)")
    _kv_row(pdf, "γs (partial safety factor)", "1.15",   "(IS 456 Cl.36.4.2)")
    pdf.ln(2)

    if req.inputs:
        _section_title(pdf, "Design Input Parameters")
        for k, v in req.inputs.items():
            _kv_row(pdf, k.replace("_"," ").title(), str(v))
        pdf.ln(2)

    if req.results:
        _section_title(pdf, "Design Calculations & Results")
        for k, v in req.results.items():
            if isinstance(v, dict):
                status = v.get("status", "")
                val    = str(round(v.get("value", v.get("result", 0)), 4))
                unit   = v.get("unit", "")
                _kv_row(pdf, k.replace("_"," ").title(), val, unit, status)
            else:
                _kv_row(pdf, k.replace("_"," ").title(), str(v))
        pdf.ln(2)

    if req.notes:
        _section_title(pdf, "Engineer's Notes")
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(190, 5, req.notes)

    # Sign-off
    pdf.ln(6)
    _section_title(pdf, "Certification")
    pdf.set_x(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(190, 5,
        "I certify that the above calculations have been prepared in accordance with the applicable Indian Standards. "
        "The design is based on the input parameters stated and the results should be verified by the project "
        "structural engineer of record before use in construction.")
    pdf.ln(4)
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(65, 5, f"Engineer:  {req.engineer}")
    pdf.cell(65, 5, "Signature:  ___________________")
    pdf.cell(55, 5, f"Date:  {datetime.now().strftime('%d %b %Y')}")

    pdf.ln(8)
    _proof_section(pdf, req.results.get("proof") if req.results else _proof_for_code(req.code, "structural"))
    _footer(pdf)
    return _pdf_response(bytes(pdf.output()), f"structural_{req.element_type.lower()}_{ref}.pdf")


# ══════════════════════════════════════════════════════════════════════════════
#  6. SUBMISSION-GRADE CALCULATION SHEET  (from a saved, signed-off calc)
# ══════════════════════════════════════════════════════════════════════════════

STATUS_COLORS = {
    "approved": (22, 163, 74), "checked": (37, 99, 235), "prepared": (217, 119, 6),
    "draft": (100, 116, 139), "superseded": (148, 163, 184),
}


def _brand_path(url):
    """Map a stored /uploads/... URL to an on-disk path if the file exists."""
    if not url:
        return None
    rel = url.lstrip("/")
    for base in (rel, os.path.join(os.path.dirname(__file__), "..", rel)):
        if os.path.isfile(base):
            return base
    return None


def _calc_sheet_header(pdf, company, rec):
    firm = (company.name if company else "NagaForge")
    pdf.set_fill_color(*BRAND_COLOR)
    pdf.rect(0, 0, 210, 26, "F")
    # Firm logo (if uploaded) sits at the left; text shifts right to make room.
    logo = _brand_path(getattr(company, "logo_url", None)) if company else None
    text_x = 10
    if logo:
        try:
            # Fixed 22mm box, width-bounded so a wide logo never overruns the name.
            pdf.image(logo, x=8, y=5, w=22)
            text_x = 36
        except Exception:
            pass
    pdf.set_xy(text_x, 5)
    pdf.set_font("Helvetica", "B", 15); pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 8, _safe(firm), ln=0)
    pdf.set_xy(10, 14); pdf.set_font("Helvetica", "", 8)
    pdf.cell(130, 5, _safe("Structural Calculation Sheet"), ln=0)
    # ref + revision box
    pdf.set_xy(140, 5); pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(255, 255, 255); pdf.set_text_color(*BRAND_COLOR)
    pdf.cell(60, 6, _safe(f"CALC-{rec.id}  Rev {rec.revision or 1}"), border=1, align="C")
    pdf.set_xy(140, 13); pdf.set_font("Helvetica", "", 7); pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 5, datetime.now().strftime("%d %b %Y  %H:%M"), align="C")
    # status ribbon
    st = (rec.signoff_status or "draft")
    pdf.set_xy(140, 19); pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*STATUS_COLORS.get(st, GRAY)); pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 6, _safe(st.upper()), border=0, align="C", fill=True)
    pdf.set_xy(10, 30); pdf.set_text_color(*DARK)


def _render_result(pdf, result: dict):
    """Render any calculator's nested result dict as readable sections/rows."""
    scalars = {}
    for k, v in (result or {}).items():
        # 'input' echoes the design inputs we already print; 'proof' is its own section.
        if k in ("proof", "input", "inputs"):
            continue
        if isinstance(v, dict):
            _section_title(pdf, k.replace("_", " ").title())
            status = v.get("status") or v.get("overall")
            for kk, vv in v.items():
                if isinstance(vv, (dict, list)):
                    continue
                pf = str(vv) if kk == "status" and str(vv).upper() in ("PASS", "FAIL", "SAFE", "REVISE") else ""
                _kv_row(pdf, kk.replace("_", " "), _fmt(vv), pass_fail=pf)
        elif not isinstance(v, list):
            scalars[k] = v
    if scalars:
        _section_title(pdf, "Summary")
        for k, v in scalars.items():
            pf = str(v) if k in ("overall", "status") and str(v).upper() in ("PASS", "FAIL") else ""
            _kv_row(pdf, k.replace("_", " "), _fmt(v), pass_fail=pf)


def _sign_row(pdf, role, name, when):
    pdf.set_x(10); pdf.set_font("Helvetica", "B", 8); pdf.set_text_color(*GRAY)
    pdf.cell(30, 8, _safe(role))
    pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*DARK)
    pdf.cell(70, 8, _safe(name or "________________________"))
    pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*GRAY)
    when_s = when.strftime("%d %b %Y %H:%M") if when else "pending"
    pdf.cell(50, 8, _safe(when_s), ln=1)


def _signoff_block(pdf, rec, company=None):
    _section_title(pdf, "Certification & Sign-off")
    _sign_row(pdf, "Prepared", rec.prepared_by, rec.prepared_at)
    _sign_row(pdf, "Checked", rec.checked_by, rec.checked_at)
    approved_y = pdf.get_y()
    _sign_row(pdf, "Approved", rec.approved_by, rec.approved_at)
    # Engineer's seal stamped next to the approval, once approved.
    seal = _brand_path(getattr(company, "seal_url", None)) if company else None
    if seal and rec.approved_by:
        try:
            pdf.image(seal, x=165, y=approved_y - 4, h=22)
        except Exception:
            pass
    pdf.ln(1)
    pdf.set_x(10); pdf.set_font("Helvetica", "I", 7); pdf.set_text_color(*GRAY)
    pdf.multi_cell(190, 4,
        _safe("This is a preliminary engineering calculation. Figures must be independently "
              "verified and the sheet sealed by the responsible licensed engineer under the "
              "governing jurisdiction before use in construction."))
    pdf.ln(1)


@router.post("/calc-sheet/{record_id}")
def calc_sheet(record_id: int, request: Request,
               current_user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Render a saved (ideally approved) calculation as a submission-grade PDF sheet."""
    FPDF = _get_pdf()
    rec = db.query(models.CalculationRecord).filter(
        models.CalculationRecord.id == record_id).first()   # tenant-scoped
    if not rec:
        raise HTTPException(status_code=404, detail="Calculation record not found")
    company = db.query(models.Company).filter(
        models.Company.id == current_user.company_id).first()
    project = (db.query(models.Project).filter(models.Project.id == rec.project_id).first()
               if rec.project_id else None)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    _calc_sheet_header(pdf, company, rec)

    # Title + project meta
    pdf.set_x(10); pdf.set_font("Helvetica", "B", 13); pdf.set_text_color(*DARK)
    pdf.cell(190, 9, _safe(rec.title or rec.calculator), ln=1)
    _section_title(pdf, "Project & Basis")
    _kv_row(pdf, "Calculator", rec.calculator or "")
    _kv_row(pdf, "Project", project.name if project else "-")
    _kv_row(pdf, "Country / Code", f"{rec.country or '-'}  |  {rec.code_basis or rec.design_code or '-'}")
    _kv_row(pdf, "Result", str(rec.status or "-"))

    # Inputs
    if rec.inputs:
        _section_title(pdf, "Design Inputs")
        for k, v in rec.inputs.items():
            if not isinstance(v, (dict, list)):
                _kv_row(pdf, k.replace("_", " "), _fmt(v))

    # Results
    _render_result(pdf, rec.result or {})

    # Proof & official sources (reuse existing section)
    pdf.ln(2)
    _proof_section(pdf, rec.proof or (rec.result or {}).get("proof") or {})

    # Sign-off certification (with firm seal if uploaded + approved)
    _signoff_block(pdf, rec, company)
    _footer(pdf)
    return _pdf_response(bytes(pdf.output()),
                         f"calc_sheet_{rec.id}_rev{rec.revision or 1}.pdf")
