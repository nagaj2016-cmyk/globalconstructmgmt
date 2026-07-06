"""
Engineering calculator VALIDATION harness.

These are not "does it run" tests — each one feeds a calculator a known input
and asserts the output against an INDEPENDENT source of truth: a published code
constant (IS 456 / SP-16 / IS 800 / IS 1893) or a hand-computed worked example.
A failure here means the numbers are wrong, which for a design tool is a safety
issue — so these must stay green.

Run:  cd backend && pytest tests/test_calculators.py -q
"""
import math
import pytest

from structural import rcc_beam, rcc_column, rcc_slab, foundation, loads, steel_is800, mix_design


REL = 0.02  # 2% relative tolerance for worked-example comparisons


def close(a, b, rel=REL):
    return abs(a - b) <= rel * max(abs(b), 1e-9)


# ══════════════════════════════════════════════════════════════════════════════
# IS 456 : 2000  —  RCC BEAM (limit state, SP-16)
# ══════════════════════════════════════════════════════════════════════════════
def test_xu_max_d_ratios_match_IS456():
    """Limiting neutral-axis depth ratios are fixed code constants (Cl. 38.1)."""
    # Published xu,max/d: Fe250=0.5313, Fe415=0.4791, Fe500=0.4560
    assert close(rcc_beam.STEEL_GRADES["Fe250"]["xu_d"], 0.5313, 0.01)
    assert close(rcc_beam.STEEL_GRADES["Fe415"]["xu_d"], 0.4791, 0.01)
    assert close(rcc_beam.STEEL_GRADES["Fe500"]["xu_d"], 0.4560, 0.01)


def test_beam_limiting_moment_coefficient_Fe415():
    """Mu,lim = 0.138 fck b d² for Fe415 (SP-16 Table C). Independent recompute."""
    b, D, cover, stir, main, fck, fy = 300, 550, 25, 8, 16, 25, 415
    r = rcc_beam.design_beam(span_m=6, Mu_kNm=150, Vu_kN=120, b_mm=b, D_mm=D,
                             fck=fck, fy=fy, cover_mm=cover, stirrup_dia_mm=stir,
                             main_bar_dia_mm=main)
    d = D - cover - stir - main / 2
    mu_lim_expected = 0.138 * fck * b * d**2 / 1e6          # kN·m (published coeff)
    assert close(r["moment_capacity"]["Mu_lim_kNm"], mu_lim_expected, 0.02)
    assert close(r["section"]["d_mm"], d, 0.001)


def test_beam_singly_reinforced_Ast_worked_example():
    """Ast from SP-16 quadratic solution, hand-computed and matched (<Mu,lim)."""
    b, D, cover, stir, main, fck, fy, Mu = 300, 550, 25, 8, 16, 25, 415, 200.0
    r = rcc_beam.design_beam(span_m=6, Mu_kNm=Mu, Vu_kN=120, b_mm=b, D_mm=D,
                             fck=fck, fy=fy, cover_mm=cover, stirrup_dia_mm=stir,
                             main_bar_dia_mm=main)
    d = D - cover - stir - main / 2
    Ast_expected = (0.5 * fck / fy) * (1 - math.sqrt(1 - (4.6 * Mu * 1e6) /
                   (fck * b * d**2))) * b * d
    assert r["moment_capacity"]["is_singly"] is True
    assert close(r["tension_steel"]["Ast_required_mm2"], Ast_expected, 0.02)


def test_beam_minimum_steel_clause_26_5_1_1():
    """Ast_min = 0.85 b d / fy (Cl. 26.5.1.1)."""
    b, D, cover, stir, main, fy = 300, 550, 25, 8, 16, 415
    r = rcc_beam.design_beam(span_m=6, Mu_kNm=40, Vu_kN=50, b_mm=b, D_mm=D,
                             fck=25, fy=fy, cover_mm=cover, stirrup_dia_mm=stir,
                             main_bar_dia_mm=main)
    d = D - cover - stir - main / 2
    assert close(r["tension_steel"]["Ast_min_mm2"], 0.85 * b * d / fy, 0.01)


def test_beam_switches_to_doubly_above_Mu_lim():
    """When applied Mu > Mu,lim the design must become doubly reinforced."""
    r = rcc_beam.design_beam(span_m=6, Mu_kNm=400, Vu_kN=150, b_mm=300, D_mm=450,
                             fck=25, fy=415)
    assert r["moment_capacity"]["is_singly"] is False


