import math
from io import BytesIO
import base64
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from PIL import Image

PROGRAM_NAME = "CUT Seismic Earth Pressure Toolkit"
VERSION = "v15.2"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"
HOME_URL = "https://cut-apps.streamlit.app/"
UNIFIED_WARNING = "Limit condition reached: wedge solution not admissible."

METHOD_COLORS = {
    "EN active": "#4C78A8",
    "EN passive": "#4C78A8",
    "prEN active": "#72B7B2",
    "prEN passive": "#72B7B2",
    "AASHTO active": "#F58518",
    "AASHTO passive": "#F58518",
    "CUT active": "#7B2CBF",
    "CUT passive": "#7B2CBF",
}


class GeometryError(ValueError):
    pass


def trapz(x, y):
    return sum(0.5 * (y[i] + y[i + 1]) * (x[i + 1] - x[i]) for i in range(len(x) - 1))


def _safe_sqrt_arg(x):
    if x < 0 and x > -1e-12:
        return 0.0
    return x


def _clip_unit(x):
    if abs(x) > 1 + 1e-12:
        raise GeometryError(UNIFIED_WARNING)
    return max(-1.0, min(1.0, x))


def _require_positive(name, value):
    if value <= 0:
        raise GeometryError(f"{name} must be positive for a real-valued solution.")


def _fmt_res3(value, nr=False, na=False):
    if na:
        return "N/A"
    if nr:
        return "NR"
    return f"{value:.3f}" if value is not None else "—"


def _fmt_auto(value, nr=False, na=False):
    if na:
        return "N/A"
    if nr:
        return "NR"
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        v = float(value)
    except Exception:
        return str(value)
    if abs(v) >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


def format_numeric_df(df: pd.DataFrame):
    out = df.copy()
    for col in out.columns:
        if col == "Method":
            continue
        out[col] = out[col].map(lambda x: "N/A" if pd.isna(x) else _fmt_auto(x))
    return out


def design_wall_friction_deg(delta_deg, gamma_phi):
    return math.degrees(math.atan(math.tan(math.radians(delta_deg)) / gamma_phi))


def weighted_average(layers, key):
    H = sum(layer["thk"] for layer in layers)
    if H <= 0:
        return 0.0
    return sum(layer["thk"] * layer[key] for layer in layers) / H


def build_layers_from_df(df: pd.DataFrame):
    layers = []
    z0 = 0.0
    for _, row in df.iterrows():
        thk = float(row["Thickness"])
        phi = float(row["phi'"])
        c = float(row["c'"])
        gd = float(row["gamma"])
        gs = float(row["gamma_sat"])
        if thk <= 0:
            continue
        layers.append({"z0": z0, "z1": z0 + thk, "thk": thk, "phi": phi, "c": c, "gd": gd, "gs": gs})
        z0 += thk
    return layers


def layer_at_z(layers, z):
    for layer in layers:
        if z <= layer["z1"] + 1e-12:
            return layer
    return layers[-1]


def sigma_v_u_layered(z, layers, zwt, gamma_w):
    sv = 0.0
    for layer in layers:
        a, b = layer["z0"], layer["z1"]
        seg = max(0.0, min(z, b) - a)
        if seg <= 0:
            continue
        if zwt >= b:
            sv += layer["gd"] * seg
        elif zwt <= a:
            sv += layer["gs"] * seg
        else:
            sv += layer["gd"] * (zwt - a) + layer["gs"] * (b - zwt if z >= b else z - zwt)
            if z < b:
                break
    u = 0.0 if z <= zwt else gamma_w * (z - zwt)
    return sv, u


def retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=True):
    sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
    u_d = 0.0
    if include_dynamic and inner_flow == "pervious" and z > zwt:
        z_sub = z - zwt
        Hprime = max(0.0, H - zwt)
        if z_sub > Hprime:
            z_sub = Hprime
        u_d = (7.0 / 6.0) * kh * gamma_w * z_sub
    return sv, u_h, u_d, u_h + u_d


def pren_theta_eq(alphaH, sigma_v, u):
    if u <= 0.0:
        return math.atan(alphaH)
    eff = sigma_v - u
    _require_positive("(σv-u)", eff)
    return math.atan(alphaH * sigma_v / eff)


def compute_gamma_star_theta_ewd(water_case, gamma_dry, gamma_sat, gamma_w, Hprime_base, kh, kv, mode):
    sign = -1.0 if mode == "active" else 1.0
    denom = 1.0 + sign * kv
    if denom <= 0.0:
        raise GeometryError("The denominator 1 ± kv must be positive for θ.")
    if water_case == "E.5: Water table below wall":
        gamma_star = gamma_dry
        tan_theta = kh / denom
        ews = ewd = 0.0
    elif water_case == "E.6: Impervious soil below water table":
        gamma_star = gamma_sat - gamma_w
        tan_theta = (gamma_sat / (gamma_sat - gamma_w)) * (kh / denom)
        ews = 0.5 * gamma_w * Hprime_base**2
        ewd = 0.0
    else:
        gamma_star = gamma_sat - gamma_w
        tan_theta = (gamma_dry / (gamma_sat - gamma_w)) * (kh / denom)
        ews = 0.5 * gamma_w * Hprime_base**2
        ewd = (7.0 / 12.0) * kh * gamma_w * Hprime_base**2
    return gamma_star, math.atan(tan_theta), ews, ewd


def en_active_coeffs_with_theta(phi_deg, beta_deg, alpha_deg, delta_deg, theta):
    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    psi = math.radians(90.0 - alpha_deg)
    delta = math.radians(delta_deg)
    num = math.sin(psi + phi - theta) ** 2
    den0 = math.cos(theta) * math.sin(psi) ** 2 * math.sin(psi - theta - delta)
    _require_positive("denominator", den0)
    threshold = phi_deg - math.degrees(theta)
    if beta_deg <= threshold + 1e-12:
        rad = math.sin(phi + delta) * math.sin(phi - beta - theta) / (math.sin(psi - theta - delta) * math.sin(psi + beta))
        rad = _safe_sqrt_arg(rad)
        if rad < 0:
            raise GeometryError(UNIFIED_WARNING)
        K = num / (den0 * (1.0 + math.sqrt(rad)) ** 2)
    else:
        K = num / den0
    return {"theta_deg": math.degrees(theta), "K_gamma": K, "K_q": K, "K_c": K}


def en_passive_coeffs_with_theta(phi_deg, beta_deg, alpha_deg, theta):
    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    psi = math.radians(90.0 - alpha_deg)
    num = math.sin(psi + phi - theta) ** 2
    den0 = math.cos(theta) * math.sin(psi) ** 2 * math.sin(psi + theta)
    _require_positive("denominator", den0)
    rad = math.sin(phi) * math.sin(phi + beta - theta) / (math.sin(psi + beta) * math.sin(psi + theta))
    rad = _safe_sqrt_arg(rad)
    if rad < 0:
        raise GeometryError(UNIFIED_WARNING)
    bracket = 1.0 - math.sqrt(rad)
    _require_positive("bracket", bracket)
    K = num / (den0 * bracket**2)
    return {"theta_deg": math.degrees(theta), "K_gamma": K, "K_q": K, "K_c": K}


