
from __future__ import annotations

import ast
import base64
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

APP_TITLE = "CUT method Bearing Capacity v8.5"

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / "CUT_Bearing_capacity_updated_v8.5.py"
MANUAL_FILE = BASE_DIR / "CUT_Bearing_Capacity_User_Manual_v3.pdf"
COULOMB_FILE = BASE_DIR / "CUT_K_Coulomb.py"
LOGO_FILE = BASE_DIR / "cut_logo.png"
BRAND_FILE = BASE_DIR / "Cut bearing capacity.png"
HOME_LOGO_FILE = BASE_DIR / "home.png"
HOME_URL = "https://cut-apps.streamlit.app/"

CUT_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/v7.1/CUT_Bearing_capacity_updated_v8.5.exe"
COULOMB_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/cut-k-coulomb-v2/CUT_K_Coulomb_v2.exe"

ABOUT_TEXT = """CUT_Bearing_capacity
Version: v8.5 (Program), v3 (Manual)
Author: Dr Lysandros Pantelidis, Cyprus University of Technology

Educational tool — no warranty. Use at your own risk. Free of charge."""

DISCLAIMER_TEXT = """Licensing
This program is copyrighted © 2026 Dr. Lysandros Pantelidis. It is distributed free of charge for academic, educational, and research purposes only.
Users may download, install, and employ the software provided that proper citation of the original source and relevant publications is made.
Modification, redistribution, commercial use, or incorporation into other software is strictly prohibited without the explicit written permission of the author.
All intellectual property rights relating to the program, its source code, algorithms, user interface, documentation, figures, and theoretical framework are fully retained by the copyright holder.

NO WARRANTY
THIS PROGRAM IS PROVIDED FREE OF CHARGE “AS IS”, WITHOUT ANY WARRANTY OF ANY KIND.
THE AUTHOR MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, OR ACCURACY OR RELIABILITY OF RESULTS.
THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH THE USER.

LIMITATION OF LIABILITY
IN NO EVENT SHALL THE AUTHOR OR THE CYPRUS UNIVERSITY OF TECHNOLOGY BE LIABLE FOR ANY DAMAGES WHATSOEVER, INCLUDING GENERAL, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, LOSS OF DATA, LOSS OF PROFITS, BUSINESS INTERRUPTION, OR ANY CLAIM BY A THIRD PARTY, ARISING FROM THE USE OR INABILITY TO USE THE PROGRAM, EVEN 1997-3 IF THE AUTHOR HAS BEEN 1997-3 ADVISED OF THE POSSIBILITY OF SUCH DAMAGES."""