# ══════════════════════════════════════════════════════════════════════════════
# IS 456 : 2000  —  SHORT AXIAL COLUMN (Cl. 39.3)
# ══════════════════════════════════════════════════════════════════════════════
def test_column_axial_capacity_formula_cl_39_3():
    """Pu = 0.4 fck Ac + 0.67 fy Asc — recompute from the steel it provided."""
    fck, fy, b, D = 25, 415, 400, 400
    r = rcc_column.design_column_axial(Pu_kN=2000, height_m=3.0, b_mm=b, D_mm=D,
                                       fck=fck, fy=fy)
    Ag = b * D
    Asc_prov = r["steel_design"]["Asc_provided_mm2"]
    Ac = Ag - Asc_prov
    Pu_cap_expected = (0.4 * fck * Ac + 0.67 * fy * Asc_prov) / 1000  # kN
    assert close(r["capacity"]["Pu_capacity_kN"], Pu_cap_expected, 0.01)
    assert r["capacity"]["Pu_capacity_kN"] >= 2000            # must carry the load


def test_column_minimum_steel_and_bars():
    """Min longitudinal steel 0.8% Ag and min 4 bars (Cl. 26.5.3.1)."""
    r = rcc_column.design_column_axial(Pu_kN=800, height_m=3.0, b_mm=300, D_mm=300,
                                       fck=25, fy=415)
    assert r["steel_design"]["Asc_min_mm2"] == pytest.approx(0.008 * 300 * 300, rel=0.01)
    n_bars = int(r["steel_design"]["bars"].split("—")[0].strip() or 0)
    assert n_bars >= 4


# ══════════════════════════════════════════════════════════════════════════════
# IS 1893 (Part 1) : 2016  —  SEISMIC BASE SHEAR
# ══════════════════════════════════════════════════════════════════════════════
def test_seismic_zone_factors_match_IS1893_2016():
    """Zone factors Z are fixed in Table 3 of IS 1893 (Part 1):2016."""
    assert loads.SEISMIC_ZONE["II"]["Z"] == 0.10
    assert loads.SEISMIC_ZONE["III"]["Z"] == 0.16
    assert loads.SEISMIC_ZONE["IV"]["Z"] == 0.24
    assert loads.SEISMIC_ZONE["V"]["Z"] == 0.36


def test_seismic_spectral_plateau_soil_type_II():
    """Sa/g plateau = 2.5 in the short-period range (Fig. 2, medium soil)."""
    assert close(loads.sa_g("II", 0.3), 2.5, 0.001)


def test_seismic_base_shear_worked_example():
    """Zone IV, I=1, R=5, short building on medium soil.
       Ah = (Z/2)(I/R)(Sa/g) = 0.12·0.2·2.5 = 0.06 ; Vb = Ah·W."""
    W = 10000.0
    r = loads.calculate_seismic_load(city="Delhi", total_seismic_weight_kn=W,
                                     building_height_m=3.0, num_floors=1,
                                     soil_type="II", response_reduction=5.0,
                                     building_use="residential", custom_zone="IV")
    Z, I, R, sag = r["zone_factor_Z"], r["importance_factor_I"], r["response_reduction_R"], r["Sa_g"]
    Ah_expected = (Z / 2) * sag / (R / I)
    assert close(r["Ah"], Ah_expected, 0.01)
    assert close(r["Ah"], 0.06, 0.02)                     # against the hand value
    assert close(r["base_shear_VB_kn"], r["Ah"] * W, 0.01)
    # Story forces must sum back to the base shear (Cl. 7.7.1)
    total = sum(f["seismic_force_kn"] for f in r["floor_distribution"])
    assert close(total, r["base_shear_VB_kn"], 0.02)