def pren_active_coeffs(phi_deg, beta_deg, delta_deg, theta):
    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    delta = math.radians(delta_deg)
    t1 = _clip_unit(math.sin(delta) / math.sin(phi))
    t2 = _clip_unit(math.sin(beta + theta) / math.sin(phi))
    sq1 = _safe_sqrt_arg(math.sin(phi) ** 2 - math.sin(beta + theta) ** 2)
    sq2 = _safe_sqrt_arg(math.sin(phi) ** 2 - math.sin(delta) ** 2)
    if sq1 < 0 or sq2 < 0:
        raise GeometryError(UNIFIED_WARNING)
    den = math.cos(beta + theta) + math.sqrt(sq1)
    _require_positive("denominator", den)
    factor2 = math.cos(delta) - math.sqrt(sq2)
    _require_positive("factor2", factor2)
    psiA = 0.5 * (math.asin(t1) - math.asin(t2) - delta + beta - theta)
    Kg = (math.cos(delta) / den) * factor2 * (math.cos(beta) / math.cos(theta)) * math.exp(-2.0 * psiA * math.tan(phi))
    return {"theta_deg": math.degrees(theta), "K_gamma": Kg, "K_q": Kg / math.cos(beta), "K_c": (1 - Kg) / math.tan(phi)}


def pren_passive_coeffs(phi_deg, beta_deg, delta_deg, theta):
    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    delta = math.radians(delta_deg)
    t1 = _clip_unit(math.sin(delta) / math.sin(phi))
    t2 = _clip_unit(math.sin(beta - theta) / math.sin(phi))
    sq1 = _safe_sqrt_arg(math.sin(phi) ** 2 - math.sin(beta - theta) ** 2)
    sq2 = _safe_sqrt_arg(math.sin(phi) ** 2 - math.sin(delta) ** 2)
    if sq1 < 0 or sq2 < 0:
        raise GeometryError(UNIFIED_WARNING)
    den = math.cos(beta - theta) - math.sqrt(sq1)
    _require_positive("denominator", den)
    factor2 = math.cos(delta) + math.sqrt(sq2)
    _require_positive("factor2", factor2)
    psiP = 0.5 * (math.asin(t1) + math.asin(t2) + delta + beta + theta)
    Kg = (math.cos(delta) / den) * factor2 * (math.cos(beta) / math.cos(theta)) * math.exp(2.0 * psiP * math.tan(phi))
    return {"theta_deg": math.degrees(theta), "K_gamma": Kg, "K_q": Kg / math.cos(beta), "K_c": (Kg - 1) / math.tan(phi)}


def cut_theta_eq(alphaH, av, sigma_v, u):
    denom = 1.0 - av
    _require_positive("(1-a_v)", denom)
    base = alphaH / denom
    eff = sigma_v - u
    if u > 0.0 and eff > 1e-12:
        return math.atan(base * sigma_v / eff)
    return math.atan(base)


def cut_failure_xi_set():
    return 0.0, 1.0, -1.0


def cut_backslope_vertical_stress_increment(z, gamma_val, beta_deg, mode):
    factor = 1.0 if mode == "active" else 2.5
    return factor * gamma_val * z * math.tan(math.radians(beta_deg))


def cut_empirical_adjustment(phi_deg, c_val, gamma_val, beta_deg, phi_m_deg, mode, z=0.0):
    dsig = cut_backslope_vertical_stress_increment(z, gamma_val, beta_deg, mode)
    return phi_deg, c_val, gamma_val, dsig


def cut_lambda_a0_b1(phi_deg, c_val, sigma_v, u, theta, av, xi, xi1, xi2, mode):
    c_val = max(c_val, 0.001)
    phi = math.radians(phi_deg)
    sin_phi = math.sin(phi)
    tan_phi = math.tan(phi)
    denom = (1.0 - av) * (sigma_v - u)
    _require_positive("(1-a_v)(σv-u)", denom)
    if mode == "active":
        lam = 1.0
        A0 = ((1.0 - sin_phi) / (1.0 + sin_phi)) * (1.0 - xi * sin_phi + math.tan(theta) * tan_phi * (2.0 + xi * (1.0 - sin_phi)))
        B1 = (2.0 * c_val / denom) * math.tan(math.pi / 4.0 - phi / 2.0)
    else:
        A0 = (((1.0 + sin_phi) / (1.0 - sin_phi)) ** xi1) * (1.0 + xi * sin_phi + xi2 * math.tan(theta) * tan_phi * (2.0 + xi * (1.0 + sin_phi)))
        lam = 0.0 if A0 >= 1.0 else 1.0
        ratio = math.tan(math.pi / 4.0 + phi / 2.0) / math.tan(math.pi / 4.0 - phi / 2.0)
        B1 = (2.0 * lam - 1.0) * (2.0 * c_val / denom) * math.tan(math.pi / 4.0 - phi / 2.0) * (ratio ** xi1)
    return lam, A0, B1


def cut_phi_m_from_parameters(phi_deg, c_val, sigma_v, u, theta, av, xi, xi1, xi2, mode):
    phi = math.radians(phi_deg)
    tan_phi = math.tan(phi)
    lam, A0, B1 = cut_lambda_a0_b1(phi_deg, c_val, sigma_v, u, theta, av, xi, xi1, xi2, mode)
    if abs(B1) <= 1e-20 or not math.isfinite(B1):
        raise GeometryError("CUT: invalid B1.")
    e1 = (1.0 - A0) / B1
    denomB = (2.0 * lam - 1.0) * B1
    if abs(denomB) <= 1e-20:
        raise GeometryError("CUT: invalid denominator for e2.")
    e2 = (1.0 + A0) / denomB + 2.0 * c_val / (((1.0 - av) * (sigma_v - u)) * denomB * tan_phi)
    tan2 = tan_phi**2
    a0 = 1.0 + (e2**2) * tan2
    b0 = 1.0 - (2.0 * (2.0 * lam - 1.0) * e1 * e2 + e2**2) * tan2
    c0 = (e1**2 + 2.0 * (2.0 * lam - 1.0) * e1 * e2) * tan2
    d0 = -(e1**2) * tan2
    D0 = b0**2 - 3.0 * a0 * c0
    D1 = 2.0 * b0**3 - 9.0 * a0 * b0 * c0 + 27.0 * (a0**2) * d0
    disc = complex(D1**2 - 4.0 * (D0**3), 0.0)
    inside = 0.5 * (complex(D1, 0.0) - disc ** 0.5)
    C0 = inside ** (1.0 / 3.0) if abs(inside) > 1e-30 else complex(0.0, 0.0)
    if abs(C0) <= 1e-30:
        raise GeometryError("CUT: invalid cubic solution.")
    omega = [complex(1.0, 0.0), complex(-0.5, math.sqrt(3.0) / 2.0), complex(-0.5, -math.sqrt(3.0) / 2.0)]
    roots = []
    sgn = 2.0 * lam - 1.0
    for w in omega:
        xk = -sgn * (b0 + D0 / (C0 * w) + C0 * w) / (3.0 * a0)
        if abs(xk.imag) < 1e-8:
            xr = xk.real
            if -1.0 <= xr <= 1.0:
                phi_k = math.degrees(math.asin(xr))
                if 0.0 <= phi_k <= phi_deg + 1e-8:
                    roots.append((abs(phi_deg - phi_k), phi_k, xr))
    if not roots:
        raise GeometryError("CUT: no physically admissible root.")
    roots.sort(key=lambda t: t[0])
    phi_m = roots[0][1]
    return {"lambda": lam, "A0": A0, "B1": B1, "phi_m_deg": phi_m}


