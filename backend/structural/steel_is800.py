"""
Steel Design Engine — Phase 9
IS 800:2007  General Construction in Steel — Code of Practice
AISC 360-22  Specification for Structural Steel Buildings (LRFD)
Covers: Beams, Columns, Bolted Connections, Fillet Welds, Section Selector
"""
import math
from typing import Dict, Any, List, Optional

# ── Material grades (IS 2062 / ASTM A992) ─────────────────────────────────────
STEEL_GRADES_IS = {
    "E250":  {"fy": 250, "fu": 410, "E": 200000, "G": 77000},
    "E300":  {"fy": 300, "fu": 440, "E": 200000, "G": 77000},
    "E350":  {"fy": 350, "fu": 490, "E": 200000, "G": 77000},
    "E410":  {"fy": 410, "fu": 540, "E": 200000, "G": 77000},
    "E450":  {"fy": 450, "fu": 570, "E": 200000, "G": 77000},
}

# ── IS 808 standard I-sections (ISMB) ─────────────────────────────────────────
# h=depth, bf=flange width, tw=web t, tf=flange t  (all mm)
# Iz=Ix cm4, Iy cm4, Zpz=plastic section modulus cm3, A=area cm2
IS_SECTIONS = {
    "ISMB100": {"h":100,"bf":50, "tw":4.0,"tf":6.4, "Iz":257.5,   "Iy":9.5,    "Zpz":60.4,   "A":10.03},
    "ISMB150": {"h":150,"bf":80, "tw":4.8,"tf":7.6, "Iz":726.9,   "Iy":52.9,   "Zpz":123.3,  "A":15.07},
    "ISMB200": {"h":200,"bf":100,"tw":5.7,"tf":10.8,"Iz":2235.4,  "Iy":150.0,  "Zpz":292.0,  "A":28.51},
    "ISMB250": {"h":250,"bf":125,"tw":6.9,"tf":12.5,"Iz":5131.6,  "Iy":334.5,  "Zpz":531.3,  "A":37.31},
    "ISMB300": {"h":300,"bf":140,"tw":7.5,"tf":12.4,"Iz":8603.6,  "Iy":453.9,  "Zpz":743.9,  "A":46.01},
    "ISMB350": {"h":350,"bf":140,"tw":8.1,"tf":14.2,"Iz":13630.3, "Iy":537.4,  "Zpz":1009.4, "A":52.41},
    "ISMB400": {"h":400,"bf":140,"tw":8.9,"tf":16.0,"Iz":20458.4, "Iy":622.1,  "Zpz":1327.9, "A":61.30},
    "ISMB450": {"h":450,"bf":150,"tw":9.4,"tf":17.4,"Iz":30390.8, "Iy":834.0,  "Zpz":1742.0, "A":72.39},
    "ISMB500": {"h":500,"bf":180,"tw":10.2,"tf":17.2,"Iz":45218.0,"Iy":1369.8, "Zpz":2341.1, "A":86.65},
    "ISMB550": {"h":550,"bf":190,"tw":11.2,"tf":19.3,"Iz":64894.0,"Iy":1835.0, "Zpz":3054.8, "A":100.4},
    "ISMB600": {"h":600,"bf":210,"tw":12.0,"tf":20.8,"Iz":91813.0,"Iy":2651.0, "Zpz":3991.0, "A":121.2},
    # ISMC channels
    "ISMC100": {"h":100,"bf":50, "tw":4.7,"tf":7.5, "Iz":186.6,   "Iy":26.0,   "Zpz":47.0,   "A":11.70},
    "ISMC150": {"h":150,"bf":75, "tw":5.7,"tf":9.0, "Iz":779.6,   "Iy":103.2,  "Zpz":131.5,  "A":19.01},
    "ISMC200": {"h":200,"bf":75, "tw":6.2,"tf":11.4,"Iz":1819.3,  "Iy":140.4,  "Zpz":232.0,  "A":25.91},
    "ISMC250": {"h":250,"bf":82, "tw":7.2,"tf":12.5,"Iz":3828.7,  "Iy":219.1,  "Zpz":391.0,  "A":34.51},
    "ISMC300": {"h":300,"bf":90, "tw":7.8,"tf":13.6,"Iz":6362.6,  "Iy":310.8,  "Zpz":550.0,  "A":42.11},
}