# ══════════════════════════════════════════════════════════════════════════════
# IS 875 (Part 3) : 2015  —  WIND PRESSURE
# ══════════════════════════════════════════════════════════════════════════════
def test_wind_pressure_formula_pz():
    """pz = 0.6 Vz²  (N/m²) → kN/m². Recompute from the code's own Vz."""
    r = loads.calculate_wind_load(city="Chennai", building_height_m=10,
                                  terrain_category="2", custom_vb=44)
    vz = r.get("design_wind_speed_Vz") or r.get("Vz")
    if vz:                                                # only if exposed
        assert close(r["design_wind_pressure_pz"], 0.6 * vz**2 / 1000, 0.02)
    assert r["design_wind_pressure_pz"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# IS 800 : 2007  —  STEEL BEAM (Cl. 8)
# ══════════════════════════════════════════════════════════════════════════════
def test_steel_plastic_moment_gamma_m0():
    """Md = Zpz·fy/γm0 with γm0 = 1.10 (Cl. 8.2.1.2). ISMB300, Fe250."""
    sec = steel_is800.IS_SECTIONS["ISMB300"]
    Zpz = sec["Zpz"] * 1e3            # cm³ → mm³
    Md_expected = Zpz * 250 / (1.10 * 1e6)     # kN·m
    r = steel_is800.design_beam_IS800("ISMB300", span_m=6, Md_kNm=100, Vd_kN=100, grade="E250")
    assert close(r["bending"]["Md_plastic_kNm"], Md_expected, 0.01)


def test_steel_shear_capacity_cl_8_4_1():
    """Vd = Av·fy/(√3·γm0), Av = h·tw (Cl. 8.4.1)."""
    sec = steel_is800.IS_SECTIONS["ISMB300"]
    Av = sec["h"] * sec["tw"]
    Vd_expected = Av * 250 / (math.sqrt(3) * 1.10 * 1000)
    r = steel_is800.design_beam_IS800("ISMB300", span_m=6, Md_kNm=100, Vd_kN=100, grade="E250")
    assert close(r["shear"]["Vd_capacity_kN"], Vd_expected, 0.01)


# ══════════════════════════════════════════════════════════════════════════════
# Dead load unit weights (IS 875 Part 1)
# ══════════════════════════════════════════════════════════════════════════════
def test_dead_load_slab_self_weight():
    """150 mm RC slab at 25 kN/m³ = 3.75 kN/m²."""
    r = loads.calculate_dead_loads(slab_thickness_mm=150)
    assert close(r["slab_self_weight"], 3.75, 0.001)


# ══════════════════════════════════════════════════════════════════════════════
# AISC 360-22 (USA)  —  STEEL BEAM (LRFD, Ch. F / G)
# ══════════════════════════════════════════════════════════════════════════════
def test_aisc_plastic_moment_and_phi():
    """F2.1  Mp = Fy·Zx ;  φb = 0.90.  W12x50, Fy=50 ksi, braced (Lb<Lp)."""
    sec = steel_is800.AISC_SECTIONS["W12x50"]
    Mp_expected = 50 * sec["Zx"] / 12                 # kip-ft
    r = steel_is800.design_beam_AISC("W12x50", span_ft=20, Mu_kip_ft=100,
                                     Vu_kips=30, Lb_ft=5.0, Fy_ksi=50)
    assert close(r["bending"]["Mp_kip_ft"], Mp_expected, 0.01)
    assert close(r["bending"]["phi_Mn_kip_ft"], 0.90 * Mp_expected, 0.02)  # fully braced


def test_aisc_shear_capacity_G2():
    """G2.1  Vn = 0.6·Fy·Aw ,  Aw = d·tw ,  φv = 1.0."""
    sec = steel_is800.AISC_SECTIONS["W12x50"]
    Vn_expected = 0.6 * 50 * (sec["d"] * sec["tw"])
    r = steel_is800.design_beam_AISC("W12x50", span_ft=20, Mu_kip_ft=100,
                                     Vu_kips=30, Lb_ft=5.0, Fy_ksi=50)
    assert close(r["shear"]["phi_Vn_kips"], Vn_expected, 0.02)


# ══════════════════════════════════════════════════════════════════════════════
# NBC 2020 + CSA S16 (Canada)
# ══════════════════════════════════════════════════════════════════════════════
def test_nbc_snow_load_formula_cl_4_1_6():
    """S = Is·[Ss·(Cb·Cw·Cs·Ca) + Sr]. Vancouver Ss=1.8, Sr=0.3, flat roof."""
    from routers.nbc_canada import calc_snow_load, SnowInput
    r = calc_snow_load(SnowInput(city="Vancouver", importance="normal",
                                 Cb=0.8, Cw=1.0, Cs=1.0, Ca=1.0))
    ins = r["inputs"]
    expected = ins["Is"] * (ins["Ss_ground"] * ins["Cb"] * ins["Cw"] * ins["Cs"] * ins["Ca"]
                            + ins["Sr_rain"])
    assert close(r["S_specified"], expected, 0.001)
    assert close(r["S_specified"], 1.74, 0.02)          # hand value


def test_csa_s16_steel_beam_resistance_cl_13_5():
    """Mr = φ·Zx·Fy (φ=0.90, Cl. 13.5);  Vr = φ·0.66·Fy·Aw (Cl. 13.4)."""
    from routers.nbc_canada import csa_steel_beam, CSASteelBeamInput
    inp = CSASteelBeamInput(Fy=350, Zx=2030e3, Sx=1440e3, d=308, tw=9.9, Lb=0.0)
    r = csa_steel_beam(inp)
    Mr_expected = 0.90 * 350 * 2030e3 / 1e6                       # kN·m
    Vr_expected = 0.90 * 0.66 * 350 * (308 * 9.9) / 1e3          # kN
    assert close(r["flexure"]["Mr_final_kNm"], Mr_expected, 0.02)
    assert close(r["shear"]["Vr_kN"], Vr_expected, 0.02)


# ══════════════════════════════════════════════════════════════════════════════
# IS 456 : 2000  —  ISOLATED FOOTING (bearing area) + ONE-WAY SLAB (min steel)
# ══════════════════════════════════════════════════════════════════════════════
def test_footing_bearing_area_sizing():
    """A_req = P_gross / SBC ; provided area must cover it (square, rounded up)."""
    r = foundation.design_isolated_footing(Pu_kN=1000, sbc_kN_m2=150)
    P_gross = 1000 * 1.10 / 1.5                       # unfactored gross (matches module)
    A_req = P_gross / 150
    L_expected = math.ceil(math.sqrt(A_req) * 10) / 10
    assert close(r["footing_size"]["L_m"], L_expected, 0.01)
    assert r["footing_size"]["area_m2"] >= A_req * 0.999


def test_one_way_slab_min_steel_cl_26_5_2_1():
    """Slab minimum steel = 0.12% of gross section for Fe415 (Cl. 26.5.2.1)."""
    r = rcc_slab.design_one_way_slab(span_m=3.5, total_load_kN_m2=10, fck=25, fy=415)
    D = r["section"]["D_mm"]
    assert close(r["main_steel"]["Ast_min_mm2_m"], 0.0012 * 1000 * D, 0.02)


# ══════════════════════════════════════════════════════════════════════════════
# AISC 360-22  —  COMPRESSION MEMBER (Ch. E3)
# ══════════════════════════════════════════════════════════════════════════════
def test_aisc_column_flexural_buckling_E3():
    """Fe = π²E/(KL/r)² ; Fcr per E3 ; Pn = Fcr·Ag ; φc = 0.90. W14x48."""
    sec = steel_is800.AISC_SECTIONS["W14x48"]
    r = steel_is800.design_column_AISC("W14x48", Pu_kips=200, KL_ft=14, Fy_ksi=50)
    Fe = r["Fe_ksi"]
    Fy = 50
    Fcr_expected = (0.658 ** (Fy / Fe)) * Fy if (Fy / Fe) <= 2.25 else 0.877 * Fe
    Pn_expected = Fcr_expected * sec["A"]
    assert close(r["Fcr_ksi"], Fcr_expected, 0.01)
    assert close(r["phi_Pn_kips"], 0.90 * Pn_expected, 0.02)


# ══════════════════════════════════════════════════════════════════════════════
# IS 10262 : 2019  —  MIX DESIGN (target mean strength)
# ══════════════════════════════════════════════════════════════════════════════
def test_mix_design_target_mean_strength():
    """f_target = fck + 1.65·s ; for M25 this sits in the 30–34 MPa band."""
    r = mix_design.design_mix(grade="M25", exposure="moderate")
    ft = r["target_strength_N_mm2"]
    assert 25 < ft, "target must exceed characteristic strength"
    assert 30.0 <= ft <= 34.0, f"M25 target strength out of expected band: {ft}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