def cut_kxe_from_phi_m(phi_m_deg, phi_deg, c_val, sigma_v, u, av, lam):
    phi_m = math.radians(phi_m_deg)
    phi_p = math.radians(phi_deg)
    tan_phi_p = math.tan(phi_p)
    tan_phi_m = math.tan(phi_m)
    c_m = c_val if abs(tan_phi_p) <= 1e-20 else c_val * (tan_phi_m / tan_phi_p)
    denom = (1.0 - av) * (sigma_v - u)
    _require_positive("(1-a_v)(σv-u)", denom)
    s = 2.0 * lam - 1.0
    KXE = (1.0 - s * math.sin(phi_m)) / (1.0 + s * math.sin(phi_m)) - s * (2.0 * c_m / denom) * math.tan(math.pi / 4.0 - s * phi_m / 2.0)
    sigma_xe = KXE * denom + u
    return KXE, c_m, sigma_xe


def positive_resultant_from_arrays(zvals, sigma_vals):
    if not zvals or not sigma_vals:
        return 0.0, 0.0
    sigma_pos = [max(0.0, s) for s in sigma_vals]
    P = trapz(zvals, sigma_pos)
    if abs(P) <= 1e-12:
        return 0.0, 0.0
    Mtop = trapz(zvals, [sigma_pos[i] * zvals[i] for i in range(len(zvals))])
    ybar_base = zvals[-1] - Mtop / P
    return P, ybar_base


def pointwise_method_profile(method, mode, layers, H, alpha_deg, beta_deg, delta_deg, alphaH, kv, gamma_w, zwt, q,
                             c_mode_on, kh=0.0, inner_flow="impervious", include_retained_dynamic=True, npts=401):
    zvals = [H * i / (npts - 1) for i in range(npts)]
    sigma = []
    theta_vals = []
    Kg = []
    Kq = []
    Kc = []
    qterm = []
    cterm = []
    uvals = []
    udvals = []
    svvals = []
    for z in zvals:
        layer = layer_at_z(layers, z if z > 1e-9 else 1e-9)
        sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=include_retained_dynamic)
        theta = pren_theta_eq(alphaH, sv, u_h)
        if method == "EN":
            if mode == "active":
                coeff = en_active_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, delta_deg, theta)
                cterm_i = -coeff["K_c"] * layer["c"] if c_mode_on else 0.0
                sigma_eff = coeff["K_gamma"] * (1.0 - kv) * (sv - u_h)
            else:
                coeff = en_passive_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, theta)
                cterm_i = coeff["K_c"] * layer["c"] if c_mode_on else 0.0
                sigma_eff = coeff["K_gamma"] * (1.0 + kv) * (sv - u_h)
        elif method == "AASHTO":
            if mode != "active":
                raise GeometryError("AASHTO passive is not defined.")
            coeff = en_active_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, delta_deg, theta)
            cterm_i = -coeff["K_c"] * layer["c"] if c_mode_on else 0.0
            sigma_eff = coeff["K_gamma"] * (1.0 - kv) * (sv - u_h)
        else:
            raise ValueError("Unknown method")
        qterm_i = coeff["K_q"] * q
        s = sigma_eff + qterm_i + cterm_i + u_h + u_d
        sigma.append(s)
        theta_vals.append(coeff["theta_deg"])
        Kg.append(coeff["K_gamma"])
        Kq.append(coeff["K_q"])
        Kc.append(coeff["K_c"])
        qterm.append(qterm_i)
        cterm.append(cterm_i)
        uvals.append(u_h)
        udvals.append(u_d)
        svvals.append(sv)
    P, ybar = positive_resultant_from_arrays(zvals, sigma)
    return {
        "z": zvals, "sigma": sigma, "P": P, "ybar_base": ybar, "theta_deg": theta_vals,
        "K_gamma": Kg, "K_q": Kq, "K_c": Kc, "qterm": qterm, "cterm": cterm,
        "u": uvals, "ud": udvals, "sv": svvals,
        "base_K_gamma": Kg[-1], "base_K_q": Kq[-1], "base_K_c": Kc[-1], "base_theta_deg": theta_vals[-1],
        "top_sigma": sigma[0], "base_sigma": sigma[-1]
    }


def pren_profile(mode, layers, H, beta_deg, delta_deg, alphaH, gamma_w, zwt, q, c_mode_on, kh=0.0, inner_flow="impervious", include_retained_dynamic=True):
    zvals = [H * i / 400 for i in range(401)]
    sigma = []
    theta_vals = []
    Kg = []
    Kq = []
    Kc = []
    qterm = []
    cterm = []
    uvals = []
    udvals = []
    svvals = []
    for z in zvals:
        layer = layer_at_z(layers, z if z > 1e-9 else 1e-9)
        sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=include_retained_dynamic)
        theta = pren_theta_eq(alphaH, sv, u_h)
        if mode == "active":
            coeff = pren_active_coeffs(layer["phi"], beta_deg, delta_deg, theta)
            cterm_i = -coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        else:
            coeff = pren_passive_coeffs(layer["phi"], beta_deg, delta_deg, theta)
            cterm_i = coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        qterm_i = coeff["K_q"] * q
        s = coeff["K_gamma"] * (sv - u_h) + qterm_i + cterm_i + u_h + u_d
        sigma.append(s)
        theta_vals.append(coeff["theta_deg"])
        Kg.append(coeff["K_gamma"])
        Kq.append(coeff["K_q"])
        Kc.append(coeff["K_c"])
        qterm.append(qterm_i)
        cterm.append(cterm_i)
        uvals.append(u_h)
        udvals.append(u_d)
        svvals.append(sv)
    P, ybar = positive_resultant_from_arrays(zvals, sigma)
    return {
        "z": zvals, "sigma": sigma, "P": P, "ybar_base": ybar, "theta_deg": theta_vals,
        "K_gamma": Kg, "K_q": Kq, "K_c": Kc, "qterm": qterm, "cterm": cterm, "u": uvals, "ud": udvals, "sv": svvals,
        "base_K_gamma": Kg[-1], "base_K_q": Kq[-1], "base_K_c": Kc[-1], "base_theta_deg": theta_vals[-1],
        "top_sigma": sigma[0], "base_sigma": sigma[-1]
    }