# ── AISC W-sections (imperial, in / in4 / kips) ───────────────────────────────
AISC_SECTIONS = {
    "W8x31":  {"d":8.00, "bf":7.995,"tw":0.285,"tf":0.435,"Ix":110, "Zx":30.4,"Sx":27.5,"A":9.13,"ry":2.02,"Iy":37.1},
    "W10x49": {"d":9.98, "bf":10.0, "tw":0.34, "tf":0.56, "Ix":272, "Zx":60.4,"Sx":54.6,"A":14.4,"ry":2.54,"Iy":93.4},
    "W12x50": {"d":12.2, "bf":8.08, "tw":0.37, "tf":0.64, "Ix":394, "Zx":71.9,"Sx":64.7,"A":14.7,"ry":1.96,"Iy":56.3},
    "W14x48": {"d":13.8, "bf":8.031,"tw":0.34, "tf":0.595,"Ix":485, "Zx":78.4,"Sx":70.3,"A":14.1,"ry":2.31,"Iy":51.4},
    "W16x57": {"d":16.4, "bf":7.12, "tw":0.43, "tf":0.715,"Ix":758, "Zx":105, "Sx":92.2,"A":16.8,"ry":1.60,"Iy":43.1},
    "W18x76": {"d":18.2, "bf":11.0, "tw":0.425,"tf":0.68, "Ix":1330,"Zx":163, "Sx":146, "A":22.3,"ry":2.61,"Iy":152},
    "W18x97": {"d":18.6, "bf":11.1, "tw":0.535,"tf":0.87, "Ix":1750,"Zx":211, "Sx":188, "A":28.5,"ry":2.65,"Iy":201},
    "W21x62": {"d":20.99,"bf":8.24, "tw":0.40, "tf":0.615,"Ix":1330,"Zx":144, "Sx":127, "A":18.3,"ry":1.77,"Iy":57.5},
    "W24x76": {"d":23.9, "bf":8.99, "tw":0.44, "tf":0.68, "Ix":2100,"Zx":200, "Sx":176, "A":22.4,"ry":1.92,"Iy":82.5},
    "W24x104":{"d":24.1, "bf":12.75,"tw":0.50, "tf":0.75, "Ix":3100,"Zx":289, "Sx":258, "A":30.7,"ry":2.91,"Iy":259},
}


# ══════════════════════════════════════════════════════════════════════════════
# IS 800:2007 — BEAM DESIGN (Cl. 8)
# ══════════════════════════════════════════════════════════════════════════════