@st.cache_resource
def load_core_functions(source_path) -> Dict[str, Any]:
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find {source_path} next to app.py")
    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=source_path)
    wanted = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    mod = ast.Module(body=wanted, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns: Dict[str, Any] = {"math": math}
    exec(compile(mod, source_path, "exec"), ns)
    return ns


core = load_core_functions(SOURCE_FILE)

compute_two_layer_equivalent = core["compute_two_layer_equivalent"]
compute_soil_compressibility_factors_raw = core["compute_soil_compressibility_factors"]
original_drained_factors = core["original_drained_factors"]
original_undrained_factors = core["original_undrained_factors"]
effective_surcharge_and_gamma = core["effective_surcharge_and_gamma"]
coulomb_Ka = core["coulomb_Ka"]
coulomb_Kp = core["coulomb_Kp"]
H_distance = core["H_distance"]
Hmax_distance = core["Hmax_distance"]
IB_over_B = core["IB_over_B"]
cyprus_shape_factors = core["cyprus_shape_factors"]
cyprus_depth_factors = core["cyprus_depth_factors"]
cyprus_inclination_factors = core["cyprus_inclination_factors"]
cyprus_seismic_factors = core["cyprus_seismic_factors"]
cyprus_w_factors = core["cyprus_w_factors"]
sc_rankine_active = core["sc_rankine_active"]
sc_rankine_passive = core["sc_rankine_passive"]
sc_influence_integral = core["sc_influence_integral"]


def robust_compute_soil_compressibility_factors(**kwargs):
    try:
        return compute_soil_compressibility_factors_raw(**kwargs)
    except ZeroDivisionError:
        eps = 1e-12
        c = float(kwargs["c"])
        phi_deg = float(kwargs["phi_deg"])
        Df_A = float(kwargs["Df_A"])
        Df_P = float(kwargs["Df_P"])
        B = float(kwargs["B"])
        f_cs = float(kwargs["f_cs"])
        footing_type = kwargs["footing_type"]
        mode = kwargs.get("mode", "edge")
        lambda3 = float(kwargs.get("lambda3", 0.5))

        phi = math.radians(phi_deg)
        c_cr = f_cs * c
        phi_cr = math.atan(f_cs * math.tan(phi))
        r_o = B / max(2.0 * math.cos(math.pi / 4.0 + phi / 2.0), eps)

        if abs(math.sin(phi_cr)) < eps:
            s_lg_tot = 0.0
        else:
            s_lg_tot = (r_o / math.sin(phi_cr)) * (
                math.exp((math.pi / 2.0) * math.tan(phi_cr)) - 1.0
            )

        H_cr = (
            B
            / max(2.0 * math.cos(math.pi / 4.0 + phi_cr / 2.0), eps)
            * math.exp((math.pi / 4.0 - phi_cr / 2.0) * math.tan(phi_cr))
        )
        H_o = (
            B
            / max(2.0 * math.cos(math.pi / 4.0 + phi / 2.0), eps)
            * math.exp((math.pi / 4.0 - phi / 2.0) * math.tan(phi))
        )
        H_cr = max(H_cr, eps)
        H_o = max(H_o, eps)

        f_ep = 0.16 + 1.5 * f_cs - 0.66 * f_cs**2
        if mode == "local":
            sin_phi = math.sin(phi)
            sin_45_minus_phi2 = math.sin(math.radians(45.0) - phi / 2.0)
            Slg_tot3 = 0.0 if abs(sin_phi) < eps else (r_o / sin_phi) * (math.exp((math.pi / 2.0) * math.tan(phi)) - 1.0)
            S3 = 0.0 if abs(sin_45_minus_phi2) < eps else r_o * math.exp((math.pi / 2.0) * math.tan(phi)) + Df_P / sin_45_minus_phi2
            denom_loc = max(Slg_tot3 + S3, eps)
            phi_waA = phi
            c_waA = c
            phi_waP = (phi * Slg_tot3 + 0.5 * (phi + phi_cr) * S3 * lambda3) / denom_loc
            c_waP = (c * Slg_tot3 + 0.5 * c * S3 * lambda3) / denom_loc
            K_IA_wa = (1.0 - math.sin(f_ep * phi_waA)) / max(1.0 + math.sin(f_ep * phi_waA), eps)
            K_IP_wa = (1.0 + math.sin(f_ep * phi_waP)) / max(1.0 - math.sin(f_ep * phi_waP), eps)
        else:
            s_lg_A = (r_o / math.sin(phi_cr)) * (math.exp((math.pi / 4.0 - phi_cr / 2.0) * math.tan(phi_cr)) - 1.0)
            denom = max(r_o + s_lg_A, eps)
            phi_waA = (r_o * phi + s_lg_A * (phi + phi_cr) / 2.0) / denom
            c_waA = (r_o * c + s_lg_A * (c + 0.0) / 2.0) / denom
            K_IA_wa = (1.0 - math.sin(f_ep * phi_waA)) / max(1.0 + math.sin(f_ep * phi_waA), eps)
            K_IP_wa = (1.0 + math.sin(f_ep * phi_cr)) / max(1.0 - math.sin(f_ep * phi_cr), eps)

        K_A = sc_rankine_active(phi)
        K_P = sc_rankine_passive(phi)
        I_I_phi = sc_influence_integral(phi, footing_type, B)
        sqrt_part = max(math.sqrt(max(K_IA_wa, eps)) * (math.sqrt(max(K_A, eps)) + math.sqrt(max(K_P, eps))), eps)

        c_c = float("nan") if abs(c) < eps else (c_waA / c) * (K_A / sqrt_part) * (H_cr / H_o)
        den_cg = max(1.0 - K_P / max(K_A, eps), eps)
        c_gamma = ((1.0 - K_IP_wa / max(K_IA_wa, eps)) / den_cg) * (H_cr / H_o) ** 2
        cq_num = (Df_A / max(Df_P, eps)) * (1.0 - I_I_phi / H_cr) - (K_IP_wa / max(K_IA_wa, eps))
        cq_den = (Df_A / max(Df_P, eps)) * (1.0 - I_I_phi / H_cr) - (K_P / max(K_A, eps))
        if abs(cq_den) < eps:
            cq_den = eps if cq_den >= 0 else -eps
        c_q = (H_cr / H_o) * (cq_num / cq_den)
        return {
            "c_c": c_c,
            "c_q": c_q,
            "c_gamma": c_gamma,
            "c_cr": c_cr,
            "phi_cr_deg": math.degrees(phi_cr),
        }


def cyprus_qult_with_params(c_val: float, phi_deg: float, kv_override: float, kh_override: float, params: Dict[str, Any], return_factors: bool = False):
    Beff = params["Beff"]
    Leff = params["Leff"]
    Df = params["Df"]
    DfA = params["DfA"]
    DfP = params["DfP"]
    Dw = params["Dw"]
    psi = params["psi"]
    gd = params["gd"]
    gs = params["gs"]
    gw = params["gw"]
    alpha = params["alpha"]
    beta_en = params["beta_en"]
    theta = params["theta"]
    source_key = params["source_key"]
    KA_user = params["KA_user"]
    KP_user = params["KP_user"]
    betaA = params["betaA"]
    betaP = params["betaP"]
    delta_used = params["delta_used"]
    res_pf = params["res_pf"]
    use_reinf = params["use_reinf"]
    n_layers = params["n_layers"]
    p_tens = params["p_tens"]
    footing_type = params["footing_type"]
    is_circular = params.get("is_circular", False)
    failure_mode = params.get("failure_mode", "General shear")
    f_cs = params.get("f_cs", 1.0)
    lambda3 = params.get("lambda3", 0.5)

    kv = kv_override
    kh = kh_override
    gd_eff = gd * (1.0 + kv)
    gs_eff = gs * (1.0 + kv)

    if source_key == "KAKP":
        KA_used = KA_user
        KP_used = KP_user
    elif source_key == "B_AP":
        KA_used = coulomb_Ka(phi_deg, betaA, 0.0)
        KP_used = coulomb_Kp(phi_deg, betaP, 0.0)
    else:
        KA_used = coulomb_Ka(phi_deg, beta_en, 0.0)
        KP_used = coulomb_Kp(phi_deg, -beta_en, 0.0)

    H = H_distance(Beff, phi_deg)
    rHB = H / max(Beff, 1e-12)
    invJ = 1.0 / max(IB_over_B(phi_deg, footing_type), 1e-12)
    df_ratio = DfA / max(DfP, 1e-12)

    Nq_c = df_ratio + (KP_used / max(KA_used, 1e-12) - df_ratio) * rHB * invJ
    Ng_c = (KP_used - KA_used) / max(KA_used, 1e-12) * (rHB ** 2) * invJ
    Nc_c = 2.0 * (math.sqrt(KP_used) + math.sqrt(KA_used)) / max(KA_used, 1e-12) * rHB * invJ
    Nr_c = invJ / max(KA_used, 1e-12)

    sc_c, sq_c, sg_c = cyprus_shape_factors(phi_deg, Beff, Leff)
    if is_circular:
        circ_factor = 4.0 / math.pi
        sc_c *= circ_factor
        sq_c *= circ_factor
        sg_c *= circ_factor

    dc_c, dq_c, dg_c, _ = cyprus_depth_factors(phi_deg, Beff, Df, psi)
    dr_c = dc_c
    ic_c, iq_c, ig_c = cyprus_inclination_factors(phi_deg, delta_used, Beff, Leff, theta, psi)

    phi_rad = math.radians(phi_deg)
    if abs(phi_deg) <= 1e-12:
        bq_c = bg_c = bc_c = 1.0
    else:
        a = math.radians(alpha)
        Nc_approx = (math.exp(math.pi * math.tan(phi_rad)) * (math.tan(math.pi / 4 + phi_rad / 2) ** 2) - 1.0) / (math.tan(phi_rad) + 1e-12)
        bq_c = (1.0 - a * math.tan(phi_rad)) ** 2
        bg_c = bq_c
        bc_c = bq_c - (1.0 - bq_c) / (Nc_approx * math.tan(phi_rad) + 1e-12)

    gc_c = gq_c = gg_c = 1.0

    if failure_mode in ("Local shear", "Punching shear"):
        mode = "local" if failure_mode == "Local shear" else "edge"
        comp = robust_compute_soil_compressibility_factors(
            c=c_val, phi_deg=phi_deg, gamma=gd, Df=Df, B=Beff, L=Leff,
            f_cs=f_cs, footing_type=footing_type, Df_A=DfA, Df_P=DfP, mode=mode, lambda3=lambda3,
        )
        cc_factor = comp["c_c"]
        cq_factor = comp["c_q"]
        cg_factor = comp["c_gamma"]
        failure_mode_short = "Local" if failure_mode == "Local shear" else "Punching"
    else:
        cc_factor = cq_factor = cg_factor = 1.0
        failure_mode_short = "General"

    if kh != 0.0:
        v_loc = cyprus_depth_factors(phi_deg, Beff, Df, psi)[0]
        Hmax_star_local = Hmax_distance(Beff, phi_deg) * v_loc
        f = max(0.0, min(1.0, (Df + Hmax_star_local - Dw) / max(Hmax_star_local, 1e-12)))
        geff_tmp = (1.0 - f) * gd_eff + f * gs_eff
        denom = max(geff_tmp * max(Hmax_star_local, 1e-12), 1e-12)
        kh_lim = math.tan(math.radians(phi_deg)) + (c_val / denom)
        ec_c, eq_c, eg_c = cyprus_seismic_factors(kh, kh_lim)
    else:
        kh_lim = 0.0
        ec_c = eq_c = eg_c = 1.0

    q_total = gd_eff * Df
    gamma_total = gd_eff
    v_loc = cyprus_depth_factors(phi_deg, Beff, Df, psi)[0]
    Hstar_local = H_distance(Beff, phi_deg) * v_loc
    _, geff_cyp_local = effective_surcharge_and_gamma(Df, Beff, Dw, gd_eff, gs_eff, gw)
    wc, wq, wy = cyprus_w_factors(Dw, Df, Hstar_local, geff_cyp_local, gd_eff)

    term_r_c = (n_layers * p_tens / Beff) * Nr_c if use_reinf and n_layers > 0.0 and p_tens > 0.0 and Beff > 0.0 else 0.0
    term_c_c = (c_val * cc_factor * Nc_c * bc_c * dc_c * gc_c * ic_c * sc_c * ec_c * wc) / max(res_pf, 1e-12)
    term_q_c = (q_total * cq_factor * wq * Nq_c * bq_c * dq_c * gq_c * iq_c * sq_c * eq_c) / max(res_pf, 1e-12)
    term_g_c = (0.5 * gamma_total * cg_factor * wy * Beff * Ng_c * bg_c * dg_c * gg_c * ig_c * sg_c * eg_c) / max(res_pf, 1e-12)
    qult_c = term_c_c + term_q_c + term_g_c + term_r_c

    if return_factors:
        Hstar = H * cyprus_depth_factors(phi_deg, Beff, Df, psi)[0]
        Hmax_star = Hmax_distance(Beff, phi_deg) * cyprus_depth_factors(phi_deg, Beff, Df, psi)[0]
        return qult_c, {
            "Nc": Nc_c, "Nq": Nq_c, "Nγ": Ng_c, "Nr (reinforcement)": Nr_c,
            "bc": bc_c, "bq": bq_c, "bγ": bg_c,
            "dc": dc_c, "dq": dq_c, "dγ": dg_c, "dr": dr_c,
            "gc": gc_c, "gq": gq_c, "gγ": gg_c,
            "ic": ic_c, "iq": iq_c, "iγ": ig_c,
            "sc": sc_c, "sq": sq_c, "sγ": sg_c,
            "wc": wc, "wq": wq, "wγ": wy,
            "εc": ec_c, "εq": eq_c, "εγ": eg_c, "k_h,lim": kh_lim,
            "cc": cc_factor, "cq": cq_factor, "cγ": cg_factor,
            "KA used": KA_used, "KP used": KP_used,
            "H*": Hstar, "H* max": Hmax_star,
            "q_ult": qult_c, "RN": qult_c * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff),
            "RN/N": None, "Failure mode": failure_mode_short,
            "term_c": term_c_c, "term_q": term_q_c, "term_g": term_g_c, "term_r": term_r_c,
        }
    return qult_c