def cut_profile(mode, layers, H, beta_deg, alphaH, av, gamma_w, zwt, q,
                kh=0.0, inner_flow="impervious", include_retained_dynamic=True, npts=401):
    zvals = [H * i / (npts - 1) for i in range(npts)]
    sigma = []
    theta_vals = []
    Kg = []
    Kq = []
    Kc = []
    qterm = []
    cterm = []
    uvals = []
    udvals = []
    svvals = []
    phim_vals = []
    cm_vals = []
    xi, xi1, xi2 = cut_failure_xi_set()
    for z in zvals:
        layer = layer_at_z(layers, z if z > 1e-9 else 1e-9)
        c0 = max(layer["c"], 0.001)
        sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=include_retained_dynamic)
        try:
            phi_adj, c_adj, _, dsig_beta = cut_empirical_adjustment(layer["phi"], c0, layer["gd"], beta_deg, 0.0, mode, z=z)
            sigma_v_adj = sv + dsig_beta
            theta_adj = cut_theta_eq(alphaH, av, sigma_v_adj, u_h)
            phim = cut_phi_m_from_parameters(phi_adj, c_adj, sigma_v_adj, u_h, theta_adj, av, xi, xi1, xi2, mode)
            KXE, c_m, sigma_xe = cut_kxe_from_phi_m(phim["phi_m_deg"], phi_adj, c_adj, sigma_v_adj, u_h, av, phim["lambda"])
            qterm_i = KXE * q
            sigma_total = sigma_xe + qterm_i + u_d
            sigma.append(sigma_total)
            theta_vals.append(math.degrees(theta_adj))
            Kg.append(KXE)
            Kq.append(KXE)
            Kc.append(0.0)
            qterm.append(qterm_i)
            cterm.append(0.0)
            uvals.append(u_h)
            udvals.append(u_d)
            svvals.append(sigma_v_adj)
            phim_vals.append(phim["phi_m_deg"])
            cm_vals.append(c_m)
        except Exception:
            sigma.append(0.0)
            theta_vals.append(0.0)
            Kg.append(0.0)
            Kq.append(0.0)
            Kc.append(0.0)
            qterm.append(0.0)
            cterm.append(0.0)
            uvals.append(u_h)
            udvals.append(u_d)
            svvals.append(sv)
            phim_vals.append(0.0)
            cm_vals.append(0.0)
    P, ybar = positive_resultant_from_arrays(zvals, sigma)
    return {
        "z": zvals, "sigma": sigma, "P": P, "ybar_base": ybar, "theta_deg": theta_vals,
        "K_gamma": Kg, "K_q": Kq, "K_c": Kc, "qterm": qterm, "cterm": cterm,
        "u": uvals, "ud": udvals, "sv": svvals,
        "phi_m_deg": phim_vals, "c_m": cm_vals,
        "base_K_gamma": Kg[-1], "base_K_q": Kq[-1], "base_K_c": Kc[-1], "base_theta_deg": theta_vals[-1],
        "base_phi_m_deg": phim_vals[-1], "base_c_m": cm_vals[-1],
        "top_sigma": sigma[0], "base_sigma": sigma[-1]
    }


def wall_x_at_depth(H, alpha_deg, z_from_surface):
    if H <= 0:
        return 0.0
    xb = H * math.tan(math.radians(alpha_deg))
    return xb * (z_from_surface / H)