def design_beam_IS800(
    section: str,
    span_m: float,
    Md_kNm: float,
    Vd_kN: float,
    grade: str = "E250",
    Lz_m: Optional[float] = None,
    loading: str = "udl",
) -> Dict[str, Any]:
    """IS 800:2007 Cl. 8 — beam bending, shear, LTB, deflection."""
    sec = IS_SECTIONS.get(section)
    if not sec:
        return {"error": f"Section '{section}' not found. Available: {list(IS_SECTIONS.keys())}"}
    mat = STEEL_GRADES_IS.get(grade, STEEL_GRADES_IS["E250"])
    fy = mat["fy"]; E = mat["E"]; gamma_m0 = 1.10

    h = sec["h"]; tw = sec["tw"]; tf = sec["tf"]
    Iz_mm4 = sec["Iz"] * 1e4
    Zpz_mm3 = sec["Zpz"] * 1e3
    Iy_mm4 = sec["Iy"] * 1e4
    A_mm2 = sec["A"] * 1e2
    d_web = h - 2 * tf

    # 1. Plastic moment capacity (Cl. 8.2.1.2)
    Md_plastic = Zpz_mm3 * fy / (gamma_m0 * 1e6)  # kNm

    # 2. LTB check (IS 800:2007 Cl. 8.2.2) — elastic critical moment Mcr
    #    Mcr = (π/Lz) × √(E·Iy·G·J) × √(1 + π²EIw/(Lz²·G·J))
    #    λLT = √(βb·Zpz·fy / Mcr)
    Lz = (Lz_m or span_m) * 1000  # mm
    # St. Venant torsional constant J (mm4) — IS 800 / IS 808 formula
    J = (1.0/3.0) * (2.0 * sec["bf"] * tf**3 + (h - 2*tf) * tw**3)
    # Warping constant Iw (mm6) — doubly-symmetric I-section equal flanges
    Iw = Iy_mm4 * (h - tf)**2 / 4.0
    G = 77000.0  # shear modulus MPa
    GJ   = G * J
    EIy  = E * Iy_mm4
    EIw  = E * Iw
    # Elastic critical moment (N·mm)
    factor = 1.0 + (math.pi**2 * EIw) / (Lz**2 * GJ)
    Mcr_Nmm = (math.pi / Lz) * math.sqrt(EIy * GJ) * math.sqrt(max(factor, 1.0))
    Mcr_kNm = Mcr_Nmm / 1e6
    # Non-dimensional slenderness λLT (βb=1 for plastic section Cl. 8.2.2)
    lambda_LT = math.sqrt(Zpz_mm3 * fy / Mcr_Nmm)
    alpha_LT = 0.21  # IS 800 Table 13a — rolled I doubly-symmetric
    phi_LT = 0.5 * (1 + alpha_LT * (lambda_LT - 0.2) + lambda_LT**2)
    denom = phi_LT + math.sqrt(max(0.0, phi_LT**2 - lambda_LT**2))
    chi_LT = min(1.0, 1.0 / denom) if denom > 0 else 1.0
    fbd = chi_LT * fy / gamma_m0
    Md_LTB = Zpz_mm3 * fbd / 1e6
    Md_design = min(Md_plastic, Md_LTB)

    # 3. Shear capacity (Cl. 8.4.1)
    Av = h * tw
    Vd_cap = Av * fy / (math.sqrt(3) * gamma_m0 * 1000)

    # 4. Web d/t check (Cl. 8.6)
    d_over_tw = d_web / tw
    limit_dtw = 67 * math.sqrt(250 / fy)

    # 5. Deflection (Cl. 5.6.1 — L/300)
    q_kNm = Md_kNm * 8 / span_m**2 if loading == "udl" else Md_kNm * 4 / span_m
    L_mm = span_m * 1000
    if loading == "udl":
        delta = (5 * (q_kNm / 1e3) * L_mm**4) / (384 * E * Iz_mm4)
    else:
        delta = ((q_kNm * 1000) * L_mm**3) / (48 * E * Iz_mm4)
    delta_lim = L_mm / 300

    b_ok = Md_design >= Md_kNm
    v_ok = Vd_cap >= Vd_kN
    d_ok = delta <= delta_lim
    w_ok = d_over_tw <= limit_dtw

    return {
        "code": "IS 800:2007",
        "clause": "Cl. 8.2 (bending), 8.4 (shear), 5.6.1 (deflection)",
        "section": section, "grade": grade,
        "section_props": {"h_mm": h, "bf_mm": sec["bf"], "tw_mm": tw, "tf_mm": tf,
                          "Iz_cm4": sec["Iz"], "Zpz_cm3": sec["Zpz"], "A_cm2": sec["A"]},
        "bending": {
            "Md_plastic_kNm": round(Md_plastic, 2),
            "lambda_LT": round(lambda_LT, 3), "chi_LT": round(chi_LT, 3),
            "Md_LTB_kNm": round(Md_LTB, 2),
            "Md_design_kNm": round(Md_design, 2),
            "demand_kNm": Md_kNm,
            "utilization": round(Md_kNm / Md_design, 3),
            "status": "PASS" if b_ok else "FAIL",
        },
        "shear": {
            "Av_mm2": round(Av, 1), "Vd_capacity_kN": round(Vd_cap, 2),
            "demand_kN": Vd_kN,
            "utilization": round(Vd_kN / Vd_cap, 3),
            "status": "PASS" if v_ok else "FAIL",
        },
        "web": {"d_mm": round(d_web, 1), "d_over_tw": round(d_over_tw, 2),
                "limit": round(limit_dtw, 2), "status": "PASS" if w_ok else "FAIL"},
        "deflection": {
            "delta_mm": round(delta, 2), "limit_L300_mm": round(delta_lim, 2),
            "status": "PASS" if d_ok else "FAIL",
        },
        "overall": "PASS" if (b_ok and v_ok and d_ok and w_ok) else "FAIL",
    }


# ══════════════════════════════════════════════════════════════════════════════
# IS 800:2007 — COLUMN DESIGN (Cl. 7)
# ══════════════════════════════════════════════════════════════════════════════