def compute_all(inputs: Dict[str, Any]) -> Dict[str, Any]:
    Beff = float(inputs["Beff"])
    Leff = float(inputs["Leff"])
    is_circular = bool(inputs["is_circular"])
    if is_circular:
        Leff = Beff

    Df = float(inputs["Df"])
    DfA = float(inputs["DfA"])
    DfP = Df
    Dw = float(inputs["Dw"])
    soil_mode = inputs["soil_layers"]

    if soil_mode == "1 layer":
        c_val = float(inputs["coh"])
        phi = float(inputs["phi"])
        gd = float(inputs["gamma_dry"])
        psi = float(inputs["psi1"])
        eq_info = {"mode": "1_layer", "ceq": c_val, "phi_eq_deg": phi, "gamma_eq": gd, "regime": "single_layer_input", "I1": 0.0, "I2": 0.0}
    else:
        eq_info = compute_two_layer_equivalent(
            B=Beff, DfA=DfA, DfP=DfP,
            c1=float(inputs["c1"]), phi1_deg=float(inputs["phi1"]), gamma1=float(inputs["gamma1_layer"]), H1=float(inputs["H1_layer"]),
            c2=float(inputs["c2"]), phi2_deg=float(inputs["phi2"]), gamma2=float(inputs["gamma2_layer"]),
        )
        c_val = float(eq_info["ceq"])
        phi = float(eq_info["phi_eq_deg"])
        gd = float(eq_info["gamma_eq"])
        psi1 = float(inputs["psi1"])
        psi2 = float(inputs["psi2"])
        I1 = float(eq_info.get("I1", 0.0))
        I2 = float(eq_info.get("I2", 0.0))
        psi = psi1 if abs(I1 + I2) < 1e-12 else (psi1 * I1 + psi2 * I2) / (I1 + I2)

    gs = float(inputs["gamma_sat"] if soil_mode == "1 layer" else (inputs["gamma_sat1_layer"] if eq_info.get("regime") == "homogeneous_layer_1" else 0.5 * (float(inputs["gamma_sat1_layer"]) + float(inputs["gamma_sat2_layer"]))))
    gw = float(inputs["gamma_w"])
    kv = float(inputs["kv"])
    kh = float(inputs["kh"])
    gd_eff = gd * (1.0 + kv)
    gs_eff = gs * (1.0 + kv)

    Nn = float(inputs["N"])
    alpha = float(inputs["alpha"])
    res_pf = max(float(inputs["res_factor"]), 1e-12)
    beta_en = float(inputs["beta_en"])
    theta = float(inputs["theta"])
    khlim_in = inputs["khlim"]
    use_reinf = bool(inputs["use_reinf"])
    n_layers = max(0.0, float(inputs["n_layers"]))
    p_tens = max(0.0, float(inputs["p_tens"]))

    if inputs["use_delta"]:
        delta_used = abs(float(inputs["delta_in"]))
        Tt = Nn * math.tan(math.radians(delta_used))
    else:
        Tt = float(inputs["T"])
        delta_used = math.degrees(math.atan(Tt / Nn)) if abs(Nn) > 1e-12 else 0.0

    failure_mode = inputs["failure_mode"]
    footing_type = inputs["footing_type"]
    f_cs = float(inputs["fcs"]) if failure_mode in ("Local shear", "Punching shear") else 1.0
    lambda3 = float(inputs["lambda3"]) if failure_mode == "Local shear" else 0.5
    if f_cs >= 0.80:
        failure_mode = "General shear"
        f_cs = 1.0

    if failure_mode in ("Local shear", "Punching shear"):
        c_en_default = f_cs * c_val
        phi_en_default = math.degrees(math.atan(f_cs * math.tan(math.radians(phi))))
        comp = robust_compute_soil_compressibility_factors(
            c=c_val, phi_deg=phi, gamma=gd, Df=Df, B=Beff, L=Leff, f_cs=f_cs, footing_type=footing_type, Df_A=DfA, Df_P=DfP,
            mode="local" if failure_mode == "Local shear" else "edge", lambda3=lambda3,
        )
        cc_factor, cq_factor, cg_factor = comp["c_c"], comp["c_q"], comp["c_gamma"]
        mob_smf = f_cs
        mob_c = c_en_default
        mob_phi = phi_en_default
        failure_mode_short = "Local" if failure_mode == "Local shear" else "Punching"
    else:
        c_en_default = c_val
        phi_en_default = phi
        cc_factor = cq_factor = cg_factor = 1.0
        mob_smf = 1.0
        mob_c = c_val
        mob_phi = phi
        failure_mode_short = "General"

    Aeff = Beff * Leff
    qeff_en, geff_en = effective_surcharge_and_gamma(Df, Beff, Dw, gd, gs, gw)

    def compute_en_results(c_strength: float, phi_strength: float) -> Dict[str, Any]:
        undrained_local = abs(phi_strength) <= 1e-6
        if undrained_local:
            of_u = original_undrained_factors(alpha, beta_en, Beff, Leff, Df, Tt, Aeff, c_strength)
            Nc_l, Nq_l, Ng_l = (math.pi + 2.0), 1.0, 0.0
            bc_l, bq_l, bg_l = of_u["bcu"], 1.0, 1.0
            dc_l, dq_l, dg_l = of_u["dcu"], 1.0, 1.0
            gc_l, gq_l, gg_l = of_u["gcu"], 1.0, 1.0
            ic_l, iq_l, ig_l = of_u["icu"], 1.0, 1.0
            sc_l, sq_l, sg_l = of_u["scu"], 1.0, 1.0
        else:
            of = original_drained_factors(phi_strength, alpha, beta_en, Beff, Leff, Df, Tt, Nn, theta)
            Nc_l, Nq_l, Ng_l = of["Nc"], of["Nq"], of["Ng"]
            bc_l, bq_l, bg_l = of["bc"], of["bq"], of["bg"]
            dc_l, dq_l, dg_l = of["dc"], of["dq"], of["dg"]
            gc_l, gq_l, gg_l = of["gc"], of["gq"], of["gg"]
            ic_l, iq_l, ig_l = of["ic"], of["iq"], of["ig"]
            sc_l, sq_l, sg_l = of["sc"], of["sq"], of["sg"]
        term_c_l = (c_strength * Nc_l * bc_l * dc_l * gc_l * ic_l * sc_l) / res_pf
        term_q_l = (qeff_en * Nq_l * bq_l * dq_l * gq_l * iq_l * sq_l) / res_pf
        term_g_l = 0.0 if undrained_local else (0.5 * geff_en * Beff * Ng_l * bg_l * dg_l * gg_l * ig_l * sg_l) / res_pf
        qult_l = term_c_l + term_q_l + term_g_l
        return {"undrained": undrained_local, "Nc": Nc_l, "Nq": Nq_l, "Nγ": Ng_l, "bc": bc_l, "bq": bq_l, "bγ": bg_l,
                "dc": dc_l, "dq": dq_l, "dγ": dg_l, "gc": gc_l, "gq": gq_l, "gγ": gg_l, "ic": ic_l, "iq": iq_l, "iγ": ig_l,
                "sc": sc_l, "sq": sq_l, "sγ": sg_l, "term_c": term_c_l, "term_q": term_q_l, "term_g": term_g_l, "qult": qult_l}

    # Base EN 1997-3 result before special handling
    en_base = compute_en_results(c_en_default, phi_en_default)

    if en_base is not None:
        if "qult" in en_base:
            en_base["q_ult"] = en_base["qult"]
        RN_tmp = en_base["qult"] * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff)
        en_base["RN"] = RN_tmp
        en_base["RN/N"] = RN_tmp / Nn if Nn > 0 else None

    source_key = inputs["k_source"]
    if source_key == "KAKP":
        KA_used = float(inputs["KA_user"])
        KP_used = float(inputs["KP_user"])
        betaA = betaP = 0.0
    elif source_key == "B_AP":
        betaA = float(inputs["betaA"])
        betaP = float(inputs["betaP"])
        KA_used = coulomb_Ka(phi, betaA, 0.0)
        KP_used = coulomb_Kp(phi, betaP, 0.0)
    else:
        betaA = beta_en
        betaP = -beta_en
        KA_used = coulomb_Ka(phi, betaA, 0.0)
        KP_used = coulomb_Kp(phi, betaP, 0.0)

    params = dict(Beff=Beff, Leff=Leff, Df=Df, DfA=DfA, DfP=DfP, Dw=Dw, psi=psi, gd=gd, gs=gs, gw=gw,
                  alpha=alpha, beta_en=beta_en, theta=theta, source_key=source_key, KA_user=KA_used if source_key == "KAKP" else 0.0,
                  KP_user=KP_used if source_key == "KAKP" else 0.0, betaA=betaA, betaP=betaP, delta_used=delta_used, res_pf=res_pf,
                  use_reinf=use_reinf, n_layers=n_layers, p_tens=p_tens, footing_type=footing_type, is_circular=is_circular,
                  failure_mode=failure_mode, f_cs=f_cs, lambda3=lambda3)

    qult_c, cut_factors = cyprus_qult_with_params(c_val, phi, kv, kh, params, return_factors=True)
    RN_cut = qult_c * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff)


    target_qu = float(f"{qult_c:.3f}")

    def qu_smf(smf: float):
        c_m = smf * c_val
        phi_m = math.degrees(math.atan(smf * math.tan(math.radians(phi))))
        qu = cyprus_qult_with_params(c_m, phi_m, 0, 0, params)
        return float(f"{qu:.3f}"), c_m, phi_m, qu

    def qu_smf_safe(smf: float):
        try:
            return qu_smf(max(0.0, smf))
        except ZeroDivisionError:
            return None
        except Exception:
            return None

    def refine(lo: float, hi: float, step: float):
        best = None
        x = hi
        while x >= lo - 1e-12:
            out = qu_smf_safe(x)
            if out is not None:
                qu_r, cm, phim, qu_val = out
                err = abs(qu_r - target_qu)
                if (best is None) or (err < best[0] - 1e-12) or (abs(err - best[0]) < 1e-12 and x > best[1]):
                    best = (err, x, cm, phim, qu_val, qu_r)
            x = round(x - step, 10)

        if best is None:
            # fallback to the upper bound if everything failed
            out = qu_smf(max(0.0, hi))
            qu_r, cm, phim, qu_val = out
            best = (abs(qu_r - target_qu), hi, cm, phim, qu_val, qu_r)

        best_smf = best[1]
        return best, max(0.0, best_smf - step), min(1.0, best_smf + step)

    # coarse bracketing search, like the desktop logic
    bracket = None
    prev_smf = 1.0
    prev_out = qu_smf_safe(prev_smf)
    prev_diff = None if prev_out is None else (prev_out[0] - target_qu)

    smf = 0.9
    while smf >= -1e-12:
        out = qu_smf_safe(max(0.0, smf))
        if out is not None:
            diff = out[0] - target_qu
            if prev_diff is not None and diff * prev_diff <= 0:
                bracket = (prev_smf, max(0.0, smf))
                break
            prev_smf = max(0.0, smf)
            prev_diff = diff
        smf = round(smf - 0.1, 10)

    if bracket is None:
        best = None
        smf = 1.0
        while smf >= -1e-12:
            out = qu_smf_safe(max(0.0, smf))
            if out is not None:
                qu_r, cm_best, phim_best, qu_best = out
                err = abs(qu_r - target_qu)
                if (best is None) or (err < best[0] - 1e-12) or (abs(err - best[0]) < 1e-12 and smf > best[1]):
                    best = (err, max(0.0, smf), cm_best, phim_best, qu_best, qu_r)
            smf = round(smf - 0.00001, 10)

        if best is None:
            raise ZeroDivisionError("Mobilized-strength search failed for this case.")

        _, smf_best, cm_best, phim_best, qu_best, qu_r_best = best
    else:
        hi, lo = bracket
        best01, lo1, hi1 = refine(min(lo, hi), max(lo, hi), 0.01)
        best001, lo2, hi2 = refine(lo1, hi1, 0.00001)
        _, smf_best, cm_best, phim_best, qu_best, qu_r_best = best001

    qu_full, mob = cyprus_qult_with_params(
        cm_best, phim_best, 0, 0, params, return_factors=True
    )
    
    RN_mob = qu_full * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff)

    en_special_case = (soil_mode == "2 layers") or (abs(kh) > 1e-12) or (abs(kv) > 1e-12)
    en_special_allowed = bool(inputs.get("allow_en_special", False))
    if en_special_case and not en_special_allowed:
        en_out = None
        en_status = "disabled"
        en_comment = "n/a"
    elif en_special_case and en_special_allowed:
        if failure_mode in ("Local shear", "Punching shear"):
            en_c = f_cs * cm_best
            en_phi = math.degrees(math.atan(f_cs * math.tan(math.radians(phim_best))))
        else:
            en_c = cm_best
            en_phi = phim_best
        en_out = compute_en_results(en_c, en_phi)
        if en_out is not None:
            if "qult" in en_out:
                en_out["q_ult"] = en_out["qult"]
            RN_tmp = en_out["qult"] * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff)
            en_out["RN"] = RN_tmp
            en_out["RN/N"] = RN_tmp / Nn if Nn > 0 else None
        en_status = "via c_m, φ_m"
        en_comment = "via c_m,φ_m"
    else:
        en_out = en_base
        en_status = "standard"
        en_comment = "via strength"

    RN_en = None if en_out is None else en_out["qult"] * (math.pi * Beff * Beff / 4.0 if is_circular else Beff * Leff)

    cut_factors["RN/N"] = RN_cut / Nn if Nn > 0 else None
    mob["RN/N"] = RN_mob / Nn if Nn > 0 else None

    return {
        "Summary": {
            "EN 1997-3 status": en_status,
            "q_ult EN 1997-3 (kPa)": None if en_out is None else en_out["qult"],
            "q_ult CUT method (kPa)": qult_c,
            "q_ult Mobilized shear strength static (kPa)": qu_full,
            "R_N EN 1997-3 (kN)": RN_en,
            "R_N CUT method (kN)": RN_cut,
            "R_N Mobilized shear strength static (kN)": RN_mob,
            "Safety ratio EN 1997-3 (R_N/N)": None if (RN_en is None or Nn <= 0) else RN_en / Nn,
            "Safety ratio CUT method (R_N/N)": RN_cut / Nn if Nn > 0 else None,
            "Safety ratio Mobilized shear strength static (R_N/N)": RN_mob / Nn if Nn > 0 else None,
        },
        "EN 1997-3": {"status": en_status, "compressibility basis": en_comment, **({} if en_out is None else en_out)},
        "CUT method": cut_factors,
        "Mobilized shear strength of soil": {"SMF": smf_best, "c_m (kPa)": cm_best, "φ_m (deg)": phim_best, **mob},
        "equivalent_soil": {"c_eq (kPa)": c_val,"φ_eq (deg)": phi,"γ_eq (kN/m³)": gd,"ψ_eq (deg)": psi,"regime": eq_info.get("regime", "-"),"qu_two_layer": eq_info.get("qu_two_layer", None)},
        "eq_info": eq_info,
    }