def plot_geometry(H, alpha, beta, zwt, layers):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    xb = H * math.tan(math.radians(alpha))
    x_end = max(4.0, 1.1 * H, xb + 1.0)
    y_end = math.tan(math.radians(beta)) * x_end
    ax.plot([0, xb], [0, -H], lw=2.4, color="crimson")
    ax.plot([0, x_end], [0, y_end], lw=1.9, color="mediumpurple")
    ax.plot([-0.35 * max(1, H), x_end], [0, 0], ls=":", alpha=0.6, color="olive")
    ax.text(x_end * 0.60, y_end + 0.05 * max(1, H), f"β={beta:.2f}°", fontsize=10)
    ax.text(min(xb, 0) - 0.10 * max(1, H), -0.12 * H, f"α={alpha:.2f}°", fontsize=10)
    layer_colors = ["#f7f3d6", "#d9ecff", "#e7f7dc", "#fde2e2", "#efe2ff", "#ffe9d6"]
    if y_end > 0:
        ax.fill([0, x_end, x_end], [0, y_end, 0], facecolor=layer_colors[0], edgecolor="none", alpha=0.6, zorder=0)
    for i, layer in enumerate(layers, start=1):
        z0p, z1p = layer["z0"], layer["z1"]
        zmid_pos = 0.5 * (z0p + z1p)
        zmid = -zmid_pos
        top_y, bot_y = -z0p, -z1p
        x_top = wall_x_at_depth(H, alpha, z0p)
        x_bot = wall_x_at_depth(H, alpha, z1p)
        color = layer_colors[(i - 1) % len(layer_colors)]
        ax.fill([x_top, x_end, x_end, x_bot], [top_y, top_y, bot_y, bot_y], facecolor=color, edgecolor="none", alpha=0.6, zorder=0)
        xtext = max(wall_x_at_depth(H, alpha, zmid_pos) + 0.35, x_end * 0.34)
        ax.text(xtext, zmid, f"L{i}: φ={layer['phi']:.1f}°, c'={layer['c']:.1f}, γ={layer['gd']:.1f}, γsat={layer['gs']:.1f}", fontsize=9, va="center")
        if i < len(layers):
            zb_pos = layer["z1"]
            zb = -zb_pos
            x_layer = wall_x_at_depth(H, alpha, zb_pos)
            ax.plot([x_layer, x_end], [zb, zb], ls="--", alpha=0.45, color="gray")
    if 0 <= zwt <= H:
        xw = wall_x_at_depth(H, alpha, zwt)
        ywt = -zwt
        ax.plot([xw, x_end], [ywt, ywt], ls="-.", lw=1.5, color="slategray")
        ax.text(x_end * 0.78, ywt - 0.03 * H, f"zwt={zwt:.2f} m", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x (m) →")
    ax.set_ylabel("z (m)")
    ax.set_xlim(min(-0.4 * H, -1.0), max(1.2 * H, xb + 1.0))
    ax.set_ylim(-1.1 * H, 0.2 * H)
    fig.tight_layout()
    return fig


def build_results(inputs, layers):
    H = sum(layer["thk"] for layer in layers)
    alpha = inputs["alpha"]
    beta = inputs["beta"]
    delta = inputs["delta"]
    gamma_phi = inputs["gamma_phi"]
    kh = inputs["kh"]
    kv_abs = inputs["kv_abs"]
    aashto_factor = inputs["aashto_factor"]
    zwt = inputs["zwt"]
    gamma_w = inputs["gamma_w"]
    q = inputs["q"]
    inner_flow = inputs["inner_flow"]
    retained_water_mode = inputs["water_action_mode"]
    allow_qc_to_en_aashto = inputs["allow_qc_to_en_aashto"]
    kv = -kv_abs if inputs["kv_negative"] else kv_abs
    delta_d = design_wall_friction_deg(delta, gamma_phi)

    en_kv = kv
    aashto_kv = 0.0
    pren_alphaH = kh
    en_q = q if allow_qc_to_en_aashto else 0.0
    pren_q = q
    pren_c = True
    aashto_q = q if allow_qc_to_en_aashto else 0.0
    en_use_c = allow_qc_to_en_aashto
    aashto_use_c = allow_qc_to_en_aashto

    warnings = []

    try:
        ena_prof = pointwise_method_profile("EN", "active", layers, H, alpha, beta, delta_d, kh, en_kv, gamma_w, zwt, en_q,
                                           en_use_c, kh=kh, inner_flow=inner_flow,
                                           include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
        ena = {"K": ena_prof["base_K_gamma"], "theta_deg": ena_prof["base_theta_deg"], "equation": "pointwise"}
    except Exception as e:
        ena_prof, ena = {"z": [], "sigma": []}, None
        warnings.append(f"EN active: {e}")

    try:
        enp_prof = pointwise_method_profile("EN", "passive", layers, H, alpha, beta, delta_d, kh, en_kv, gamma_w, zwt, en_q,
                                           en_use_c, kh=kh, inner_flow=inner_flow,
                                           include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
        enp = {"K": enp_prof["base_K_gamma"], "theta_deg": enp_prof["base_theta_deg"], "equation": "pointwise"}
    except Exception as e:
        enp_prof, enp = {"z": [], "sigma": []}, None
        warnings.append(f"EN passive: {e}")

    try:
        prena = pren_profile("active", layers, H, beta, delta, pren_alphaH, gamma_w, zwt, pren_q, pren_c,
                             kh=kh, inner_flow=inner_flow,
                             include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
    except Exception as e:
        prena = None
        warnings.append(f"prEN active: {e}")

    try:
        prenp = pren_profile("passive", layers, H, beta, delta, pren_alphaH, gamma_w, zwt, pren_q, pren_c,
                             kh=kh, inner_flow=inner_flow,
                             include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
    except Exception as e:
        prenp = None
        warnings.append(f"prEN passive: {e}")

    try:
        cuta = cut_profile("active", layers, H, beta, kh, en_kv, gamma_w, zwt, q,
                           kh=kh, inner_flow=inner_flow,
                           include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
    except Exception as e:
        cuta = None
        warnings.append(f"CUT active: {e}")

    try:
        cutp = cut_profile("passive", layers, H, beta, kh, en_kv, gamma_w, zwt, q,
                           kh=kh, inner_flow=inner_flow,
                           include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
    except Exception as e:
        cutp = None
        warnings.append(f"CUT passive: {e}")

    kh_a = aashto_factor * kh
    try:
        aashto_prof = pointwise_method_profile("AASHTO", "active", layers, H, alpha, beta, delta_d, kh_a, aashto_kv, gamma_w, zwt, aashto_q,
                                               aashto_use_c, kh=kh, inner_flow=inner_flow,
                                               include_retained_dynamic=(retained_water_mode == "hydrodynamic"))
        aask = {"K": aashto_prof["base_K_gamma"], "theta_deg": aashto_prof["base_theta_deg"]}
    except Exception as e:
        aashto_prof, aask = None, None
        warnings.append(f"AASHTO active: {e}")

    summary_rows = [
        {"Method": "EN 1998-5", "Active resultant": ena_prof.get("P") if ena_prof else None, "Active line above base": ena_prof.get("ybar_base") if ena_prof else None,
         "Passive resultant": enp_prof.get("P") if enp_prof else None, "Passive line above base": enp_prof.get("ybar_base") if enp_prof else None},
        {"Method": "prEN 1998-5", "Active resultant": prena.get("P") if prena else None, "Active line above base": prena.get("ybar_base") if prena else None,
         "Passive resultant": prenp.get("P") if prenp else None, "Passive line above base": prenp.get("ybar_base") if prenp else None},
        {"Method": "AASHTO", "Active resultant": aashto_prof.get("P") if aashto_prof else None, "Active line above base": aashto_prof.get("ybar_base") if aashto_prof else None,
         "Passive resultant": None, "Passive line above base": None},
        {"Method": "CUT", "Active resultant": cuta.get("P") if cuta else None, "Active line above base": cuta.get("ybar_base") if cuta else None,
         "Passive resultant": cutp.get("P") if cutp else None, "Passive line above base": cutp.get("ybar_base") if cutp else None},
    ]
    summary_df = pd.DataFrame(summary_rows)

    return {
        "H": H,
        "profiles": {"ena": ena_prof, "enp": enp_prof, "prena": prena, "prenp": prenp, "aashto": aashto_prof, "cuta": cuta, "cutp": cutp},
        "coeffs": {"ena": ena, "enp": enp, "aask": aask},
        "summary_df": summary_df,
        "warnings": warnings,
    }


def point_table_at_z(zq, H, layers, inputs, results):
    alpha = inputs["alpha"]
    beta = inputs["beta"]
    delta = inputs["delta"]
    gamma_phi = inputs["gamma_phi"]
    kh = inputs["kh"]
    kv_abs = inputs["kv_abs"]
    gamma_w = inputs["gamma_w"]
    zwt = inputs["zwt"]
    q = inputs["q"]
    inner_flow = inputs["inner_flow"]
    retained_water_mode = inputs["water_action_mode"]
    allow_qc_to_en_aashto = inputs["allow_qc_to_en_aashto"]
    aashto_factor = inputs["aashto_factor"]
    kv = -kv_abs if inputs["kv_negative"] else kv_abs
    delta_d = design_wall_friction_deg(delta, gamma_phi)
    en_kv = kv
    aashto_kv = 0.0
    en_q = q if allow_qc_to_en_aashto else 0.0
    pren_q = q
    aashto_q = q if allow_qc_to_en_aashto else 0.0
    en_use_c = allow_qc_to_en_aashto
    aashto_use_c = allow_qc_to_en_aashto
    zq = max(0.0, min(H, float(zq)))
    layer = layer_at_z(layers, max(zq, 1e-9))
    svq_h, uq_h = sigma_v_u_layered(zq, layers, zwt, gamma_w)
    _, _, uq_d, _ = retained_side_u_total(zq, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=(retained_water_mode == "hydrodynamic"))
    effq = max(0.0, svq_h - uq_h)
    rows = []

    def add_row(method, sigma_eff, u_val, ud_val, kq_term, kc_term, sigma_total, kgamma, kq_val, kc_val):
        rows.append({
            "Method": method,
            "σ'=Kγ(σv-u)": sigma_eff,
            "u": u_val,
            "u_d": ud_val,
            "Kq,term": kq_term,
            "Kc,term": kc_term,
            "σa or σp": sigma_total,
            "Kγ": kgamma,
            "Kq": kq_val,
            "Kc": kc_val,
        })

    try:
        coeff_en_a = en_active_coeffs_with_theta(layer["phi"], beta, alpha, delta_d, pren_theta_eq(kh, svq_h, uq_h))
        sigma_eff = coeff_en_a["K_gamma"] * (1.0 - en_kv) * effq
        kq_term = coeff_en_a["K_q"] * en_q
        kc_term = coeff_en_a["K_c"] * layer["c"] if en_use_c else 0.0
        sigma_total = sigma_eff + uq_h + uq_d + kq_term - kc_term
        add_row("EN active", sigma_eff, uq_h, uq_d, kq_term, kc_term, sigma_total, coeff_en_a["K_gamma"], coeff_en_a["K_q"] if allow_qc_to_en_aashto else 0.0, coeff_en_a["K_c"] if allow_qc_to_en_aashto else 0.0)
    except Exception:
        add_row("EN active", None, uq_h, uq_d, None, None, None, None, None, None)

    try:
        coeff_prena = pren_active_coeffs(layer["phi"], beta, delta, pren_theta_eq(kh, svq_h, uq_h))
        sigma_eff = coeff_prena["K_gamma"] * (svq_h - uq_h)
        kq_term = coeff_prena["K_q"] * pren_q
        kc_term = coeff_prena["K_c"] * layer["c"]
        sigma_total = sigma_eff + uq_h + uq_d + kq_term - kc_term
        add_row("prEN active", sigma_eff, uq_h, uq_d, kq_term, kc_term, sigma_total, coeff_prena["K_gamma"], coeff_prena["K_q"], coeff_prena["K_c"])
    except Exception:
        add_row("prEN active", None, uq_h, uq_d, None, None, None, None, None, None)

    try:
        kh_a = aashto_factor * kh
        coeff_aashto = en_active_coeffs_with_theta(layer["phi"], beta, alpha, delta_d, pren_theta_eq(kh_a, svq_h, uq_h))
        sigma_eff = coeff_aashto["K_gamma"] * (1.0 - aashto_kv) * effq
        kq_term = coeff_aashto["K_q"] * aashto_q
        kc_term = coeff_aashto["K_c"] * layer["c"] if aashto_use_c else 0.0
        sigma_total = sigma_eff + uq_h + uq_d + kq_term - kc_term
        add_row("AASHTO active", sigma_eff, uq_h, uq_d, kq_term, kc_term, sigma_total, coeff_aashto["K_gamma"], coeff_aashto["K_q"] if allow_qc_to_en_aashto else 0.0, coeff_aashto["K_c"] if allow_qc_to_en_aashto else 0.0)
    except Exception:
        add_row("AASHTO active", None, uq_h, uq_d, None, None, None, None, None, None)

    try:
        coeff_en_p = en_passive_coeffs_with_theta(layer["phi"], beta, alpha, pren_theta_eq(kh, svq_h, uq_h))
        sigma_eff = coeff_en_p["K_gamma"] * (1.0 + en_kv) * effq
        kq_term = coeff_en_p["K_q"] * en_q
        kc_term = coeff_en_p["K_c"] * layer["c"] if en_use_c else 0.0
        sigma_total = sigma_eff + uq_h + uq_d + kq_term + kc_term
        add_row("EN passive", sigma_eff, uq_h, uq_d, kq_term, kc_term, sigma_total, coeff_en_p["K_gamma"], coeff_en_p["K_q"] if allow_qc_to_en_aashto else 0.0, coeff_en_p["K_c"] if allow_qc_to_en_aashto else 0.0)
    except Exception:
        add_row("EN passive", None, uq_h, uq_d, None, None, None, None, None, None)

    try:
        coeff_prenp = pren_passive_coeffs(layer["phi"], beta, delta, pren_theta_eq(kh, svq_h, uq_h))
        sigma_eff = coeff_prenp["K_gamma"] * (svq_h - uq_h)
        kq_term = coeff_prenp["K_q"] * pren_q
        kc_term = coeff_prenp["K_c"] * layer["c"]
        sigma_total = sigma_eff + uq_h + uq_d + kq_term + kc_term
        add_row("prEN passive", sigma_eff, uq_h, uq_d, kq_term, kc_term, sigma_total, coeff_prenp["K_gamma"], coeff_prenp["K_q"], coeff_prenp["K_c"])
    except Exception:
        add_row("prEN passive", None, uq_h, uq_d, None, None, None, None, None, None)

    cuta = results["profiles"].get("cuta")
    if cuta is not None:
        iz = min(range(len(cuta["z"])), key=lambda i: abs(cuta["z"][i] - zq))
        add_row("CUT active", cuta["sigma"][iz] - cuta["qterm"][iz] - cuta["u"][iz] - cuta["ud"][iz], cuta["u"][iz], cuta["ud"][iz], cuta["qterm"][iz], 0.0, cuta["sigma"][iz], cuta["K_gamma"][iz], cuta["K_q"][iz], 0.0)
    else:
        add_row("CUT active", None, uq_h, uq_d, None, None, None, None, None, None)

    cutp = results["profiles"].get("cutp")
    if cutp is not None:
        iz = min(range(len(cutp["z"])), key=lambda i: abs(cutp["z"][i] - zq))
        add_row("CUT passive", cutp["sigma"][iz] - cutp["qterm"][iz] - cutp["u"][iz] - cutp["ud"][iz], cutp["u"][iz], cutp["ud"][iz], cutp["qterm"][iz], 0.0, cutp["sigma"][iz], cutp["K_gamma"][iz], cutp["K_q"][iz], 0.0)
    else:
        add_row("CUT passive", None, uq_h, uq_d, None, None, None, None, None, None)

    add_row("AASHTO passive", None, None, None, None, None, None, None, None, None)
    return pd.DataFrame(rows)


def build_notes(results, inputs):
    warnings = results["warnings"]
    profiles = results["profiles"]
    coeffs = results["coeffs"]
    kh = inputs["kh"]
    aashto_factor = inputs["aashto_factor"]
    kh_a = aashto_factor * kh

    active_lines = ["Practical notes"]
    active_lines += [f"• {w}" for w in warnings] if warnings else ["• No warning for the current active-side solution."]
    ena = coeffs.get("ena")
    if ena is not None:
        active_lines += ["", "=== EN 1998-5 ===",
                         f"• Governing equation at base: {ena['equation']}",
                         f"• Base coefficient Kγ = {ena['K']:.6f}",
                         f"• Base seismic angle θ = {ena['theta_deg']:.4f}°",
                         f"• Resultant force = {profiles['ena']['P']:.6f}",
                         f"• Point of application above base = {profiles['ena']['ybar_base']:.6f} m"]
    if profiles.get("prena") is not None:
        p = profiles["prena"]
        active_lines += ["", "=== prEN 1998-5 ===",
                         f"• Base coefficients: K_AEγ = {p['base_K_gamma']:.6f}, K_AEq = {p['base_K_q']:.6f}, K_AEc = {p['base_K_c']:.6f}",
                         f"• Base seismic angle θeq = {p['base_theta_deg']:.4f}°",
                         f"• Resultant force = {p['P']:.6f}",
                         f"• Point of application above base = {p['ybar_base']:.6f} m"]
    if profiles.get("aashto") is not None:
        p = profiles["aashto"]
        active_lines += ["", "=== AASHTO ===",
                         f"• kh input = {kh:.3f}, reduction factor = {aashto_factor:.3f}, kh used = {kh_a:.3f}",
                         f"• Base seismic angle θ = {p['base_theta_deg']:.3f}°",
                         f"• Resultant force = {p['P']:.6f}",
                         f"• Point of application above base = {p['ybar_base']:.6f} m"]
    if profiles.get("cuta") is not None:
        p = profiles["cuta"]
        active_lines += ["", "=== CUT ===",
                         "• Active CUT formulation is used with δ ignored.",
                         f"• Base values: K_XE = {p['base_K_gamma']:.6f}, φ_m = {p['base_phi_m_deg']:.6f}°, c_m = {p['base_c_m']:.6f}",
                         f"• Base seismic angle θeq = {p['base_theta_deg']:.6f}°",
                         f"• Resultant force = {p['P']:.6f}",
                         f"• Point of application above base = {p['ybar_base']:.6f} m"]

    passive_lines = ["Practical notes"]
    passive_lines += [f"• {w}" for w in warnings] if warnings else ["• No warning for the current passive-side solution."]
    enp = coeffs.get("enp")
    if enp is not None:
        passive_lines += ["", "=== EN 1998-5 ===",
                          f"• Governing equation at base: {enp['equation']}",
                          f"• Base coefficient Kγ = {enp['K']:.6f}",
                          f"• Base seismic angle θ = {enp['theta_deg']:.4f}°",
                          f"• Resultant force = {profiles['enp']['P']:.6f}",
                          f"• Point of application above base = {profiles['enp']['ybar_base']:.6f} m"]
    if profiles.get("prenp") is not None:
        p = profiles["prenp"]
        passive_lines += ["", "=== prEN 1998-5 ===",
                          f"• Base coefficients: K_PEγ = {p['base_K_gamma']:.6f}, K_PEq = {p['base_K_q']:.6f}, K_PEc = {p['base_K_c']:.6f}",
                          f"• Base seismic angle θeq = {p['base_theta_deg']:.4f}°",
                          f"• Resultant force = {p['P']:.6f}",
                          f"• Point of application above base = {p['ybar_base']:.6f} m"]
    passive_lines += ["", "=== AASHTO ===", "• Seismic passive pressure by Mononobe–Okabe is not used here.", "• Use an alternative passive design method."]
    if profiles.get("cutp") is not None:
        p = profiles["cutp"]
        passive_lines += ["", "=== CUT ===",
                          "• Passive CUT formulation is used with δ ignored.",
                          f"• Base values: K_XE = {p['base_K_gamma']:.6f}, φ_m = {p['base_phi_m_deg']:.6f}°, c_m = {p['base_c_m']:.6f}",
                          f"• Base seismic angle θeq = {p['base_theta_deg']:.6f}°",
                          f"• Resultant force = {p['P']:.6f}",
                          f"• Point of application above base = {p['ybar_base']:.6f} m"]
    return "\n".join(active_lines), "\n".join(passive_lines)


def df_to_csv_download(df: pd.DataFrame):
    return df.to_csv(index=False).encode("utf-8")


def df_to_markdown_download(df: pd.DataFrame):
    try:
        md = df.to_markdown(index=False)
    except Exception:
        md = df.to_csv(index=False)
    return md.encode("utf-8")


def build_report_text(inputs, layers_df, results, point_df, active_notes, passive_notes):
    lines = [PROGRAM_NAME, VERSION, AUTHOR, "", "INPUTS"]
    for key, value in inputs.items():
        lines.append(f"{key}: {value}")
    lines += ["", "LAYERS", layers_df.to_string(index=False), "", "RESULTANT FORCES AND POINTS OF APPLICATION", results["summary_df"].to_string(index=False), "", "POINT RESULTS AT z", point_df.to_string(index=False), "", "ACTIVE PRACTICAL NOTES", active_notes, "", "PASSIVE PRACTICAL NOTES", passive_notes]
    return "\n".join(lines)


def load_logo():
    candidates = [Path("/mnt/data/logo.png"), Path(__file__).with_name("logo.png")]
    for path in candidates:
        if path.exists():
            return Image.open(path)
    return None


def load_home_icon():
    candidates = [Path("/mnt/data/home.png"), Path(__file__).with_name("home.png")]
    for path in candidates:
        if path.exists():
            return path
    return None


def build_cutapps_card(home_icon_path):
    if home_icon_path is None or not Path(home_icon_path).exists():
        return f"""
        <a href="{HOME_URL}" target="_blank" style="
            display:block;
            text-align:center;
            padding:16px;
            border:1px solid rgba(120,120,120,0.35);
            border-radius:16px;
            text-decoration:none;
            font-weight:700;
            color:inherit;
            margin:4px 0 14px 0;
            background:rgba(255,255,255,0.65);
        ">CUT Apps</a>
        """
    mime = "image/png"
    img_b64 = base64.b64encode(Path(home_icon_path).read_bytes()).decode("ascii")
    return f"""
    <a href="{HOME_URL}" target="_blank" style="
        display:block;
        padding:12px;
        border:1px solid rgba(120,120,120,0.28);
        border-radius:18px;
        text-decoration:none;
        color:inherit;
        margin:4px 0 14px 0;
        background:rgba(255,255,255,0.70);
        box-shadow:0 1px 4px rgba(0,0,0,0.06);
    ">
        <img src="data:{mime};base64,{img_b64}" style="width:100%; display:block; border-radius:14px;" />
    </a>
    """


def inject_sidebar_css():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            margin-top: 0.35rem;
            margin-bottom: 0.45rem;
        }
        [data-testid="stSidebar"] .stExpander {
            border-radius: 14px;
            overflow: hidden;
        }
        [data-testid="stSidebar"] .stButton > button,
        [data-testid="stSidebar"] .stDownloadButton > button {
            width: 100%;
            border-radius: 12px;
            min-height: 2.8rem;
        }
        [data-testid="stSidebar"] .cutapps-note {
            font-size: 0.92rem;
            line-height: 1.35;
            opacity: 0.9;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title=PROGRAM_NAME, layout="wide")
    logo = load_logo()
    home_icon = load_home_icon()
    c1, c2 = st.columns([1, 5])
    with c1:
        if logo is not None:
            st.image(logo, use_container_width=True)
    with c2:
        st.title(PROGRAM_NAME)
        st.caption(f"{VERSION} · {AUTHOR}")
        st.markdown("Educational Edition · Streamlit interface")

    inject_sidebar_css()

    with st.sidebar:
        st.markdown(build_cutapps_card(home_icon), unsafe_allow_html=True)
        st.markdown("## Program")
        with st.expander("About / Disclaimer / Warranty", expanded=False):
            st.markdown(
                f"""
                **{PROGRAM_NAME}**  
                {VERSION}  
                {AUTHOR}

                Educational software for teaching and research use.

                Results should always be checked independently. No warranty is provided, and the user remains responsible for engineering judgement, interpretation, and design decisions.
                """
            )
        st.markdown('<div class="cutapps-note">Use the CUT Apps icon above to open the main CUT Apps portal.</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown("## Input data")
        with st.expander("Wall data", expanded=True):
            alpha = st.number_input("Wall batter α (deg) from vertical; + into soil", value=0.0, step=1.0)
            beta = st.number_input("Backfill slope β (deg) from horizontal", value=5.0, step=1.0)
            delta = st.number_input("Wall-soil friction angle δ (deg)", value=0.0, step=1.0)
            gamma_phi = st.number_input("γφ' (partial factor for EN)", value=1.0, step=0.1)
        with st.expander("Seismic data", expanded=True):
            kh = st.number_input("Horizontal seismic coefficient (kh in EN/AASHTO, αH in prEN)", value=0.3, step=0.05)
            kv_abs = st.number_input("Absolute value of vertical seismic coefficient", value=0.0, step=0.05)
            kv_negative = st.checkbox("Use upward seismic force (kv = −|kv|)", value=False)
            aashto_factor = st.number_input("AASHTO reduction factor for kh", value=0.5, step=0.05)
            st.caption("A positive |kv| corresponds to downward seismic force. AASHTO: kv = 0 for design.")
        with st.expander("Water and loads", expanded=True):
            zwt = st.number_input("zwt (m) water table depth from surface z=0", value=4.0, step=0.5)
            gamma_w = st.number_input("γw (kN/m³)", value=9.81, step=0.01)
            inner_flow = st.selectbox("Retained-side soil condition", ["impervious", "pervious"], index=0)
            water_action_mode = st.selectbox("Retained-side water mode", ["hydrostatic", "hydrodynamic"], index=0)
            q = st.number_input("q (kPa) surcharge", value=0.0, step=1.0)
            allow_qc_to_en_aashto = st.checkbox("Apply the logic of prEN1998-5 for q and c to EN1998-5:2004 and AASHTO", value=True)
        with st.expander("Query depth", expanded=True):
            z_query = st.number_input("z (m) from surface", value=2.0, step=0.5)

    st.subheader("Soil data (layers from top to bottom)")
    default_layers = pd.DataFrame([
        {"Thickness": 6.0, "phi'": 30.0, "c'": 20.0, "gamma": 18.0, "gamma_sat": 20.0},
        {"Thickness": 1.0, "phi'": 30.0, "c'": 0.0, "gamma": 18.0, "gamma_sat": 20.0},
    ])
    layers_df = st.data_editor(default_layers, num_rows="dynamic", use_container_width=True, key="layers_editor")

    layers = build_layers_from_df(layers_df)
    if not layers:
        st.error("At least one layer with positive thickness is required.")
        st.stop()

    inputs = {
        "alpha": alpha,
        "beta": beta,
        "delta": delta,
        "gamma_phi": gamma_phi,
        "kh": kh,
        "kv_abs": kv_abs,
        "kv_negative": kv_negative,
        "aashto_factor": aashto_factor,
        "zwt": zwt,
        "gamma_w": gamma_w,
        "inner_flow": inner_flow,
        "water_action_mode": water_action_mode,
        "q": q,
        "allow_qc_to_en_aashto": allow_qc_to_en_aashto,
    }

    results = build_results(inputs, layers)
    H = results["H"]
    point_df = point_table_at_z(z_query, H, layers, inputs, results)
    active_notes, passive_notes = build_notes(results, inputs)

    if results["warnings"]:
        for warning in results["warnings"]:
            st.warning(warning)

    st.subheader("Resultant forces and point of application")
    st.dataframe(format_numeric_df(results["summary_df"]), use_container_width=True, hide_index=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Indicative geometry", "Point level results", "Resultant forces and point of application", "Pressure distributions"])

    with tab1:
        st.pyplot(plot_geometry(H, alpha, beta, zwt, layers), use_container_width=True)

    with tab2:
        show_df = point_df.copy()

        def _format_point_row(row):
            is_na_row = row.get("Method") == "AASHTO passive"
            formatted = {}
            for col, val in row.items():
                if col == "Method":
                    formatted[col] = val
                else:
                    formatted[col] = _fmt_auto(val, na=(is_na_row and val is None))
            return pd.Series(formatted)

        show_df = show_df.apply(_format_point_row, axis=1)
        st.dataframe(show_df, use_container_width=True, hide_index=True)
        st.download_button("Download point results CSV", data=df_to_csv_download(point_df), file_name="point_results.csv", mime="text/csv")

    with tab3:
        summary_fmt = format_numeric_df(results["summary_df"])
        st.dataframe(summary_fmt, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.text_area("Active notes / warnings", active_notes, height=360)
        with c2:
            st.text_area("Passive notes / warnings", passive_notes, height=360)

    with tab4:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 8), sharex=False)
        profiles = results["profiles"]
        if profiles["ena"].get("z"):
            ax1.plot(profiles["ena"]["sigma"], profiles["ena"]["z"], '--o', linewidth=2, markersize=3, markevery=25, label="EN active", color=METHOD_COLORS["EN active"])
        if profiles["prena"] is not None:
            ax1.plot(profiles["prena"]["sigma"], profiles["prena"]["z"], '-', linewidth=2.2, label="prEN active", color=METHOD_COLORS["prEN active"])
        if profiles["aashto"] is not None:
            ax1.plot(profiles["aashto"]["sigma"], profiles["aashto"]["z"], ':s', linewidth=2.2, markersize=3, markevery=25, label="AASHTO active", color=METHOD_COLORS["AASHTO active"])
        if profiles["cuta"] is not None:
            ax1.plot(profiles["cuta"]["sigma"], profiles["cuta"]["z"], '-', linewidth=2.6, label="CUT active", color=METHOD_COLORS["CUT active"])

        if profiles["enp"].get("z"):
            ax2.plot(profiles["enp"]["sigma"], profiles["enp"]["z"], '--o', linewidth=2, markersize=3, markevery=25, label="EN passive", color=METHOD_COLORS["EN passive"])
        if profiles["prenp"] is not None:
            ax2.plot(profiles["prenp"]["sigma"], profiles["prenp"]["z"], '-', linewidth=2.2, label="prEN passive", color=METHOD_COLORS["prEN passive"])
        if profiles["cutp"] is not None:
            ax2.plot(profiles["cutp"]["sigma"], profiles["cutp"]["z"], '-', linewidth=2.6, label="CUT passive", color=METHOD_COLORS["CUT passive"])

        for ax, title, xlabel in [(ax1, "Active-side distributions", "Active earth pressure (kPa)"), (ax2, "Passive-side distributions", "Passive earth pressure (kPa)")]:
            ax.invert_yaxis()
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel("Depth from top (m)")
            ax.grid(True, alpha=0.3)
            if ax.lines:
                ax.legend(loc="best")
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)

    report_text = build_report_text(inputs, layers_df, results, point_df, active_notes, passive_notes)
    with st.sidebar:
        st.divider()
        st.markdown("## Downloads")
        st.download_button("Download report as TXT", data=report_text.encode("utf-8"), file_name="CUT_report.txt", mime="text/plain", use_container_width=True)
        st.download_button("Download resultant summary as CSV", data=df_to_csv_download(results["summary_df"]), file_name="resultant_summary.csv", mime="text/csv", use_container_width=True)
        st.download_button("Download resultant summary as Markdown", data=df_to_markdown_download(results["summary_df"]), file_name="resultant_summary.md", mime="text/markdown", use_container_width=True)


if __name__ == "__main__":
    main()