def design_column_IS800(
    section: str,
    P_kN: float,
    Leff_m: float,
    grade: str = "E250",
    buckling_curve: str = "b",
) -> Dict[str, Any]:
    """IS 800:2007 Cl. 7 — axially loaded compression member."""
    sec = IS_SECTIONS.get(section)
    if not sec:
        return {"error": f"Section '{section}' not found."}
    mat = STEEL_GRADES_IS.get(grade, STEEL_GRADES_IS["E250"])
    fy = mat["fy"]; E = mat["E"]; gamma_m0 = 1.10

    A_mm2 = sec["A"] * 1e2
    Iy_mm4 = sec["Iy"] * 1e4
    r_min = math.sqrt(Iy_mm4 / A_mm2)
    Leff_mm = Leff_m * 1000

    # Non-dim slenderness (Cl. 7.1.2)
    lam = (Leff_mm / r_min) * math.sqrt(fy / (math.pi**2 * E))
    alpha = {"a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}.get(buckling_curve, 0.34)
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam**2)
    chi = min(1.0, 1.0 / (phi + math.sqrt(max(0.0, phi**2 - lam**2))))
    fcd = chi * fy / gamma_m0
    Pd = A_mm2 * fcd / 1000

    KL_r = Leff_mm / r_min
    sl_ok = KL_r <= 250
    cap_ok = Pd >= P_kN

    return {
        "code": "IS 800:2007", "clause": "Cl. 7.1 (compression)",
        "section": section, "grade": grade,
        "section_props": {"A_cm2": sec["A"], "Iz_cm4": sec["Iz"], "Iy_cm4": sec["Iy"],
                          "r_min_mm": round(r_min, 2)},
        "column": {
            "KL_r": round(KL_r, 1), "lambda": round(lam, 3),
            "phi": round(phi, 3), "chi": round(chi, 3),
            "fcd_MPa": round(fcd, 2), "Pd_kN": round(Pd, 2),
            "demand_kN": P_kN,
            "utilization": round(P_kN / Pd, 3),
            "status": "PASS" if cap_ok else "FAIL",
        },
        "slenderness": {"KL_r": round(KL_r, 1), "limit": 250,
                        "status": "PASS" if sl_ok else "FAIL"},
        "overall": "PASS" if (cap_ok and sl_ok) else "FAIL",
        "note": "IS 800:2007 Cl. 7. Buckling curve "+buckling_curve+" (Table 10)."
    }


# ══════════════════════════════════════════════════════════════════════════════
# IS 800:2007 — CONNECTIONS (Cl. 10)
# ══════════════════════════════════════════════════════════════════════════════

BOLT_GRADES = {
    "4.6":  {"fyb": 240,  "fub": 400},
    "4.8":  {"fyb": 320,  "fub": 400},
    "5.6":  {"fyb": 300,  "fub": 500},
    "6.8":  {"fyb": 480,  "fub": 600},
    "8.8":  {"fyb": 640,  "fub": 800},
    "10.9": {"fyb": 900,  "fub": 1000},
}

def design_bolt_IS800(
    dia_mm: float,
    n_bolts: int,
    n_shear_planes: int,
    P_kN: float,
    plate_t_mm: float,
    plate_fy: float = 250.0,
    bolt_grade: str = "8.8",
) -> Dict[str, Any]:
    """IS 800:2007 Cl. 10.3 — bearing-type bolted connection."""
    bp = BOLT_GRADES.get(bolt_grade, BOLT_GRADES["8.8"])
    fub = bp["fub"]
    gamma_mb = 1.25

    # Net tensile stress area (~0.78 × gross area)
    Anb = math.pi * (0.78 * dia_mm)**2 / 4

    # Shear capacity per bolt (Cl. 10.3.3)
    Vnsb = fub * Anb * n_shear_planes / math.sqrt(3)
    Vdsb = Vnsb / (gamma_mb * 1000)

    # Bearing capacity per bolt (Cl. 10.3.4)
    e = 1.5 * dia_mm
    kb = min(e / (3 * dia_mm), 1.0)
    Vnpb = 2.5 * kb * dia_mm * plate_t_mm * plate_fy
    Vdpb = Vnpb / (gamma_mb * 1000)

    Vd_per = min(Vdsb, Vdpb)
    Vd_total = Vd_per * n_bolts
    ok = Vd_total >= P_kN

    return {
        "code": "IS 800:2007 Cl. 10.3",
        "bolt_grade": bolt_grade, "dia_mm": dia_mm,
        "n_bolts": n_bolts, "n_shear_planes": n_shear_planes,
        "shear_capacity_per_bolt_kN": round(Vdsb, 2),
        "bearing_capacity_per_bolt_kN": round(Vdpb, 2),
        "governing_per_bolt_kN": round(Vd_per, 2),
        "total_capacity_kN": round(Vd_total, 2),
        "demand_kN": P_kN,
        "utilization": round(P_kN / Vd_total, 3),
        "status": "PASS" if ok else "FAIL",
        "note": "Cl. 10.3.3 (shear), 10.3.4 (bearing). Partial safety γmb = 1.25."
    }