def fmt_val(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return "n/a"
        av = abs(float(v))
        if av >= 1000:
            return f"{float(v):.2f}"
        return f"{float(v):.3f}"
    return str(v)


def build_summary_table(results: Dict[str, Any]) -> pd.DataFrame:
    summary = results["Summary"]

    data = {
        "q_ult (kPa)": [
            summary.get("q_ult EN 1997-3 (kPa)"),
            summary.get("q_ult CUT method (kPa)"),
            summary.get("q_ult Mobilized shear strength static (kPa)")
        ],
        "R_N (kN)": [
            summary.get("R_N EN 1997-3 (kN)"),
            summary.get("R_N CUT method (kN)"),
            summary.get("R_N Mobilized shear strength static (kN)")
        ],
        "R_N/N": [
            summary.get("Safety ratio EN 1997-3 (R_N/N)"),
            summary.get("Safety ratio CUT method (R_N/N)"),
            summary.get("Safety ratio Mobilized shear strength static (R_N/N)")
        ]
    }

    df = pd.DataFrame(data, index=["EN 1997-3", "CUT method", "Mobilized"]).T

    df = df.reset_index().rename(columns={"index": "Parameter"})

    return df


def build_method_comparison_table(results: Dict[str, Any]) -> pd.DataFrame:
    en = results.get("EN 1997-3", {}) or {}
    cut = results.get("CUT method", {}) or {}
    mob = results.get("Mobilized shear strength of soil", {}) or {}

    ordered_keys = [
        "Failure mode",
        "undrained",
        "Nc", "Nq", "Nγ", "Nr (reinforcement)",
        "bc", "bq", "bγ",
        "compressibility basis", "cc", "cq", "cγ",
        "dc", "dq", "dγ", "dr",
        "gc", "gq", "gγ",
        "ic", "iq", "iγ",
        "sc", "sq", "sγ",
        "wc", "wq", "wγ",
        "εc", "εq", "εγ",
        "k_h,lim",
        "KA used", "KP used",
        "H*", "H* max",
        "SMF", "c_m (kPa)", "φ_m (deg)",
        "term_c", "term_q", "term_g", "term_r",
        "q_ult",
        "RN", "RN/N",
    ]

    label_map = {
        "RN": "R_N",
        "RN/N": "R_N/N"
    }

    display_keys = [label_map.get(k, k) for k in ordered_keys]

    df = pd.DataFrame({
        "Parameter": display_keys,
        "EN 1997-3": [fmt_val(en.get(k)) for k in ordered_keys],
        "CUT method": [fmt_val(cut.get(k)) for k in ordered_keys],
        "Mobilized shear strength of soil": [fmt_val(mob.get(k)) for k in ordered_keys],
    })

    return df



def image_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "image/png" if suffix == "png" else f"image/{suffix}"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def sidebar_home_link(path: Path, url: str) -> None:
    data_uri = image_to_data_uri(path)
    if data_uri:
        html_block = f"""
        <div style="text-align:center; margin-bottom: 0.75rem;">
            <a href="{url}" target="_blank" style="display:inline-block; width:100%; max-width:220px; padding:8px; border:1px solid #cfd8e3; border-radius:12px; background:#ffffff; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <img src="{data_uri}" alt="CUT Apps Home" style="width:100%; height:auto; border-radius:8px; display:block;">
            </a>
        </div>
        """
        st.markdown(html_block, unsafe_allow_html=True)
    else:
        st.link_button("🏠 CUT Apps Home", url, use_container_width=True)


def build_inputs_table(inputs: Dict[str, Any]) -> pd.DataFrame:
    rows = [{"Parameter": key, "Value": fmt_val(value)} for key, value in inputs.items()]
    return pd.DataFrame(rows)


def build_report_html(inputs: Dict[str, Any], results: Dict[str, Any]) -> str:
    summary_df = build_summary_table(results)
    comparison_df = build_method_comparison_table(results)
    eq_df = pd.DataFrame({
        "Parameter": list(results["equivalent_soil"].keys()),
        "Value": [fmt_val(v) for v in results["equivalent_soil"].values()],
    })
    input_df = build_inputs_table(inputs)

    def df_to_html(df: pd.DataFrame, summary: bool = False) -> str:
        df2 = df.copy()
        if summary:
            for col in df2.columns:
                if col != "Parameter":
                    df2[col] = pd.to_numeric(df2[col], errors="coerce").map(
                        lambda x: "n/a" if pd.isna(x) else f"{x:.2f}"
                    )
        return df2.to_html(index=False, border=0, classes="report-table", justify="left", escape=False)

    logo_uri = image_to_data_uri(Path(LOGO_FILE))
    home_uri = image_to_data_uri(HOME_LOGO_FILE)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    logo_html = ""
    if logo_uri:
        logo_html += f'<img src="{logo_uri}" alt="CUT logo" style="height:72px; margin-right:16px;">'
    if home_uri:
        logo_html += f'<img src="{home_uri}" alt="CUT Apps Home" style="height:72px;">'

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CUT Bearing Capacity Report</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 32px; color: #132238; }}
    h1, h2, h3 {{ color: #0e4f8a; margin-bottom: 8px; }}
    .header {{ display:flex; align-items:center; justify-content:space-between; border-bottom:2px solid #d9e6f2; padding-bottom:16px; margin-bottom:24px; }}
    .meta {{ color:#456; font-size:14px; }}
    .logos {{ display:flex; align-items:center; gap:12px; }}
    .cards {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin:20px 0; }}
    .card {{ border:1px solid #d9e6f2; border-radius:12px; padding:14px 16px; background:#f8fbff; }}
    .card .label {{ font-size:13px; color:#5b7288; margin-bottom:6px; }}
    .card .value {{ font-size:22px; font-weight:700; color:#0f2f57; }}
    .section {{ margin-top:28px; }}
    .report-table {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }}
    .report-table th, .report-table td {{ border:1px solid #d7e3ee; padding:8px 10px; text-align:left; vertical-align:top; }}
    .report-table th {{ background:#eef5fb; }}
    .note {{ margin-top:20px; padding:12px 14px; background:#fafcff; border-left:4px solid #8db7de; white-space:pre-wrap; }}
    @media print {{
      body {{ margin: 14mm; }}
      .card .value {{ font-size:18px; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>CUT Bearing Capacity Report</h1>
      <div class="meta">{timestamp}<br>{APP_TITLE}</div>
    </div>
    <div class="logos">{logo_html}</div>
  </div>

  <div class="cards">
    <div class="card">
      <div class="label">EN 1997-3 q_ult (kPa)</div>
      <div class="value">{fmt_val(results["Summary"]["q_ult EN 1997-3 (kPa)"])}</div>
    </div>
    <div class="card">
      <div class="label">CUT method q_ult (kPa)</div>
      <div class="value">{fmt_val(results["Summary"]["q_ult CUT method (kPa)"])}</div>
    </div>
    <div class="card">
      <div class="label">Mobilized shear strength q_ult (kPa)</div>
      <div class="value">{fmt_val(results["Summary"]["q_ult Mobilized shear strength static (kPa)"])}</div>
    </div>
  </div>

  <div class="section">
    <h2>Inputs</h2>
    {df_to_html(input_df)}
  </div>

  <div class="section">
    <h2>Summary</h2>
    {df_to_html(summary_df, summary=True)}
  </div>

  <div class="section">
    <h2>Method comparison</h2>
    {df_to_html(comparison_df)}
  </div>

  <div class="section">
    <h2>Equivalent soil</h2>
    {df_to_html(eq_df)}
  </div>

  <div class="section">
    <h2>About</h2>
    <div class="note">{ABOUT_TEXT}</div>
  </div>

  <div class="section">
    <h2>Disclaimer / Warranty</h2>
    <div class="note">{DISCLAIMER_TEXT}</div>
  </div>
</body>
</html>
"""


def build_report_pdf_bytes(inputs: Dict[str, Any], results: Dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception:
        return None

    summary_df = build_summary_table(results)
    comparison_df = build_method_comparison_table(results)
    eq_df = pd.DataFrame({
        "Parameter": list(results["equivalent_soil"].keys()),
        "Value": [fmt_val(v) for v in results["equivalent_soil"].values()],
    })
    input_df = build_inputs_table(inputs)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    logo_paths = [Path(LOGO_FILE), HOME_LOGO_FILE]
    for logo_path in logo_paths:
        if logo_path.exists():
            img = Image(str(logo_path))
            iw, ih = img.imageWidth, img.imageHeight
            scale = min(140.0 / max(iw, 1), 70.0 / max(ih, 1), 1.0)
            img.drawWidth = iw * scale
            img.drawHeight = ih * scale
            elements.append(img)
            elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>CUT Bearing Capacity Report</b>", styles["Title"]))
    elements.append(Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["Normal"]))
    elements.append(Spacer(1, 12))

    metric_rows = [
        ["EN 1997-3 q_ult (kPa)", fmt_val(results["Summary"]["q_ult EN 1997-3 (kPa)"])],
        ["CUT method q_ult (kPa)", fmt_val(results["Summary"]["q_ult CUT method (kPa)"])],
        ["Mobilized shear strength q_ult (kPa)", fmt_val(results["Summary"]["q_ult Mobilized shear strength static (kPa)"])],
    ]
    metric_tbl = Table(metric_rows, colWidths=[240, 220])
    metric_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(metric_tbl)
    elements.append(Spacer(1, 12))

    def add_df(title: str, df: pd.DataFrame):
        elements.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        rows = [list(df.columns)] + df.astype(str).values.tolist()
        ncols = len(df.columns)
        if ncols == 2:
            col_widths = [180, 320]
        elif ncols == 4:
            col_widths = [160, 110, 110, 110]
        else:
            col_widths = None
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2fb")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 12))

    add_df("Inputs", input_df)

    summary_df_pdf = summary_df.copy()
    for col in summary_df_pdf.columns:
        if col != "Parameter":
            summary_df_pdf[col] = pd.to_numeric(summary_df_pdf[col], errors="coerce").map(
                lambda x: "n/a" if pd.isna(x) else f"{x:.2f}"
            )
    add_df("Summary", summary_df_pdf)
    add_df("Method comparison", comparison_df)
    add_df("Equivalent soil", eq_df)

    elements.append(Paragraph("<b>About</b>", styles["Heading2"]))
    elements.append(Paragraph(ABOUT_TEXT.replace("\n", "<br/>"), styles["BodyText"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>Disclaimer / Warranty</b>", styles["Heading2"]))
    elements.append(Paragraph(DISCLAIMER_TEXT.replace("\n", "<br/>"), styles["BodyText"]))

    doc.build(elements)
    return buffer.getvalue()

def num(label: str, value: float, step: float = 0.1, fmt: str | None = None, help: str | None = None) -> float:
    return st.number_input(label, value=float(value), step=float(step), format=fmt, help=help)


st.set_page_config(page_title=APP_TITLE, layout="wide")

header_cols = st.columns([1, 3])
with header_cols[0]:
    if Path(LOGO_FILE).exists():
        st.image(LOGO_FILE, width=180)
with header_cols[1]:
    st.title(APP_TITLE)
    st.caption("Version: v8.5 (Program), v3 (Manual)")

CUT_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/v7.1/CUT_Bearing_capacity_updated_v8.5.exe"
COULOMB_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/cut-k-coulomb-v2/CUT_K_Coulomb_v2.exe"

compute_col1, compute_col2, compute_col3 = st.columns([1, 1, 1])
with compute_col1:
    run = st.button("Compute", type="primary", use_container_width=True)
with compute_col2:
    report_html_placeholder = st.empty()
with compute_col3:
    report_pdf_placeholder = st.empty()

with st.sidebar:
    sidebar_home_link(HOME_LOGO_FILE, HOME_URL)

    st.link_button(
        "Run CUT_K_Coulomb (Web)",
        "https://cut-k-coulomb.streamlit.app/",
        use_container_width=True,
    )

    st.header("Program")

    with st.expander("About / Disclaimer / Warranty", expanded=False):
        st.text(ABOUT_TEXT)
        st.text(DISCLAIMER_TEXT)

    if MANUAL_FILE.exists():
        st.download_button(
            "Download User Manual (PDF)",
            data=MANUAL_FILE.read_bytes(),
            file_name=MANUAL_FILE.name,
            mime="application/pdf",
            use_container_width=True,
        )

    st.link_button(
        "Download CUT Bearing Capacity (.exe)",
        CUT_EXE_URL,
        use_container_width=True,
    )

    st.link_button(
        "Download CUT Coulomb (.exe)",
        COULOMB_EXE_URL,
        use_container_width=True,
    )

st.markdown("---")

with st.container():
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("General")
        soil_layers = st.radio("Soil profile", ["1 layer", "2 layers"], index=0)
        footing_type = st.selectbox("Footing type (CUT)", ["Rigid", "Flexible"], index=0)
        is_circular = st.checkbox("Circular footing", value=False)
        failure_mode = st.selectbox("Failure mode", ["General shear", "Local shear", "Punching shear"], index=0)
        if failure_mode in ("Local shear", "Punching shear"):
            fcs = num("f_cs", 2/3, step=0.01)
            lambda3 = num("λ3", 0.5, step=0.05) if failure_mode == "Local shear" else 0.5
        else:
            fcs = 1.0
            lambda3 = 0.5
        kv = num("k_v", 0.0, step=0.01)
        kh = num("k_h", 0.0, step=0.01)
        allow_en_special = st.checkbox("Allow EN 1997-3 for 2-layer and/or seismic situation using c_m and φ_m", value=False)

    with c2:
        st.subheader("Geometry & loading")
        Beff = num("B, B′ or D (m)", 2.0)
        Leff = num("L or L′ (m)", 20.0)
        Df = num("Df = DfP (m)", 1.0)
        DfA = num("DfA (m)", 1.0)
        Dw = num("Dw from ground surface (m)", 10.0)
        alpha = num("α base (deg)", 0.0)
        N = num("N (kN)", 5000.0, step=10.0)
        T = num("T (kN)", 0.0, step=10.0)
        use_delta = st.checkbox("Use δ instead of T", value=False)
        delta_in = num("δ (deg)", 0.0) if use_delta else 0.0
        theta = num("θ (deg)", 90.0)
        res_factor = num("Resistance factor", 1.0, step=0.1)

    with c3:
        st.subheader("Ground inclination / earth pressure")
        beta_en = num("β (EN) (deg)", 0.0)
        k_source = st.selectbox("Source for KA & KP (CUT method)", ["B_EN", "B_AP", "KAKP"], format_func=lambda x: {"B_EN": "β same with EN", "B_AP": "βA & βP", "KAKP": "KA & KP"}[x])
        if k_source == "B_AP":
            betaA = num("βA (active) (deg)", 0.0)
            betaP = num("βP (passive) (deg)", 0.0)
            KA_user = KP_user = 0.0
        elif k_source == "KAKP":
            KA_user = num("KA (manual)", 0.3333, step=0.01)
            KP_user = num("KP (manual)", 3.0, step=0.01)
            betaA = betaP = 0.0
        else:
            st.caption("CUT method uses βA = β and βP = −β in this mode.")
            betaA = betaP = KA_user = KP_user = 0.0
        khlim = st.text_input("k_h,lim (optional)", value="")
        use_reinf = st.checkbox("Enable reinforced earth", value=False)
        n_layers = num("n (layers)", 4.0, step=1.0) if use_reinf else 0.0
        p_tens = num("p (kN/m per layer)", 100.0, step=10.0) if use_reinf else 0.0

st.subheader("Soil data")
if soil_layers == "1 layer":
    soil_left, soil_right = st.columns(2)
    with soil_left:
        coh = num("c (kPa)", 20.0)
        phi = num("φ (deg)", 30.0)
        psi1 = num("ψ (deg)", 0.0)
    with soil_right:
        gamma_dry = num("γ dry (kN/m³)", 18.0)
        gamma_sat = num("γ sat (kN/m³)", 20.0)
        gamma_w = num("γw (kN/m³)", 9.81, step=0.01)
else:
    row1_left, row1_right = st.columns(2)
    with row1_left:
        c1v = num("Layer 1: c (kPa)", 20.0)
    with row1_right:
        c2v = num("Layer 2: c (kPa)", 10.0)

    row2_left, row2_right = st.columns(2)
    with row2_left:
        phi1 = num("Layer 1: φ (deg)", 30.0)
    with row2_right:
        phi2 = num("Layer 2: φ (deg)", 35.0)

    row3_left, row3_right = st.columns(2)
    with row3_left:
        psi1 = num("Layer 1: ψ (deg)", 0.0)
    with row3_right:
        psi2 = num("Layer 2: ψ (deg)", 0.0)

    row4_left, row4_right = st.columns(2)
    with row4_left:
        gamma1_layer = num("Layer 1: γ dry (kN/m³)", 18.0)
    with row4_right:
        gamma2_layer = num("Layer 2: γ dry (kN/m³)", 19.0)

    row5_left, row5_right = st.columns(2)
    with row5_left:
        gamma_sat1_layer = num("Layer 1: γ sat (kN/m³)", 20.0)
    with row5_right:
        gamma_sat2_layer = num("Layer 2: γ sat (kN/m³)", 21.0)

    row6_left, row6_right = st.columns(2)
    with row6_left:
        H1_layer = num("Layer 1: H (m)", 2.0)
    with row6_right:
        gamma_w = num("γw (kN/m³)", 9.81, step=0.01)

inputs = {
    "soil_layers": soil_layers, "footing_type": footing_type, "is_circular": is_circular, "failure_mode": failure_mode,
    "k_source": k_source, "allow_en_special": allow_en_special,
    "Beff": Beff, "Leff": Leff, "Df": Df, "DfA": DfA, "Dw": Dw, "alpha": alpha, "beta_en": beta_en,
    "psi1": psi1, "gamma_w": gamma_w, "N": N, "T": T, "use_delta": use_delta, "delta_in": delta_in, "theta": theta,
    "kv": kv, "kh": kh, "khlim": khlim, "use_reinf": use_reinf, "n_layers": n_layers, "p_tens": p_tens,
    "res_factor": res_factor, "fcs": fcs, "lambda3": lambda3, "betaA": betaA, "betaP": betaP, "KA_user": KA_user, "KP_user": KP_user,
}
if soil_layers == "1 layer":
    inputs.update({"coh": coh, "phi": phi, "gamma_dry": gamma_dry, "gamma_sat": gamma_sat})
else:
    inputs.update({"c1": c1v, "phi1": phi1, "gamma1_layer": gamma1_layer, "gamma_sat1_layer": gamma_sat1_layer, "H1_layer": H1_layer,
                   "c2": c2v, "phi2": phi2, "psi2": psi2, "gamma2_layer": gamma2_layer, "gamma_sat2_layer": gamma_sat2_layer})

if run or "results" in st.session_state:
    try:
        st.session_state["results"] = compute_all(inputs)
    except Exception as e:
        st.session_state.pop("results", None)
        st.error(f"Computation failed: {e}")

if "results" in st.session_state:
    results = st.session_state["results"]
    summary_table = build_summary_table(results)
    comparison_table = build_method_comparison_table(results)
    report_html = build_report_html(inputs, results)
    report_pdf = build_report_pdf_bytes(inputs, results)

    with compute_col2:
        report_html_placeholder.download_button(
            "Report (HTML)",
            data=report_html.encode("utf-8"),
            file_name="CUT_Bearing_Capacity_Report.html",
            mime="text/html",
            use_container_width=True,
        )
    with compute_col3:
        if report_pdf is not None:
            report_pdf_placeholder.download_button(
                "Report (PDF)",
                data=report_pdf,
                file_name="CUT_Bearing_Capacity_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            report_pdf_placeholder.button("Report (PDF)", disabled=True, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("EN 1997-3 q_ult (kPa)", fmt_val(results["Summary"]["q_ult EN 1997-3 (kPa)"]))
    with m2:
        st.metric("CUT method q_ult (kPa)", fmt_val(results["Summary"]["q_ult CUT method (kPa)"]))
    with m3:
        st.metric("Mobilized shear strength q_ult (kPa)", fmt_val(results["Summary"]["q_ult Mobilized shear strength static (kPa)"]))

    tabs = st.tabs(["Summary", "Method comparison", "Equivalent soil", "Help"])
    with tabs[0]:
        st.dataframe(
            summary_table.style.format(
                {col: "{:.2f}" for col in summary_table.columns if col != "Parameter"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    with tabs[1]:
        st.dataframe(comparison_table, use_container_width=True, hide_index=True)
    with tabs[2]:
        eq_df = pd.DataFrame({
            "Parameter": list(results["equivalent_soil"].keys()),
            "Value": [fmt_val(v) for v in results["equivalent_soil"].values()],
        })
        st.dataframe(eq_df, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.write("The web app follows the final v8.5 program and v3 manual, including the original EN 1997-3 checkbox logic, βA/βP and KA/KP inputs, and CUT_K_Coulomb as an auxiliary download tool.")
else:
    with compute_col2:
        report_html_placeholder.button("Report (HTML)", disabled=True, use_container_width=True)
    with compute_col3:
        report_pdf_placeholder.button("Report (PDF)", disabled=True, use_container_width=True)