def design_fillet_weld_IS800(
    size_mm: float,
    length_mm: float,
    P_kN: float,
    grade: str = "E250",
) -> Dict[str, Any]:
    """IS 800:2007 Cl. 10.5 — fillet weld."""
    mat = STEEL_GRADES_IS.get(grade, STEEL_GRADES_IS["E250"])
    fu = mat["fu"]; gamma_mw = 1.25
    tt = 0.7 * size_mm  # effective throat
    cap_per_mm = fu * tt / (math.sqrt(3) * gamma_mw * 1000)
    Vdw = cap_per_mm * length_mm
    ok = Vdw >= P_kN
    return {
        "code": "IS 800:2007 Cl. 10.5.7.1",
        "weld_size_mm": size_mm, "throat_mm": round(tt, 2),
        "length_mm": length_mm,
        "capacity_per_mm_kN": round(cap_per_mm, 4),
        "total_capacity_kN": round(Vdw, 2),
        "demand_kN": P_kN,
        "utilization": round(P_kN / Vdw, 3),
        "status": "PASS" if ok else "FAIL",
    }


# ══════════════════════════════════════════════════════════════════════════════
# AISC 360-22 LRFD — BEAM DESIGN
# ══════════════════════════════════════════════════════════════════════════════

def design_beam_AISC(
    section: str,
    span_ft: float,
    Mu_kip_ft: float,
    Vu_kips: float,
    Lb_ft: float,
    Fy_ksi: float = 50.0,
    loading: str = "udl",
) -> Dict[str, Any]:
    """AISC 360-22 LRFD Cl. F (flexure), G (shear)."""
    sec = AISC_SECTIONS.get(section)
    if not sec:
        return {"error": f"Section '{section}' not found. Available: {list(AISC_SECTIONS.keys())}"}
    phi_b = 0.90; phi_v = 1.00; E = 29000

    Zx = sec["Zx"]; Sx = sec["Sx"]; ry = sec["ry"]
    d = sec["d"]; tw = sec["tw"]

    # F2: Yielding
    Mp = Fy_ksi * Zx / 12  # kip-ft
    # F2: Limiting unbraced lengths
    Lp = 1.76 * ry * math.sqrt(E / Fy_ksi) / 12  # ft

    # Simplified Lr approximation
    c = 1.0  # doubly symmetric
    rts = math.sqrt(math.sqrt(sec["Iy"] * sec.get("Ix", sec["Ix"] if "Ix" in sec else sec["Zx"] * 12 / Fy_ksi * E)) / Sx) if False else ry * 1.5
    Lr = 1.95 * rts * E / (0.7 * Fy_ksi) * math.sqrt(1) / 12

    if Lb_ft <= Lp:
        Mn = Mp
        ltb = "No LTB"
    elif Lb_ft <= Lr:
        Mn = Mp - (Mp - 0.7 * Fy_ksi * Sx / 12) * (Lb_ft - Lp) / (Lr - Lp)
        ltb = "Inelastic LTB"
    else:
        # Elastic LTB — simplified
        Mn = max(0.7 * Fy_ksi * Sx / 12, Mp * 0.5)
        ltb = "Elastic LTB"
    Mn = min(Mn, Mp)

    phi_Mn = phi_b * Mn

    # G2: Shear
    Aw = d * tw
    Vn = 0.6 * Fy_ksi * Aw
    phi_Vn = phi_v * Vn

    # Deflection L/360
    if loading == "udl":
        w = Mu_kip_ft * 8 / span_ft**2  # k/ft
        delta = (5 * w / 12 * (span_ft * 12)**4) / (384 * E * sec["Ix"])
    else:
        P = Mu_kip_ft * 4 / span_ft
        delta = (P * 1000 * (span_ft * 12)**3) / (48 * E * sec["Ix"])
    delta_lim = span_ft * 12 / 360

    b_ok = phi_Mn >= Mu_kip_ft
    v_ok = phi_Vn >= Vu_kips
    d_ok = delta <= delta_lim

    return {
        "code": "AISC 360-22 LRFD",
        "clause": "F2 (flexure), G2 (shear), L360 (deflection)",
        "section": section, "Fy_ksi": Fy_ksi,
        "bending": {
            "Mp_kip_ft": round(Mp, 1),
            "Lp_ft": round(Lp, 2), "Lr_ft": round(Lr, 2),
            "Lb_ft": Lb_ft, "LTB_zone": ltb,
            "Mn_kip_ft": round(Mn, 1),
            "phi_Mn_kip_ft": round(phi_Mn, 1),
            "demand_kip_ft": Mu_kip_ft,
            "utilization": round(Mu_kip_ft / phi_Mn, 3),
            "status": "PASS" if b_ok else "FAIL",
        },
        "shear": {
            "Aw_in2": round(Aw, 3),
            "phi_Vn_kips": round(phi_Vn, 1),
            "demand_kips": Vu_kips,
            "utilization": round(Vu_kips / phi_Vn, 3),
            "status": "PASS" if v_ok else "FAIL",
        },
        "deflection": {
            "delta_in": round(delta, 3),
            "limit_L360_in": round(delta_lim, 3),
            "status": "PASS" if d_ok else "FAIL",
        },
        "overall": "PASS" if (b_ok and v_ok and d_ok) else "FAIL",
    }


def design_column_AISC(
    section: str,
    Pu_kips: float,
    KL_ft: float,
    Fy_ksi: float = 50.0,
) -> Dict[str, Any]:
    """AISC 360-22 LRFD Cl. E — compression member."""
    sec = AISC_SECTIONS.get(section)
    if not sec:
        return {"error": f"Section '{section}' not found."}
    phi_c = 0.90; E = 29000

    A = sec["A"]; ry = sec["ry"]
    KL_in = KL_ft * 12
    Fe = math.pi**2 * E / (KL_in / ry)**2

    if Fy_ksi / Fe <= 2.25:
        Fcr = (0.658 ** (Fy_ksi / Fe)) * Fy_ksi
    else:
        Fcr = 0.877 * Fe

    Pn = Fcr * A
    phi_Pn = phi_c * Pn
    ok = phi_Pn >= Pu_kips

    return {
        "code": "AISC 360-22 LRFD", "clause": "E3",
        "section": section, "Fy_ksi": Fy_ksi,
        "KL_over_r": round(KL_in / ry, 1),
        "Fe_ksi": round(Fe, 2),
        "Fcr_ksi": round(Fcr, 2),
        "Pn_kips": round(Pn, 1),
        "phi_Pn_kips": round(phi_Pn, 1),
        "demand_kips": Pu_kips,
        "utilization": round(Pu_kips / phi_Pn, 3),
        "status": "PASS" if ok else "FAIL",
        "overall": "PASS" if ok else "FAIL",
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION SELECTOR
# ══════════════════════════════════════════════════════════════════════════════

def select_beam_IS800(span_m: float, Md_kNm: float, Vd_kN: float, grade: str = "E250"):
    """Pick lightest IS section that passes all checks."""
    passed = []
    for name in IS_SECTIONS:
        r = design_beam_IS800(name, span_m, Md_kNm, Vd_kN, grade)
        if r.get("overall") == "PASS":
            passed.append({
                "section": name, "A_cm2": IS_SECTIONS[name]["A"],
                "bending_util": r["bending"]["utilization"],
                "shear_util": r["shear"]["utilization"],
                "deflection_util": round(r["deflection"]["delta_mm"] / r["deflection"]["limit_L300_mm"], 3),
            })
    if not passed:
        return {"error": "No suitable section found — increase section depth or reduce span."}
    passed.sort(key=lambda x: x["A_cm2"])
    return {"recommended": passed[0]["section"], "alternatives": passed[1:4], "all_passing": passed}


def get_section_properties(system: str = "IS"):
    """Return all sections in the database."""
    if system.upper() == "IS":
        return [{"name": k, **v} for k, v in IS_SECTIONS.items()]
    return [{"name": k, **v} for k, v in AISC_SECTIONS.items()]
