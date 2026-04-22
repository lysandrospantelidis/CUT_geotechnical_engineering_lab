#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math, os, sys, tempfile, urllib.request, webbrowser, subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab
from tkinter import filedialog
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

PROGRAM_NAME = "CUT_K_EN1998_AASHTO_prEN"
VERSION = "v16.3"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"
CUT_LOGO_URL = "https://www.cut.ac.cy/digitalAssets/17/17780_100tepak-logo.png"
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


def script_dir():
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(name):
    try:
        base = sys._MEIPASS
    except Exception:
        base = script_dir()
    return os.path.join(base, name)

def find_local_file(name):
    for p in [os.path.join(script_dir(), name), resource_path(name), os.path.join(os.path.abspath("."), name)]:
        if os.path.exists(p):
            return p
    return None

def load_button_image(path, target_w, target_h):
    img = Image.open(path).convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (255,255,255,0))
    x = (target_w - img.width)//2
    y = (target_h - img.height)//2
    canvas.paste(img, (x,y), img)
    return ImageTk.PhotoImage(canvas)

def load_home_button_image(path, target_size):
    return load_button_image(path, target_size, target_size)

def trapz(x, y):
    return sum(0.5*(y[i]+y[i+1])*(x[i+1]-x[i]) for i in range(len(x)-1))

class GeometryError(ValueError):
    pass

def _safe_sqrt_arg(x):
    if x < 0 and x > -1e-12:
        return 0.0
    return x

def _clip_unit(x):
    if abs(x) > 1+1e-12:
        raise GeometryError(UNIFIED_WARNING)
    return max(-1.0, min(1.0, x))

def _require_positive(name, value):
    if value <= 0:
        raise GeometryError(f"{name} must be positive for a real-valued solution.")

def design_wall_friction_deg(delta_deg, gamma_phi):
    return math.degrees(math.atan(math.tan(math.radians(delta_deg))/gamma_phi))

def _is_nr_error(exc):
    return str(exc) == UNIFIED_WARNING

def _fmt_res3(value, nr=False, na=False):
    if na:
        return "N/A"
    if nr:
        return "NR"
    return f"{value:.3f}" if value is not None else "—"

def _fmt_res4(value, nr=False, na=False):
    if na:
        return "N/A"
    if nr:
        return "NR"
    return f"{value:.4f}" if value is not None else "—"

def _fmt_theta(value, nr=False, na=False):
    if na:
        return "N/A"
    if nr:
        return "θ=NR"
    return f"θ={value:.2f}" if value is not None else "—"


def _fmt_cell3(value, nr=False, na=False):
    if isinstance(value, str):
        return value
    return _fmt_res3(value, nr=nr, na=na)


def derive_pren_qc_from_K(K_gamma, phi_deg, beta_deg, mode):
    phi = math.radians(phi_deg)
    cosb = math.cos(math.radians(beta_deg))
    _require_positive("cos(beta)", cosb)
    tanphi = math.tan(phi)
    _require_positive("tan(phi)", tanphi)
    K_q = K_gamma / cosb
    if mode == "active":
        K_c = (1.0 - K_gamma) / tanphi
    else:
        K_c = (K_gamma - 1.0) / tanphi
    return K_q, K_c

# ---------------- layer helpers ----------------
def weighted_average(layers, key):
    H = sum(layer["thk"] for layer in layers)
    if H <= 0: return 0.0
    return sum(layer["thk"] * layer[key] for layer in layers) / H

def build_layers(layer_rows):
    layers = []
    z0 = 0.0
    for row in layer_rows:
        thk = float(row["thk"].get())
        phi = float(row["phi"].get())
        c = float(row["c"].get())
        gd = float(row["gd"].get())
        gs = float(row["gs"].get())
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
    """
    Retained-side water pressure inside the soil.
    Hydrostatic always applies below zwt.
    For pervious soil below the water table, add the E.7 hydrodynamic increment:
        u_d = (7/6) * kh * gamma_w * z_sub
    where z_sub = z - zwt.
    """
    sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)

    u_d = 0.0
    if include_dynamic and inner_flow == "pervious" and z > zwt:
        z_sub = z - zwt
        Hprime = max(0.0, H - zwt)
        if z_sub > Hprime:
            z_sub = Hprime
        u_d = (7.0 / 6.0) * kh * gamma_w * z_sub

    return sv, u_h, u_d, u_h + u_d

# ---------------- EN/AASHTO formulas ----------------
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
        ewd = (7.0/12.0) * kh * gamma_w * Hprime_base**2
    return gamma_star, math.atan(tan_theta), ews, ewd

def en_active_K(phi_deg, beta_deg, alpha_deg, delta_d_deg, kh, kv, water_case, gamma_dry, gamma_sat, gamma_w, Hprime_base):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); psi = math.radians(90.0-alpha_deg); delta = math.radians(delta_d_deg)
    gstar, theta, ews, ewd = compute_gamma_star_theta_ewd(water_case, gamma_dry, gamma_sat, gamma_w, Hprime_base, kh, kv, "active")
    num = math.sin(psi + phi - theta)**2
    den0 = math.cos(theta) * math.sin(psi)**2 * math.sin(psi - theta - delta)
    _require_positive("denominator", den0)
    threshold = phi_deg - math.degrees(theta)
    if beta_deg <= threshold + 1e-12:
        rad = math.sin(phi + delta)*math.sin(phi - beta - theta)/(math.sin(psi-theta-delta)*math.sin(psi+beta))
        rad = _safe_sqrt_arg(rad)
        if rad < 0: raise GeometryError(UNIFIED_WARNING)
        K = num / (den0 * (1.0 + math.sqrt(rad))**2)
        eq = "Eq. (E.2)"
    else:
        K = num / den0
        eq = "Eq. (E.3)"
    return {"K": K, "theta_deg": math.degrees(theta), "gamma_star": gstar, "Ews": ews, "Ewd": ewd, "equation": eq}

def en_passive_K(phi_deg, beta_deg, alpha_deg, kh, kv, water_case, gamma_dry, gamma_sat, gamma_w, Hprime_base):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); psi = math.radians(90.0-alpha_deg)
    gstar, theta, ews, ewd = compute_gamma_star_theta_ewd(water_case, gamma_dry, gamma_sat, gamma_w, Hprime_base, kh, kv, "passive")
    num = math.sin(psi + phi - theta)**2
    den0 = math.cos(theta) * math.sin(psi)**2 * math.sin(psi + theta)
    _require_positive("denominator", den0)
    rad = math.sin(phi)*math.sin(phi + beta - theta)/(math.sin(psi+beta)*math.sin(psi+theta))
    rad = _safe_sqrt_arg(rad)
    if rad < 0: raise GeometryError(UNIFIED_WARNING)
    bracket = 1.0 - math.sqrt(rad)
    _require_positive("bracket", bracket)
    K = num / (den0 * bracket**2)
    return {"K": K, "theta_deg": math.degrees(theta), "gamma_star": gstar, "Ews": ews, "Ewd": ewd, "equation": "Eq. (E.4)"}

def en_total_force(H, K, gamma_star, kv, Ews, Ewd, mode):
    sign = -1.0 if mode=="active" else 1.0
    return 0.5 * gamma_star * (1.0 + sign*kv) * K * H * H + Ews + Ewd

# ---------------- prEN ----------------
def pren_theta_eq(alphaH, sigma_v, u):
    if u <= 0.0:
        return math.atan(alphaH)
    eff = sigma_v - u
    _require_positive("(σv-u)", eff)
    return math.atan(alphaH * sigma_v / eff)

def pren_active_coeffs(phi_deg, beta_deg, delta_deg, theta):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); delta = math.radians(delta_deg)
    t1 = _clip_unit(math.sin(delta)/math.sin(phi))
    t2 = _clip_unit(math.sin(beta + theta)/math.sin(phi))
    sq1 = _safe_sqrt_arg(math.sin(phi)**2 - math.sin(beta+theta)**2)
    sq2 = _safe_sqrt_arg(math.sin(phi)**2 - math.sin(delta)**2)
    if sq1 < 0 or sq2 < 0: raise GeometryError(UNIFIED_WARNING)
    den = math.cos(beta+theta) + math.sqrt(sq1)
    _require_positive("denominator", den)
    factor2 = math.cos(delta) - math.sqrt(sq2)
    _require_positive("factor2", factor2)
    psiA = 0.5 * (math.asin(t1) - math.asin(t2) - delta + beta - theta)
    Kg = (math.cos(delta)/den) * factor2 * (math.cos(beta)/math.cos(theta)) * math.exp(-2.0 * psiA * math.tan(phi))
    return {"theta_deg": math.degrees(theta), "K_gamma": Kg, "K_q": Kg/math.cos(beta), "K_c": (1-Kg)/math.tan(phi)}

def pren_passive_coeffs(phi_deg, beta_deg, delta_deg, theta):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); delta = math.radians(delta_deg)
    t1 = _clip_unit(math.sin(delta)/math.sin(phi))
    t2 = _clip_unit(math.sin(beta - theta)/math.sin(phi))
    sq1 = _safe_sqrt_arg(math.sin(phi)**2 - math.sin(beta-theta)**2)
    sq2 = _safe_sqrt_arg(math.sin(phi)**2 - math.sin(delta)**2)
    if sq1 < 0 or sq2 < 0: raise GeometryError(UNIFIED_WARNING)
    den = math.cos(beta-theta) - math.sqrt(sq1)
    _require_positive("denominator", den)
    factor2 = math.cos(delta) + math.sqrt(sq2)
    _require_positive("factor2", factor2)
    psiP = 0.5 * (math.asin(t1) + math.asin(t2) + delta + beta + theta)
    Kg = (math.cos(delta)/den) * factor2 * (math.cos(beta)/math.cos(theta)) * math.exp(2.0 * psiP * math.tan(phi))
    return {"theta_deg": math.degrees(theta), "K_gamma": Kg, "K_q": Kg/math.cos(beta), "K_c": (Kg-1)/math.tan(phi)}

# ---------------- CUT / K_XE method ----------------
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
    """
    Backslope correction at the wall.
    The increment is applied directly to the vertical stress and depends on the
    failure mode:
        active:  Δσz = γ z tanβ
        passive: Δσz = 2.5 γ z tanβ
    Positive β increases the vertical stress; negative β decreases it.
    """
    if mode == "active":
        factor = 1.0
    else:
        factor = 2.5
    return factor * gamma_val * z * math.tan(math.radians(beta_deg))


def cut_empirical_adjustment(phi_deg, c_val, gamma_val, beta_deg, phi_m_deg, mode, z=0.0):
    """
    Legacy wrapper kept for compatibility.
    The old empirical rescaling of φ, c, and γ has been replaced by a
    stress-based backslope correction, so soil strength parameters remain unchanged.
    """
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
        A0 = ((1.0 - sin_phi) / (1.0 + sin_phi)) * (
            1.0 - xi * sin_phi + math.tan(theta) * tan_phi * (2.0 + xi * (1.0 - sin_phi))
        )
        B1 = (2.0 * c_val / denom) * math.tan(math.pi / 4.0 - phi / 2.0)
    else:
        A0 = (((1.0 + sin_phi) / (1.0 - sin_phi)) ** xi1) * (
            1.0 + xi * sin_phi + xi2 * math.tan(theta) * tan_phi * (2.0 + xi * (1.0 + sin_phi))
        )
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

    denominator_term = max((1.0 - av) * (sigma_v - u) * (2.0 * lam - 1.0) * B1 * tan_phi, 1e-20)
    e2 = (1.0 + A0) / denomB + 2.0 * c_val / denominator_term

    tan2 = tan_phi ** 2
    a0 = 1.0 + (e2 ** 2) * tan2
    b0 = 1.0 - (2.0 * (2.0 * lam - 1.0) * e1 * e2 + e2 ** 2) * tan2
    c0 = (e1 ** 2 + 2.0 * (2.0 * lam - 1.0) * e1 * e2) * tan2
    d0 = -(e1 ** 2) * tan2

    D0 = b0 ** 2 - 3.0 * a0 * c0
    D1 = 2.0 * b0 ** 3 - 9.0 * a0 * b0 * c0 + 27.0 * (a0 ** 2) * d0

    inside_sqrt = complex(D1 ** 2 - 4.0 * (D0 ** 3), 0.0)
    inside = 0.5 * (complex(D1, 0.0) - inside_sqrt ** 0.5)
    C0 = inside ** (1.0 / 3.0)
    if abs(C0) <= 1e-30:
        raise GeometryError("CUT: invalid cubic solution.")

    zeta = complex(-0.5, math.sqrt(3.0) / 2.0)
    zlam = zeta ** lam
    x = -(2.0 * lam - 1.0) * (b0 + D0 / (C0 * zlam) + C0 * zlam) / (3.0 * a0)

    x_real = x.real
    if x_real > 1.0:
        x_real = 1.0
    elif x_real < -1.0:
        x_real = -1.0
    phi_m = math.degrees(math.asin(x_real))

    return {
        "lambda": lam, "A0": A0, "B1": B1, "e1": e1, "e2": e2,
        "a0": a0, "b0": b0, "c0": c0, "d0": d0, "D0": D0, "D1": D1, "C0": C0,
        "phi_m_deg": phi_m
    }


def cut_kxe_from_phi_m(phi_m_deg, phi_deg, c_val, sigma_v, u, av, lam):
    phi_m = math.radians(phi_m_deg)
    phi_p = math.radians(phi_deg)
    tan_phi_p = math.tan(phi_p)
    tan_phi_m = math.tan(phi_m)
    c_m = c_val if abs(tan_phi_p) <= 1e-20 else c_val * (tan_phi_m / tan_phi_p)
    denom = (1.0 - av) * (sigma_v - u)
    _require_positive("(1-a_v)(σv-u)", denom)
    s = (2.0 * lam - 1.0)
    KXE = (1.0 - s * math.sin(phi_m)) / (1.0 + s * math.sin(phi_m)) - s * (2.0 * c_m / denom) * math.tan(math.pi / 4.0 - s * phi_m / 2.0)
    sigma_xe = KXE * denom + u
    return KXE, c_m, sigma_xe


def cut_profile(mode, layers, H, beta_deg, alphaH, av, gamma_w, zwt, q,
                kh=0.0, inner_flow="impervious", include_retained_dynamic=True, npts=401):
    zvals = [H * i / (npts - 1) for i in range(npts)]
    sigma=[]; sigma_raw=[]; sigma_res=[]; tension_flags=[]; theta_vals=[]; Kg=[]; Kq=[]; Kc=[]; qterm=[]; cterm=[]; uvals=[]; udvals=[]; svvals=[]; phim_vals=[]; cm_vals=[]
    xi, xi1, xi2 = cut_failure_xi_set()

    for z in zvals:
        z_eval = max(z, 0.001)
        layer = layer_at_z(layers, z_eval)
        c0 = max(layer["c"], 0.001)

        sv, u_h = sigma_v_u_layered(z_eval, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(
            z_eval, H, layers, zwt, gamma_w, kh, inner_flow,
            include_dynamic=include_retained_dynamic
        )

        try:
            phi_adj, c_adj, _, dsig_beta = cut_empirical_adjustment(
                layer["phi"], c0, layer["gd"], beta_deg, 0.0, mode, z=z_eval
            )

            sigma_v_adj = sv + dsig_beta
            theta_adj = cut_theta_eq(alphaH, av, sigma_v_adj, u_h)

            phim = cut_phi_m_from_parameters(
                phi_adj, c_adj, sigma_v_adj, u_h, theta_adj, av, xi, xi1, xi2, mode
            )

            KXE, c_m, sigma_xe = cut_kxe_from_phi_m(
                phim["phi_m_deg"], phi_adj, c_adj, sigma_v_adj, u_h, av, phim["lambda"]
            )

            qterm_i = KXE * q
            sigma_total_raw = sigma_xe + qterm_i + u_d
            is_tension = sigma_total_raw < 0.0
            sigma_total_plot = float('nan') if is_tension else sigma_total_raw
            sigma_total_res = 0.0 if is_tension else sigma_total_raw

            sigma.append(sigma_total_plot)
            sigma_raw.append(sigma_total_raw)
            sigma_res.append(sigma_total_res)
            tension_flags.append(is_tension)
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
            sigma_raw.append(0.0)
            sigma_res.append(0.0)
            tension_flags.append(False)
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

    P, ybar = positive_resultant_from_arrays(zvals, sigma_res)

    return {
        "z": zvals, "sigma": sigma, "sigma_raw": sigma_raw, "sigma_resultant": sigma_res, "tension": tension_flags, "P": P, "ybar_base": ybar, "theta_deg": theta_vals,
        "K_gamma": Kg, "K_q": Kq, "K_c": Kc, "qterm": qterm, "cterm": cterm,
        "u": uvals, "ud": udvals, "sv": svvals,
        "phi_m_deg": phim_vals, "c_m": cm_vals,
        "base_K_gamma": Kg[-1], "base_K_q": Kq[-1], "base_K_c": Kc[-1], "base_theta_deg": theta_vals[-1],
        "base_phi_m_deg": phim_vals[-1], "base_c_m": cm_vals[-1],
        "top_sigma": sigma_raw[0], "base_sigma": sigma_raw[-1]
    }


def en_active_coeffs_with_theta(phi_deg, beta_deg, alpha_deg, delta_deg, theta):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); psi = math.radians(90.0-alpha_deg); delta = math.radians(delta_deg)
    num = math.sin(psi + phi - theta)**2
    den0 = math.cos(theta) * math.sin(psi)**2 * math.sin(psi - theta - delta)
    _require_positive("denominator", den0)
    threshold = phi_deg - math.degrees(theta)
    if beta_deg <= threshold + 1e-12:
        rad = math.sin(phi + delta)*math.sin(phi - beta - theta)/(math.sin(psi-theta-delta)*math.sin(psi+beta))
        rad = _safe_sqrt_arg(rad)
        if rad < 0:
            raise GeometryError(UNIFIED_WARNING)
        K = num / (den0 * (1.0 + math.sqrt(rad))**2)
    else:
        K = num / den0
    return {"theta_deg": math.degrees(theta), "K_gamma": K, "K_q": K, "K_c": K}


def en_passive_coeffs_with_theta(phi_deg, beta_deg, alpha_deg, theta):
    phi = math.radians(phi_deg); beta = math.radians(beta_deg); psi = math.radians(90.0-alpha_deg)
    num = math.sin(psi + phi - theta)**2
    den0 = math.cos(theta) * math.sin(psi)**2 * math.sin(psi + theta)
    _require_positive("denominator", den0)
    rad = math.sin(phi)*math.sin(phi + beta - theta)/(math.sin(psi+beta)*math.sin(psi+theta))
    rad = _safe_sqrt_arg(rad)
    if rad < 0:
        raise GeometryError(UNIFIED_WARNING)
    bracket = 1.0 - math.sqrt(rad)
    _require_positive("bracket", bracket)
    K = num / (den0 * bracket**2)
    return {"theta_deg": math.degrees(theta), "K_gamma": K, "K_q": K, "K_c": K}


def pointwise_method_profile(method, mode, layers, H, alpha_deg, beta_deg, delta_deg, alphaH, kv, gamma_w, zwt, q,
                             c_mode_on, kh=0.0, inner_flow="impervious", include_retained_dynamic=True,
                             npts=401):
    zvals = [H*i/(npts-1) for i in range(npts)]
    sigma=[]; theta_vals=[]; Kg=[]; Kq=[]; Kc=[]; qterm=[]; cterm=[]; uvals=[]; udvals=[]; svvals=[]
    for z in zvals:
        layer = layer_at_z(layers, z if z > 1e-9 else 1e-9)
        sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=include_retained_dynamic)
        theta = pren_theta_eq(alphaH, sv, u_h)
        if method == "EN":
            if mode == "active":
                coeff = en_active_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, delta_deg, theta)
                sigma_eff = coeff["K_gamma"] * (1.0 - kv) * (sv - u_h)
            else:
                coeff = en_passive_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, theta)
                sigma_eff = coeff["K_gamma"] * (1.0 + kv) * (sv - u_h)
        elif method == "AASHTO":
            if mode != "active":
                raise GeometryError("AASHTO passive is not defined.")
            coeff = en_active_coeffs_with_theta(layer["phi"], beta_deg, alpha_deg, delta_deg, theta)
            sigma_eff = coeff["K_gamma"] * (1.0 - kv) * (sv - u_h)
        else:
            raise ValueError("Unknown method")

        if c_mode_on:
            K_q_use, K_c_use = derive_pren_qc_from_K(coeff["K_gamma"], layer["phi"], beta_deg, mode)
        else:
            K_q_use, K_c_use = coeff["K_q"], coeff["K_c"]

        coeff = {**coeff, "K_q": K_q_use, "K_c": K_c_use}
        if mode == "active":
            cterm_i = -coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        else:
            cterm_i = coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        qterm_i = coeff["K_q"] * q
        s = sigma_eff + qterm_i + cterm_i + u_h + u_d
        sigma.append(s); theta_vals.append(coeff["theta_deg"]); Kg.append(coeff["K_gamma"]); Kq.append(coeff["K_q"]); Kc.append(coeff["K_c"])
        qterm.append(qterm_i); cterm.append(cterm_i); uvals.append(u_h); udvals.append(u_d); svvals.append(sv)
    P, ybar = positive_resultant_from_arrays(zvals, sigma)
    return {"z":zvals,"sigma":sigma,"P":P,"ybar_base":ybar,"theta_deg":theta_vals,"K_gamma":Kg,"K_q":Kq,"K_c":Kc,
            "qterm":qterm,"cterm":cterm,"u":uvals,"ud":udvals,"sv":svvals,
            "base_K_gamma":Kg[-1], "base_K_q":Kq[-1], "base_K_c":Kc[-1], "base_theta_deg":theta_vals[-1],
            "top_sigma":sigma[0], "base_sigma":sigma[-1]}

def pren_profile(mode, layers, H, beta_deg, delta_deg, alphaH, gamma_w, zwt, q, c_mode_on, kh=0.0, inner_flow="impervious", include_retained_dynamic=True):
    zvals = [H*i/400 for i in range(401)]
    sigma=[]; theta_vals=[]; Kg=[]; Kq=[]; Kc=[]; qterm=[]; cterm=[]; uvals=[]; udvals=[]; svvals=[]
    for z in zvals:
        layer = layer_at_z(layers, z if z > 1e-9 else 1e-9)
        sv, u_h = sigma_v_u_layered(z, layers, zwt, gamma_w)
        _, _, u_d, _ = retained_side_u_total(z, H, layers, zwt, gamma_w, kh, inner_flow, include_dynamic=include_retained_dynamic)
        theta = pren_theta_eq(alphaH, sv, u_h)
        if mode=="active":
            coeff = pren_active_coeffs(layer["phi"], beta_deg, delta_deg, theta)
            cterm_i = -coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        else:
            coeff = pren_passive_coeffs(layer["phi"], beta_deg, delta_deg, theta)
            cterm_i = coeff["K_c"] * layer["c"] if c_mode_on else 0.0
        qterm_i = coeff["K_q"] * q
        s = coeff["K_gamma"] * (sv-u_h) + qterm_i + cterm_i + u_h + u_d
        sigma.append(s); theta_vals.append(coeff["theta_deg"]); Kg.append(coeff["K_gamma"]); Kq.append(coeff["K_q"]); Kc.append(coeff["K_c"]); qterm.append(qterm_i); cterm.append(cterm_i); uvals.append(u_h); udvals.append(u_d); svvals.append(sv)
    P, ybar = positive_resultant_from_arrays(zvals, sigma)
    return {"z":zvals,"sigma":sigma,"P":P,"ybar_base":ybar,"theta_deg":theta_vals,"K_gamma":Kg,"K_q":Kq,"K_c":Kc,"qterm":qterm,"cterm":cterm,"u":uvals,"ud":udvals,"sv":svvals,
            "base_K_gamma":Kg[-1], "base_K_q":Kq[-1], "base_K_c":Kc[-1], "base_theta_deg":theta_vals[-1], "top_sigma":sigma[0], "base_sigma":sigma[-1]}

def en_outer_face_hydrodynamic(H, Hw, kh, gamma_w):
    """
    EN 1998-5 Annex E.8 / Eq. (E.18):
        q(z_local) = ± 7/8 * kh * gamma_w * sqrt(Hw * z_local)
    where z_local is measured downward from the water surface on the exposed side.
    Water occupies the LOWER Hw metres of the wall, so in global wall coordinates
    the water surface is at depth H-Hw and the base is at depth H.
    """
    if Hw <= 0:
        return {"z_global":[0.0], "q":[0.0], "P":0.0, "ybar_base":0.0, "qmax":0.0}
    z_local = [Hw * i / 200 for i in range(201)]
    qvals = [(7.0/8.0) * kh * gamma_w * math.sqrt(Hw * z) for z in z_local]
    z_global = [(H - Hw) + z for z in z_local]
    P = trapz(z_local, qvals)
    ybar = 0.0
    if abs(P) > 1e-12:
        M_local = trapz(z_local, [qvals[i] * z_local[i] for i in range(len(z_local))])
        ybar = Hw - M_local / P
    return {"z_global": z_global, "q": qvals, "P": P, "ybar_base": ybar, "qmax": qvals[-1]}


def outer_face_hydrostatic(H, Hw, gamma_w):
    if Hw <= 0:
        return {"z_global":[0.0], "p":[0.0]}
    z_local = [Hw * i / 200 for i in range(201)]
    pvals = [gamma_w * z for z in z_local]
    z_global = [(H - Hw) + z for z in z_local]
    return {"z_global": z_global, "p": pvals}


def outer_face_water_increment(H, Hw, gamma_w, kh, mode, sign=1.0):
    hydrostatic = outer_face_hydrostatic(H, Hw, gamma_w)
    hydrodynamic = en_outer_face_hydrodynamic(H, Hw, kh, gamma_w)
    if mode == "hydrodynamic":
        total = [hydrostatic["p"][i] + sign * hydrodynamic["q"][i] for i in range(len(hydrostatic["p"]))]
        sign_txt = "+" if sign >= 0 else "−"
        comment = f"contains outer-face hydrostatic {sign_txt} hydrodynamic"
    else:
        total = hydrostatic["p"][:]
        comment = "contains outer-face hydrostatic only"
    return {"z_global": hydrostatic["z_global"], "p_total": total, "p_h": hydrostatic["p"], "q_h": hydrodynamic["q"], "comment": comment}


def interpolate_piecewise(xvals, yvals, x):
    if not xvals:
        return 0.0
    if x <= xvals[0]:
        return yvals[0]
    if x >= xvals[-1]:
        return yvals[-1]
    for i in range(len(xvals)-1):
        x0, x1 = xvals[i], xvals[i+1]
        if x0 <= x <= x1:
            if abs(x1-x0) < 1e-12:
                return yvals[i]
            t = (x - x0) / (x1 - x0)
            return yvals[i] + t * (yvals[i+1] - yvals[i])
    return yvals[-1]

def equivalent_profile_layered(
    layers, H, K, gamma_star, kv, mode, q=0.0, use_c=False, npts=121,
    gamma_w=9.81, zwt=None, total_stress=True,
    kh=0.0, inner_flow="impervious", include_retained_dynamic=True
):
    sign = -1.0 if mode == "active" else 1.0
    z = [H * i / (npts - 1) for i in range(npts)]
    sigma = []
    uvals = []
    udvals = []
    for zi in z:
        layer = layer_at_z(layers, max(zi, 1e-9))
        c_here = layer["c"] if use_c else 0.0
        if total_stress and zwt is not None:
            sv, u_h = sigma_v_u_layered(zi, layers, zwt, gamma_w)
            _, _, u_d, _ = retained_side_u_total(
                zi, H, layers, zwt, gamma_w, kh, inner_flow,
                include_dynamic=include_retained_dynamic
            )
            eff = max(0.0, sv - u_h)
            base = K * (1.0 + sign * kv) * eff
            sigma_i = base + u_h + u_d
            u_show = u_h
        else:
            u_h = 0.0
            u_d = 0.0
            base = K * gamma_star * (1.0 + sign * kv) * zi
            sigma_i = base
            u_show = 0.0
        if mode == "active":
            sigma_i += K * q - K * c_here
        else:
            sigma_i += K * q + K * c_here
        sigma.append(sigma_i)
        uvals.append(u_show)
        udvals.append(u_d)
    return {"z": z, "sigma": sigma, "u": uvals, "ud": udvals}


def add_outer_face_water_to_profile(profile, H, Hw, gamma_w, kh, mode, sign=1.0):
    if not profile or not profile.get("z"):
        return {"z": [], "sigma": []}
    z = profile["z"]
    sigma = profile["sigma"][:]
    if Hw <= 0:
        return {"z": z, "sigma": sigma, "comment": "contains retained-side total stress only"}
    z_start = H - Hw
    comment = "contains retained-side total stress + outer-face hydrostatic"
    for i, zi in enumerate(z):
        if zi >= z_start:
            z_local = zi - z_start
            outer = gamma_w * z_local
            if mode == "hydrodynamic":
                outer += sign * (7.0/8.0) * kh * gamma_w * math.sqrt(Hw * z_local)
                sign_txt = "+" if sign >= 0 else "−"
                comment = f"contains retained-side total stress + outer-face hydrostatic {sign_txt} hydrodynamic"
            sigma[i] += outer
    return {"z": z, "sigma": sigma, "comment": comment}


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


def integrated_force_from_profile(profile):
    if not profile or not profile.get("z") or not profile.get("sigma"):
        return 0.0
    return positive_resultant_from_arrays(profile["z"], profile["sigma"])[0]


def resultant_from_profile(profile):
    if not profile or not profile.get("z") or not profile.get("sigma"):
        return 0.0, 0.0
    return positive_resultant_from_arrays(profile["z"], profile["sigma"])


def wall_x_at_depth(H, alpha_deg, z_from_surface):
    if H <= 0:
        return 0.0
    xb = H * math.tan(math.radians(alpha_deg))
    return xb * (z_from_surface / H)


def _dbg_num(v):
    if v is None:
        return "None"
    try:
        if isinstance(v, complex):
            return f"{v.real:.12g}{v.imag:+.12g}j"
        return f"{float(v):.12g}"
    except Exception:
        return str(v)

def _debug_append(lines, label, value):
    lines.append(f"{label} = {_dbg_num(value)}")

def build_cut_trace_for_z_mode(zq, mode, layers, H, beta_deg, alphaH, av, gamma_w, zwt, q,
                               inner_flow, retained_water_mode):
    lines = []
    zq = max(0.0, min(H, float(zq)))
    z_eval = max(zq, 0.001)
    layer = layer_at_z(layers, z_eval)
    c0_input = max(layer["c"], 0.001)
    sv, u_h = sigma_v_u_layered(z_eval, layers, zwt, gamma_w)
    _, _, u_d, _ = retained_side_u_total(
        z_eval, H, layers, zwt, gamma_w, alphaH, inner_flow,
        include_dynamic=(retained_water_mode == "hydrodynamic")
    )

    lines.append(f"CUT {mode.upper()} at z = {_dbg_num(zq)} m")
    lines.append("")
    lines.append("1. Input data at this depth")
    _debug_append(lines, "z", zq)
    _debug_append(lines, "z_eval used by CUT", z_eval)
    _debug_append(lines, "Layer.phi", layer["phi"])
    _debug_append(lines, "Layer.c", layer["c"])
    _debug_append(lines, "Layer.gd", layer["gd"])
    _debug_append(lines, "Layer.gs", layer["gs"])
    _debug_append(lines, "alphaH = kh", alphaH)
    _debug_append(lines, "a_v = kv", av)
    _debug_append(lines, "beta", beta_deg)
    _debug_append(lines, "q", q)
    lines.append("")

    lines.append("2. Vertical stress and pore pressures")
    _debug_append(lines, "sigma_v", sv)
    _debug_append(lines, "u_h", u_h)
    _debug_append(lines, "u_d", u_d)
    _debug_append(lines, "sigma_v - u_h", sv - u_h)
    lines.append("")

    lines.append("3. Internal cohesion floor used by CUT")
    _debug_append(lines, "c0 = max(c, 0.001)", c0_input)
    lines.append("")

    try:
        phi_adj, c_adj, gamma_adj, dsig_beta = cut_empirical_adjustment(
            layer["phi"], c0_input, layer["gd"], beta_deg, 0.0, mode, z=z_eval
        )

        lines.append("4. Empirical backslope correction (applied only through beta)")
        _debug_append(lines, "phi_adj", phi_adj)
        _debug_append(lines, "c_adj", c_adj)
        _debug_append(lines, "gamma_adj", gamma_adj)
        _debug_append(lines, "Delta sigma_beta", dsig_beta)
        lines.append("")

        sigma_v_adj = sv + dsig_beta
        theta_adj = cut_theta_eq(alphaH, av, sigma_v_adj, u_h)

        lines.append("5. Adjusted vertical stress and seismic angle")
        _debug_append(lines, "sigma_v_adj = sigma_v + Delta sigma_beta", sigma_v_adj)
        _debug_append(lines, "theta_eq (deg)", math.degrees(theta_adj))
        lines.append("")

        xi, xi1, xi2 = cut_failure_xi_set()
        lines.append("6. Failure-state constants")
        _debug_append(lines, "xi", xi)
        _debug_append(lines, "xi1", xi1)
        _debug_append(lines, "xi2", xi2)
        lines.append("")

        lam, A0, B1 = cut_lambda_a0_b1(phi_adj, c_adj, sigma_v_adj, u_h, theta_adj, av, xi, xi1, xi2, mode)

        lines.append("7. Compute lambda, A0, B1")
        if mode == "active":
            lines.append("lambda criterion: active state -> lambda = 1.0 by definition")
        else:
            lines.append("lambda criterion: passive state -> lambda = 0 if A0 >= 1, else lambda = 1")
        _debug_append(lines, "lambda", lam)
        _debug_append(lines, "A0", A0)
        _debug_append(lines, "B1", B1)
        lines.append("")

        phim = cut_phi_m_from_parameters(phi_adj, c_adj, sigma_v_adj, u_h, theta_adj, av, xi, xi1, xi2, mode)

        lines.append("8. Cubic-solution intermediates for phi_m")
        _debug_append(lines, "e1", phim["e1"])
        _debug_append(lines, "e2", phim["e2"])
        _debug_append(lines, "a0", phim["a0"])
        _debug_append(lines, "b0", phim["b0"])
        _debug_append(lines, "c0_cubic", phim["c0"])
        _debug_append(lines, "d0", phim["d0"])
        _debug_append(lines, "D0", phim["D0"])
        _debug_append(lines, "D1", phim["D1"])
        _debug_append(lines, "C0", phim["C0"])
        lines.append("zeta = -1/2 + sqrt(3)/2 * i")
        _debug_append(lines, "phi_m (deg)", phim["phi_m_deg"])
        lines.append("")

        KXE, c_m, sigma_xe = cut_kxe_from_phi_m(phim["phi_m_deg"], phi_adj, c_adj, sigma_v_adj, u_h, av, phim["lambda"])
        qterm_i = KXE * q
        sigma_total = sigma_xe + qterm_i + u_d

        lines.append("9. Final CUT quantities")
        _debug_append(lines, "K_XE", KXE)
        _debug_append(lines, "c_m", c_m)
        _debug_append(lines, "sigma_xe", sigma_xe)
        _debug_append(lines, "K_XE * q", qterm_i)
        _debug_append(lines, "final sigma_raw = sigma_xe + K_XE*q + u_d", sigma_total)
        if sigma_total < 0.0:
            lines.append("final status = TENSION -> rejected (not plotted, not included in resultant)")
        else:
            _debug_append(lines, "final sigma accepted", sigma_total)
    except Exception as e:
        lines.append(f"ERROR: {e}")

    return "\n".join(lines)

# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title(PROGRAM_NAME)
        try:
            root.state('zoomed')
        except Exception:
            pass

        style = ttk.Style(root)
        try:
            if style.theme_use() == "classic":
                style.theme_use("default")
        except Exception:
            pass
        style.configure("Treeview", rowheight=22, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Small.TLabel", font=("Segoe UI", 9))

        main = ttk.Frame(root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1); root.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1); main.rowconfigure(0, weight=1)

        # left scrollable
        left_outer = ttk.Frame(main); left_outer.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        left_outer.columnconfigure(0, weight=1); left_outer.rowconfigure(0, weight=1)
        self.left_canvas = tk.Canvas(left_outer, width=480, highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=self.left_canvas.yview)
        self.left_canvas.grid(row=0, column=0, sticky="nsew"); left_scroll.grid(row=0, column=1, sticky="ns")
        self.left_canvas.configure(yscrollcommand=left_scroll.set)
        self.left_inner = ttk.Frame(self.left_canvas)
        self.left_window = self.left_canvas.create_window((0,0), window=self.left_inner, anchor="nw")
        self.left_inner.bind("<Configure>", lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.bind("<Configure>", lambda e: self.left_canvas.itemconfigure(self.left_window, width=e.width))
        self.left_canvas.bind_all("<MouseWheel>", lambda e: self.left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        right = ttk.Frame(main); right.grid(row=0,column=1,sticky="nsew")
        right.columnconfigure(0, weight=1); right.rowconfigure(0, weight=1)

        # toolbar
        toolbar = ttk.Frame(self.left_inner); toolbar.grid(row=0, column=0, sticky="w", pady=(0,8))
        self._compute_img = self._home_img = None
        compute_added=False
        for name in ["cut_tepak_logo.png","100tepak-logo.png","cut_logo.png"]:
            p = find_local_file(name)
            if p:
                try:
                    self._compute_img = load_button_image(p,84,84)
                    ttk.Button(toolbar, image=self._compute_img, command=self.compute).grid(row=0,column=0,padx=(0,6))
                    compute_added=True; break
                except Exception:
                    pass
        if not compute_added:
            try:
                tmp = os.path.join(tempfile.gettempdir(), "cut_tepak_logo.png")
                if not os.path.exists(tmp):
                    urllib.request.urlretrieve(CUT_LOGO_URL, tmp)
                self._compute_img = load_button_image(tmp,84,84)
                ttk.Button(toolbar, image=self._compute_img, command=self.compute).grid(row=0,column=0,padx=(0,6))
                compute_added=True
            except Exception:
                pass
        if not compute_added:
            ttk.Button(toolbar, text="Compute", command=self.compute).grid(row=0,column=0,padx=(0,6))
        ttk.Button(toolbar, text="User Manual", command=self.open_user_manual).grid(row=0,column=1,padx=6)
        home = find_local_file("home.png")
        if home:
            try:
                self._home_img = load_home_button_image(home,84)
                ttk.Button(toolbar, image=self._home_img, command=self.open_home).grid(row=0,column=2,padx=6)
            except Exception:
                ttk.Button(toolbar, text="Home", command=self.open_home).grid(row=0,column=2,padx=6)
        else:
            ttk.Button(toolbar, text="Home", command=self.open_home).grid(row=0,column=2,padx=6)
        ttk.Button(toolbar, text="Report", command=self.show_report).grid(row=0,column=3,padx=6)
        ttk.Button(toolbar, text="About", command=self.show_about).grid(row=0,column=4,padx=6)

        # input sections
        body = ttk.Frame(self.left_inner); body.grid(row=1,column=0,sticky="ew")
        body.columnconfigure(0, weight=1)

        wall = ttk.LabelFrame(body, text="Wall data")
        wall.grid(row=0,column=0,sticky="ew", pady=(0,6))
        seismic = ttk.LabelFrame(body, text="Seismic data")
        seismic.grid(row=1,column=0,sticky="ew", pady=(0,6))
        water = ttk.LabelFrame(body, text="Water data")
        water.grid(row=2,column=0,sticky="ew", pady=(0,6))
        soil = ttk.LabelFrame(body, text="Soil data (layers from top to bottom)")
        soil.grid(row=3,column=0,sticky="ew", pady=(0,6))
        loads = ttk.LabelFrame(body, text="Additional loads")
        loads.grid(row=4,column=0,sticky="ew", pady=(0,6))

        for frame in [wall, seismic, water, loads]:
            frame.grid_columnconfigure(0, minsize=250)
            frame.grid_columnconfigure(1, minsize=110)
        water.grid_columnconfigure(2, minsize=140)
        water.grid_columnconfigure(3, minsize=140)
    
        self.alpha = tk.DoubleVar(value=0.0)
        self.beta = tk.DoubleVar(value=0.0)
        self.delta = tk.DoubleVar(value=0.0)
        self.gamma_phi = tk.DoubleVar(value=1.0)
        self.water_case = tk.StringVar(value="E.5: Water table below wall")  # hidden temporary default
        self.kh = tk.DoubleVar(value=0.10)
        self.kv_abs = tk.DoubleVar(value=0.0)
        self.kv_negative = tk.BooleanVar(value=False)
        self.aashto_allow_kv = tk.BooleanVar(value=False)  # hidden temporary default
        self.aashto_factor = tk.DoubleVar(value=0.50)
        self.zwt = tk.DoubleVar(value=6.0)
        # FORCE Hw = 0 and disable the field
        self.Hw = tk.DoubleVar(value=0.0)
        self.inner_flow_mode = tk.StringVar(value="impervious")
        self.water_action_mode = tk.StringVar(value="hydrostatic")
        self.gamma_w = tk.DoubleVar(value=9.81)
        self.q = tk.DoubleVar(value=0.0)
        self.allow_qc_to_en_aashto = tk.BooleanVar(value=True)

        def add_entry(parent,row,label,var,width=10):
            ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",padx=6,pady=3)
            ttk.Entry(parent,textvariable=var,width=width).grid(row=row,column=1,sticky="w",padx=6,pady=3)

        add_entry(wall,0,"Wall batter α (deg)\nfrom vertical; + into soil",self.alpha)
        add_entry(wall,1,"Backfill slope β (deg)\nfrom horizontal",self.beta)
        add_entry(wall,2,"Wall-soil friction angle δ (deg)",self.delta)
        add_entry(wall,3,"γφ' (partial factor for EN)",self.gamma_phi)

        add_entry(seismic,0,"Horizontal seismic coefficient\n(kh in EN/AASHTO, αH in prEN)", self.kh)
        add_entry(seismic,1,"Absolute value of vertical seismic coefficient", self.kv_abs)
        tk.Checkbutton(seismic,text="Use upward seismic force (kv = −|kv|)",variable=self.kv_negative,fg="red").grid(row=2,column=0,columnspan=2,sticky="w",padx=6,pady=(0,3))
        add_entry(seismic,3,"AASHTO reduction factor for kh", self.aashto_factor)
        ttk.Label(seismic, text="A positive |kv| corresponds to downward seismic force.\nAASHTO: kv = 0 for design.", style="Small.TLabel").grid(row=4,column=0,columnspan=2,sticky="w",padx=6,pady=(0,3))

        add_entry(water,0,"zwt (m) water table depth from surface z=0", self.zwt)
        add_entry(water,1,"γw (kN/m³)", self.gamma_w)
        ttk.Label(water,text="Retained-side soil condition").grid(row=2,column=0,sticky="w",padx=6,pady=3)
        ttk.Combobox(water, textvariable=self.inner_flow_mode, values=["impervious","pervious"], state="readonly", width=14).grid(row=2,column=1,sticky="w",padx=6,pady=3)
        ttk.Label(water,text="Retained-side water mode").grid(row=3,column=0,sticky="w",padx=6,pady=3)
        ttk.Combobox(water, textvariable=self.water_action_mode, values=["hydrostatic","hydrodynamic"], state="readonly", width=14).grid(row=3,column=1,sticky="w",padx=6,pady=3)

        add_entry(loads,0,"q (kPa) surcharge", self.q)
        tk.Checkbutton(loads,text="Apply the logic of prEN1998-5 for q and c to EN1998-5:2004 and AASHTO",variable=self.allow_qc_to_en_aashto,fg="red").grid(row=1,column=0,columnspan=2,sticky="w",padx=6,pady=(0,3))

        # dynamic layers
        self.layer_rows = []
        self.layer_selected = tk.IntVar(value=0)
        self.layer_edit_frame = ttk.Frame(soil)
        self.layer_edit_frame.grid(row=0, column=0, columnspan=7, sticky="ew")
        self.add_layer_row(30.0, 0.0, 18.0, 20.0, 6.0)
        ttk.Button(soil,text="Add layer",command=lambda:self.add_layer_row(30.0,0.0,18.0,20.0,1.0)).grid(row=1,column=0,padx=4,pady=4,sticky="w")
        ttk.Button(soil,text="Remove selected",command=self.remove_selected_layer).grid(row=1,column=1,padx=4,pady=4,sticky="w")

        ttk.Frame(self.left_inner, height=80).grid(row=2,column=0,sticky="ew")

        # tabs
        self.nb = ttk.Notebook(right); self.nb.grid(row=0,column=0,sticky="nsew")
        nb = self.nb
        self.tab_data = ttk.Frame(nb); self.tab_dp = ttk.Frame(nb); self.tab_trace = ttk.Frame(nb); self.tab_results = ttk.Frame(nb); self.tab_dist = ttk.Frame(nb)
        nb.add(self.tab_data, text="Point level results"); nb.add(self.tab_trace, text="CUT detailed calculations at z"); nb.add(self.tab_results, text="Resultant forces and point of application"); nb.add(self.tab_dist, text="Pressure distributions")

        # Data tab geometry
        self.tab_data.columnconfigure(0,weight=1)
        self.tab_data.rowconfigure(0,weight=5)
        self.tab_data.rowconfigure(1,weight=0)
        self.tab_data.rowconfigure(2,weight=3)
        self.tab_data.rowconfigure(3,weight=0)
        gp = ttk.LabelFrame(self.tab_data, text="Indicative geometry"); gp.grid(row=0,column=0,sticky="nsew",padx=4,pady=4)
        fig = Figure(figsize=(7.8,5.0),dpi=100); self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=gp); self.canvas.get_tk_widget().grid(row=0,column=0,sticky="nsew")
        gp.columnconfigure(0,weight=1); gp.rowconfigure(0,weight=1)

        # Relocated results-at-z controls and table below the drawing (independent from the original Results at z tab)
        dz_controls = ttk.Frame(self.tab_data)
        dz_controls.grid(row=1,column=0,sticky="ew",padx=4,pady=(0,2))
        dz_controls.columnconfigure(5,weight=1)
        self.z_query_data = tk.DoubleVar(value=0.0)
        ttk.Label(dz_controls, text="z (m) from surface").grid(row=0,column=0,sticky="w",padx=(2,6),pady=2)
        ttk.Entry(dz_controls,textvariable=self.z_query_data,width=10).grid(row=0,column=1,sticky="w",padx=(0,6),pady=2)
        ttk.Button(dz_controls,text="Update z table",command=self.compute).grid(row=0,column=2,sticky="w",padx=(0,8),pady=2)

        dz = ttk.LabelFrame(self.tab_data, text="Results at z")
        dz.grid(row=2,column=0,sticky="nsew",padx=4,pady=(0,4))
        dz.columnconfigure(0,weight=1); dz.rowconfigure(0,weight=1)

        # Results at z
        self.tab_dp.columnconfigure(0,weight=1); self.tab_dp.rowconfigure(0,weight=1)
        zp = ttk.LabelFrame(self.tab_dp, text="Results at z")
        zp.grid(row=0,column=0,sticky="nsew",padx=4,pady=4)
        self.z_query = tk.DoubleVar(value=0.0)
        ttk.Label(zp, text="z (m) from surface").grid(row=0,column=0,sticky="w",padx=6,pady=4)
        ttk.Entry(zp,textvariable=self.z_query,width=10).grid(row=0,column=1,sticky="w",padx=6,pady=4)
        ttk.Button(zp,text="Update z table",command=self.compute).grid(row=0,column=2,sticky="w",padx=(6,8),pady=4)

        # Updated column definitions - WITHOUT w column
        zcols = ("method","sigma_eff","u","ud","kqterm","kcterm","sigma_total","kgamma","kq","kc")
        zheads={"method":"Method","sigma_eff":"σ'=Kγ(σv−u)","u":"u","ud":"u_d","kqterm":"Kq,term","kcterm":"Kc,term","sigma_total":"σa or σp","kgamma":"Kγ","kq":"Kq","kc":"Kc"}
        zw={"method":108,"sigma_eff":90,"u":50,"ud":50,"kqterm":70,"kcterm":70,"sigma_total":80,"kgamma":50,"kq":50,"kc":50}

        self.z_tree = ttk.Treeview(zp, columns=zcols, show="headings", height=8)
        for c in zcols:
            self.z_tree.heading(c, text=zheads[c])
            self.z_tree.column(c, width=zw[c], anchor="center", stretch=False)

        xscroll_z = ttk.Scrollbar(zp, orient="horizontal", command=self.z_tree.xview)
        self.z_tree.configure(xscrollcommand=xscroll_z.set)

        self.z_tree.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=4, pady=4)
        xscroll_z.grid(row=2, column=0, columnspan=3, sticky="ew")

        self.z_tree_copy = ttk.Treeview(dz, columns=zcols, show="headings", height=8)
        for c in zcols:
            self.z_tree_copy.heading(c, text=zheads[c])
            self.z_tree_copy.column(c, width=zw[c], anchor="center", stretch=False)

        xscroll_z_copy = ttk.Scrollbar(dz, orient="horizontal", command=self.z_tree_copy.xview)
        self.z_tree_copy.configure(xscrollcommand=xscroll_z_copy.set)

        self.z_tree_copy.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        xscroll_z_copy.grid(row=1, column=0, sticky="ew")

        ttk.Label(
            self.tab_data,
            text="NOTE: NR = No real solution (negative value under square root).",
            style="Small.TLabel"
        ).grid(row=3, column=0, sticky="w", padx=6, pady=(0,4))

        zp.columnconfigure(0,weight=1); zp.rowconfigure(1,weight=1)

        # CUT detailed calculations at z tab
        self.tab_trace.columnconfigure(0, weight=1)
        self.tab_trace.rowconfigure(1, weight=1)
        trace_controls = ttk.Frame(self.tab_trace)
        trace_controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        trace_controls.columnconfigure(4, weight=1)
        self.z_query_trace = tk.DoubleVar(value=0.0)
        ttk.Label(trace_controls, text="z (m) from surface").grid(row=0, column=0, sticky="w", padx=(0,6), pady=2)
        ttk.Entry(trace_controls, textvariable=self.z_query_trace, width=10).grid(row=0, column=1, sticky="w", padx=(0,6), pady=2)
        ttk.Button(trace_controls, text="Update CUT calculations", command=self.compute).grid(row=0, column=2, sticky="w", padx=(0,8), pady=2)

        trace_box = ttk.Frame(self.tab_trace)
        trace_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0,6))
        trace_box.columnconfigure(0, weight=1)
        trace_box.columnconfigure(1, weight=1)
        trace_box.rowconfigure(0, weight=1)

        active_trace_box = ttk.LabelFrame(trace_box, text="Active CUT")
        active_trace_box.grid(row=0, column=0, sticky="nsew", padx=(0,3))
        active_trace_box.columnconfigure(0, weight=1); active_trace_box.rowconfigure(0, weight=1)
        self.text_trace_active = tk.Text(active_trace_box, wrap="word", font=("Consolas", 10), padx=10, pady=8)
        trace_scroll_a = ttk.Scrollbar(active_trace_box, orient="vertical", command=self.text_trace_active.yview)
        self.text_trace_active.configure(yscrollcommand=trace_scroll_a.set)
        self.text_trace_active.grid(row=0, column=0, sticky="nsew")
        trace_scroll_a.grid(row=0, column=1, sticky="ns")

        passive_trace_box = ttk.LabelFrame(trace_box, text="Passive CUT")
        passive_trace_box.grid(row=0, column=1, sticky="nsew", padx=(3,0))
        passive_trace_box.columnconfigure(0, weight=1); passive_trace_box.rowconfigure(0, weight=1)
        self.text_trace_passive = tk.Text(passive_trace_box, wrap="word", font=("Consolas", 10), padx=10, pady=8)
        trace_scroll_p = ttk.Scrollbar(passive_trace_box, orient="vertical", command=self.text_trace_passive.yview)
        self.text_trace_passive.configure(yscrollcommand=trace_scroll_p.set)
        self.text_trace_passive.grid(row=0, column=0, sticky="nsew")
        trace_scroll_p.grid(row=0, column=1, sticky="ns")

        # Results tab
        self.tab_results.columnconfigure(0,weight=1); self.tab_results.rowconfigure(0,weight=1)
        rc = ttk.Frame(self.tab_results); rc.grid(row=0,column=0,sticky="nsew",padx=4,pady=4)
        rc.columnconfigure(0,weight=1); rc.columnconfigure(1,weight=1)
        rc.rowconfigure(0,weight=0); rc.rowconfigure(1,weight=1)

        # hidden storage trees (kept for internal data/reporting)
        hidden_store = ttk.Frame(self.tab_results)
        hidden_cols=("method","kh","kv","force","kgamma","kq","kc","angle")
        def make_hidden_tree(parent):
            return ttk.Treeview(parent, columns=hidden_cols, show="headings", height=3)
        self.tree_active = make_hidden_tree(hidden_store)
        self.tree_passive = make_hidden_tree(hidden_store)

        active_box = ttk.LabelFrame(rc, text="Active notes / warnings")
        active_box.grid(row=1,column=0,sticky="nsew",padx=(0,4))
        active_box.columnconfigure(0,weight=1); active_box.rowconfigure(0,weight=1)
        self.text_active=tk.Text(active_box,height=18,wrap="word",font=("Segoe UI",10),padx=8,pady=6)
        self.text_active.grid(row=0,column=0,sticky="nsew")
        avs=ttk.Scrollbar(active_box,orient="vertical",command=self.text_active.yview)
        self.text_active.configure(yscrollcommand=avs.set); avs.grid(row=0,column=1,sticky="ns")

        passive_box = ttk.LabelFrame(rc, text="Passive notes / warnings")
        passive_box.grid(row=1,column=1,sticky="nsew",padx=(4,0))
        passive_box.columnconfigure(0,weight=1); passive_box.rowconfigure(0,weight=1)
        self.text_passive=tk.Text(passive_box,height=18,wrap="word",font=("Segoe UI",10),padx=8,pady=6)
        self.text_passive.grid(row=0,column=0,sticky="nsew")
        pvs=ttk.Scrollbar(passive_box,orient="vertical",command=self.text_passive.yview)
        self.text_passive.configure(yscrollcommand=pvs.set); pvs.grid(row=0,column=1,sticky="ns")

        summary_box = ttk.LabelFrame(rc, text="Resultant force and line of action")
        summary_box.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,8))
        summary_box.columnconfigure(0,weight=1)
        summary_cols=("method","aforce","ay","pforce","py")
        self.tree_summary = ttk.Treeview(summary_box, columns=summary_cols, show="headings", height=5)
        self.tree_summary.heading("method", text="Method")
        self.tree_summary.heading("aforce", text="Active resultant")
        self.tree_summary.heading("ay", text="Active line above base")
        self.tree_summary.heading("pforce", text="Passive resultant")
        self.tree_summary.heading("py", text="Passive line above base")
        self.tree_summary.column("method", width=130, anchor="center")
        self.tree_summary.column("aforce", width=130, anchor="center")
        self.tree_summary.column("ay", width=160, anchor="center")
        self.tree_summary.column("pforce", width=130, anchor="center")
        self.tree_summary.column("py", width=160, anchor="center")
        self.tree_summary.grid(row=0,column=0,sticky="ew",padx=4,pady=4)

        # Distribution - REMOVED outer-face water checkbox
        self.tab_dist.columnconfigure(0,weight=1); self.tab_dist.rowconfigure(0,weight=0); self.tab_dist.rowconfigure(1,weight=1)
        cp=ttk.LabelFrame(self.tab_dist,text="Included curves"); cp.grid(row=0,column=0,sticky="ew",padx=4,pady=(4,0))
        self.show_en_active=tk.BooleanVar(value=True); self.show_en_passive=tk.BooleanVar(value=True); self.show_pren_active=tk.BooleanVar(value=True); self.show_pren_passive=tk.BooleanVar(value=True); self.show_aashto_active=tk.BooleanVar(value=True)
        # Removed "Add outer-face water" checkbox - only these 5 remain
        for j,(txt,var) in enumerate([("EN active",self.show_en_active),("EN passive",self.show_en_passive),("prEN active",self.show_pren_active),("prEN passive",self.show_pren_passive),("AASHTO active",self.show_aashto_active)]):
            tk.Checkbutton(cp,text=txt,variable=var,fg="red",command=self.compute).grid(row=0,column=j,sticky="w",padx=6,pady=2)
        df=ttk.Frame(self.tab_dist); df.grid(row=1,column=0,sticky="nsew",padx=4,pady=4)
        df.columnconfigure(0,weight=1); df.rowconfigure(0,weight=1); df.rowconfigure(1,weight=1)
        self.dist_fig=Figure(figsize=(7.8,5.8),dpi=100); self.dist_fig.subplots_adjust(hspace=0.34,top=0.92,bottom=0.09)
        self.axd1=self.dist_fig.add_subplot(211); self.axd2=self.dist_fig.add_subplot(212)
        self.canvas_dist=FigureCanvasTkAgg(self.dist_fig,master=df); self.canvas_dist.get_tk_widget().grid(row=0,column=0,rowspan=2,sticky="nsew")

        self.compute()


    def render_layer_rows(self):
        for w in self.layer_edit_frame.winfo_children():
            w.destroy()
        hdr = ["Sel","No.","Thickness","φ'","c'","γ","γsat"]
        for j,h in enumerate(hdr):
            ttk.Label(self.layer_edit_frame, text=h).grid(row=0, column=j, padx=4, pady=3, sticky="w")
        for i, row in enumerate(self.layer_rows, start=1):
            tk.Radiobutton(self.layer_edit_frame, variable=self.layer_selected, value=i-1).grid(row=i, column=0, padx=4, pady=2)
            ttk.Label(self.layer_edit_frame, text=str(i), width=3).grid(row=i, column=1, padx=4, pady=2, sticky="w")
            ttk.Entry(self.layer_edit_frame, textvariable=row["thk"], width=8).grid(row=i, column=2, padx=4, pady=2)
            ttk.Entry(self.layer_edit_frame, textvariable=row["phi"], width=8).grid(row=i, column=3, padx=4, pady=2)
            ttk.Entry(self.layer_edit_frame, textvariable=row["c"], width=8).grid(row=i, column=4, padx=4, pady=2)
            ttk.Entry(self.layer_edit_frame, textvariable=row["gd"], width=8).grid(row=i, column=5, padx=4, pady=2)
            ttk.Entry(self.layer_edit_frame, textvariable=row["gs"], width=8).grid(row=i, column=6, padx=4, pady=2)

    def add_layer_row(self, phi, c, gd, gs, thk):
        row = {"thk": tk.DoubleVar(value=thk), "phi": tk.DoubleVar(value=phi), "c": tk.DoubleVar(value=c), "gd": tk.DoubleVar(value=gd), "gs": tk.DoubleVar(value=gs)}
        self.layer_rows.append(row)
        self.layer_selected.set(len(self.layer_rows)-1)
        self.render_layer_rows()

    def remove_selected_layer(self):
        idx = self.layer_selected.get()
        if 0 <= idx < len(self.layer_rows):
            self.layer_rows.pop(idx)
        if not self.layer_rows:
            self.layer_rows.append({"thk": tk.DoubleVar(value=6.0), "phi": tk.DoubleVar(value=30.0), "c": tk.DoubleVar(value=0.0), "gd": tk.DoubleVar(value=18.0), "gs": tk.DoubleVar(value=20.0)})
        self.layer_selected.set(max(0, min(idx, len(self.layer_rows)-1)))
        self.render_layer_rows()
        self.compute()

    def open_home(self): webbrowser.open(HOME_URL)

    def _tree_rows(self, tree):
        rows = []
        for item in tree.get_children():
            rows.append(tree.item(item).get("values", []))
        return rows

    def _build_report_text(self):
        layers = build_layers(self.layer_rows)
        lines = [
            PROGRAM_NAME,
            VERSION,
            AUTHOR,
            "",
            "ABOUT",
            "Layered input layout active. EN, AASHTO, and prEN distributions use pointwise stresses with local θ(z) based on σv and u.",
            "",
            "INPUTS",
            f"Wall batter α (deg): {self.alpha.get():.3f}",
            f"Backfill slope β (deg): {self.beta.get():.3f}",
            f"Wall-soil friction angle δ (deg): {self.delta.get():.3f}",
            f"γφ': {self.gamma_phi.get():.3f}",
            f"kh / αH: {self.kh.get():.3f}",
            f"|kv|: {self.kv_abs.get():.3f}",
            f"Use upward kv: {bool(self.kv_negative.get())}",
            f"AASHTO reduction factor: {self.aashto_factor.get():.3f}",
            f"zwt (m): {self.zwt.get():.3f}",
            f"Retained-side water mode: {self.water_action_mode.get()}",
            f"γw (kN/m³): {self.gamma_w.get():.3f}",
            f"Retained-side soil condition: {self.inner_flow_mode.get()}",
            f"q (kPa): {self.q.get():.3f}",
            f"Apply prEN logic of q and c to EN/AASHTO: {bool(self.allow_qc_to_en_aashto.get())}",
            "",
            "LAYERS",
        ]
        for i, layer in enumerate(layers, start=1):
            lines.append(f"L{i}: thickness={layer['thk']:.3f} m, φ'={layer['phi']:.3f}°, c'={layer['c']:.3f}, γ={layer['gd']:.3f}, γsat={layer['gs']:.3f}")
        lines += [
            "",
            "RESULTANT FORCES AND POINTS OF APPLICATION",
        ]
        for row in self._tree_rows(self.tree_summary):
            lines.append(" | ".join(str(v) for v in row))
        lines += ["", "ACTIVE PRACTICAL NOTES", self.text_active.get("1.0","end").strip(), "", "PASSIVE PRACTICAL NOTES", self.text_passive.get("1.0","end").strip()]
        return "\n".join(lines)

    def _summary_rows_for_report(self):
        return self._tree_rows(self.tree_summary)

    def _create_summary_tree(self, parent, height=5):
        summary_cols=("method","aforce","ay","pforce","py")
        tree = ttk.Treeview(parent, columns=summary_cols, show="headings", height=height)
        tree.heading("method", text="Method")
        tree.heading("aforce", text="Active resultant")
        tree.heading("ay", text="Active point above base")
        tree.heading("pforce", text="Passive resultant")
        tree.heading("py", text="Passive point above base")
        tree.column("method", width=140, anchor="center")
        tree.column("aforce", width=150, anchor="center")
        tree.column("ay", width=180, anchor="center")
        tree.column("pforce", width=150, anchor="center")
        tree.column("py", width=180, anchor="center")
        for row in self._summary_rows_for_report():
            tree.insert("", "end", values=row)
        return tree

    def export_report_pdf(self):
        try:
            default_name = f"{PROGRAM_NAME}_{VERSION}_report.pdf"
            pdf_path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export report as PDF",
                defaultextension=".pdf",
                initialfile=default_name,
                filetypes=[("PDF files", "*.pdf")]
            )
            if not pdf_path:
                return

            self.root.update_idletasks()
            geom_path = os.path.join(tempfile.gettempdir(), "cut_report_geometry_pdf.png")
            dist_path = os.path.join(tempfile.gettempdir(), "cut_report_charts_pdf.png")
            self.canvas.figure.savefig(geom_path, dpi=180, bbox_inches="tight")
            self.canvas_dist.figure.savefig(dist_path, dpi=180, bbox_inches="tight")

            c = pdf_canvas.Canvas(pdf_path, pagesize=A4)
            width, height = A4
            left = 40
            top = height - 40

            c.setFont("Helvetica-Bold", 14)
            c.drawString(left, top, PROGRAM_NAME)
            c.setFont("Helvetica", 10)
            c.drawString(left, top - 16, f"{VERSION} | {AUTHOR}")

            y = top - 42
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Resultant forces and points of application")
            y -= 16
            c.setFont("Helvetica", 9)
            headers = ["Method", "Active resultant", "Active point above base", "Passive resultant", "Passive point above base"]
            col_x = [left, left + 90, left + 210, left + 360, left + 470]
            for i, htxt in enumerate(headers):
                c.drawString(col_x[i], y, htxt)
            y -= 10
            c.line(left, y, width - left, y)
            y -= 14
            for row in self._summary_rows_for_report():
                vals = [str(v) for v in row]
                for i, val in enumerate(vals):
                    c.drawString(col_x[i], y, val)
                y -= 14

            y -= 6
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Active practical notes")
            y -= 14
            c.setFont("Helvetica", 9)
            for line in self.text_active.get("1.0", "end").strip().splitlines():
                if y < 70:
                    c.showPage()
                    y = height - 40
                    c.setFont("Helvetica", 9)
                c.drawString(left, y, line[:120])
                y -= 12

            y -= 8
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Passive practical notes")
            y -= 14
            c.setFont("Helvetica", 9)
            for line in self.text_passive.get("1.0", "end").strip().splitlines():
                if y < 70:
                    c.showPage()
                    y = height - 40
                    c.setFont("Helvetica", 9)
                c.drawString(left, y, line[:120])
                y -= 12

            c.showPage()
            pw, ph = landscape(A4)
            c.setPageSize((pw, ph))
            c.setFont("Helvetica-Bold", 12)
            c.drawString(30, ph - 30, "Indicative geometry")
            geom_reader = ImageReader(geom_path)
            iw, ih = geom_reader.getSize()
            scale = min((pw - 60) / iw, (ph - 70) / ih)
            c.drawImage(geom_reader, 30, ph - 40 - ih * scale, width=iw * scale, height=ih * scale)

            c.showPage()
            c.setPageSize((pw, ph))
            c.setFont("Helvetica-Bold", 12)
            c.drawString(30, ph - 30, "Pressure distributions")
            dist_reader = ImageReader(dist_path)
            iw, ih = dist_reader.getSize()
            scale = min((pw - 60) / iw, (ph - 70) / ih)
            c.drawImage(dist_reader, 30, ph - 40 - ih * scale, width=iw * scale, height=ih * scale)

            c.save()
            messagebox.showinfo("PDF export", f"PDF report saved to:\n{pdf_path}")
        except Exception as e:
            messagebox.showerror("PDF export", f"Could not export PDF report:\n{e}")

    def open_user_manual(self):
        base = script_dir()
        for name in ["CUT_K_Coulomb_User_Manual.pdf", "User_Manual.pdf", "CUT_Bearing_Capacity_User_Manual.pdf"]:
            p = os.path.join(base, name)
            if os.path.exists(p):
                if sys.platform.startswith("win"): os.startfile(p)
                elif sys.platform == "darwin": subprocess.Popen(["open", p])
                else: subprocess.Popen(["xdg-open", p])
                return
        messagebox.showinfo("User Manual", "No user manual PDF was found in this folder.")

    def show_report(self):
        win = tk.Toplevel(self.root)
        win.title("Report")
        win.geometry("1100x800")

        outer = ttk.Frame(win, padding=8)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0,8))

        logo_path = find_local_file("cut_tepak_logo.png") or find_local_file("100tepak-logo.png") or find_local_file("cut_logo.png")
        self._report_logo = None
        if logo_path:
            try:
                self._report_logo = load_button_image(logo_path, 84, 84)
                ttk.Label(header, image=self._report_logo).pack(side="left", padx=(0,10))
            except Exception:
                pass

        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text=PROGRAM_NAME, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(title_box, text=f"{VERSION} | {AUTHOR}", style="Small.TLabel").pack(anchor="w")
        ttk.Button(header, text="Export PDF", command=self.export_report_pdf).pack(side="right", padx=(10,0))

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        tab_text = ttk.Frame(nb)
        tab_geom = ttk.Frame(nb)
        tab_charts = ttk.Frame(nb)

        nb.add(tab_text, text="Summary and notes")
        nb.add(tab_geom, text="Drawing")
        nb.add(tab_charts, text="Pressure distributions")

        for tab in (tab_text, tab_geom, tab_charts):
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)

        text_frame = ttk.Frame(tab_text)
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.rowconfigure(1, weight=1)
        text_frame.columnconfigure(0, weight=1)

        summary_box = ttk.LabelFrame(text_frame, text="Resultant forces and points of application")
        summary_box.grid(row=0, column=0, sticky="ew", padx=4, pady=(0,8))
        summary_box.columnconfigure(0, weight=1)
        summary_tree = self._create_summary_tree(summary_box, height=5)
        summary_tree.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        txt_frame = ttk.Frame(text_frame)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.rowconfigure(0, weight=1)
        txt_frame.columnconfigure(0, weight=1)
        txt = tk.Text(txt_frame, wrap="word", font=("Segoe UI", 10), padx=10, pady=8)
        scr = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        txt.grid(row=0, column=0, sticky="nsew")
        scr.grid(row=0, column=1, sticky="ns")
        txt.insert("1.0", self._build_report_text())
        txt.configure(state="disabled")

        try:
            geom_path = os.path.join(tempfile.gettempdir(), "cut_report_geometry.png")
            self.canvas.figure.savefig(geom_path, dpi=150, bbox_inches="tight")
            img = Image.open(geom_path)
            img.thumbnail((900, 600), Image.LANCZOS)
            self._report_geom = ImageTk.PhotoImage(img)
            geom_label = ttk.Label(tab_geom, image=self._report_geom)
            geom_label.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            ttk.Label(tab_geom, text=f"Could not render drawing: {e}").grid(row=0, column=0, sticky="nw", padx=10, pady=10)

        try:
            dist_path = os.path.join(tempfile.gettempdir(), "cut_report_charts.png")
            self.canvas_dist.figure.savefig(dist_path, dpi=150, bbox_inches="tight")
            img2 = Image.open(dist_path)
            img2.thumbnail((900, 600), Image.LANCZOS)
            self._report_charts = ImageTk.PhotoImage(img2)
            charts_label = ttk.Label(tab_charts, image=self._report_charts)
            charts_label.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            ttk.Label(tab_charts, text=f"Could not render charts: {e}").grid(row=0, column=0, sticky="nw", padx=10, pady=10)

    def show_about(self):
        messagebox.showinfo(
            "About",
            f"{PROGRAM_NAME}\n"
            f"{VERSION}\n\n"
            "Dr Lysandros Pantelidis\n"
            "Cyprus University of Technology\n\n"
            "Educational software\n"
            "For teaching and research purposes only.\n\n"
            "No warranty is provided.\n"
            "Use at your own responsibility."
        )
    def _clear_tree(self, tree):
        for item in tree.get_children(): tree.delete(item)

    def _set_text(self, widget, content):
        widget.configure(state="normal"); widget.delete("1.0","end"); widget.insert("1.0",content); widget.configure(state="disabled")


    def draw_geometry(self, H, alpha, beta, zwt, Hw, layers):
        self.ax.clear()
        xb = H * math.tan(math.radians(alpha))
        x_end = max(4.0, 1.1*H, xb + 1.0)
        y_end = math.tan(math.radians(beta)) * x_end

        # wall in negative-y region, backfill positive beta goes upward
        self.ax.plot([0, xb], [0, -H], lw=2.4)
        self.ax.plot([0, x_end], [0, y_end], lw=1.9)
        self.ax.plot([-0.35*max(1,H), x_end], [0, 0], ls=":", alpha=0.6)

        self.ax.text(x_end*0.60, y_end + 0.05*max(1,H), f"β={beta:.2f}°", fontsize=9)
        self.ax.text(min(xb,0)-0.10*max(1,H), -0.12*H, f"α={alpha:.2f}°", fontsize=9)

        # layer boundaries, light fills, and layer properties
        layer_colors = ["#f7f3d6", "#d9ecff", "#e7f7dc", "#fde2e2", "#efe2ff", "#ffe9d6"]

        self.ax.plot([0, xb], [0, -H], lw=2.4)
        self.ax.plot([0, x_end], [0, y_end], lw=1.9)
        self.ax.plot([-0.35*max(1,H), x_end], [0, 0], ls=":", alpha=0.6)

        if y_end > 0:
            self.ax.fill(
                [0, x_end, x_end],
                [0, y_end, 0],
                facecolor=layer_colors[0],
                edgecolor='none',
                alpha=0.6,
                zorder=0
            )

    # layer boundaries, light fills, and layer properties
        for i, layer in enumerate(layers, start=1):
            z0p, z1p = layer["z0"], layer["z1"]
            zmid_pos = 0.5 * (z0p + z1p)
            zmid = -zmid_pos
            top_y, bot_y = -z0p, -z1p
            x_top = wall_x_at_depth(H, alpha, z0p)
            x_bot = wall_x_at_depth(H, alpha, z1p)
            color = layer_colors[(i-1) % len(layer_colors)]
            poly_x = [x_top, x_end, x_end, x_bot]
            poly_y = [top_y, top_y, bot_y, bot_y]
            self.ax.fill(poly_x, poly_y, facecolor=color, edgecolor='none', alpha=0.6, zorder=0)
            xtext = max(wall_x_at_depth(H, alpha, zmid_pos) + 0.35, x_end * 0.34)
            self.ax.text(
                xtext, zmid,
                f"L{i}: φ={layer['phi']:.1f}°, c'={layer['c']:.1f}, γ={layer['gd']:.1f}, γsat={layer['gs']:.1f}",
                fontsize=8, va="center"
            )
            if i < len(layers):
                zb_pos = layer["z1"]
                zb = -zb_pos
                x_layer = wall_x_at_depth(H, alpha, zb_pos)
                self.ax.plot([x_layer, x_end], [zb, zb], ls="--", alpha=0.45)

        # water table line starts from the wall
        if 0 <= zwt <= H:
            xw = wall_x_at_depth(H, alpha, zwt)
            ywt = -zwt
            self.ax.plot([xw, x_end], [ywt, ywt], ls="-.", lw=1.5)
            self.ax.text(x_end*0.78, ywt - 0.03*H, f"zwt={zwt:.2f} m", fontsize=9)

        # exposed water on the outer face - SKIP drawing since Hw=0
        # (kept for completeness but Hw is forced to 0)
        if Hw > 0:
            zws_pos = H - Hw
            yws = -zws_pos
            xw_outer = wall_x_at_depth(H, alpha, zws_pos)
            x_left = min(-0.18*H, -0.4)
            self.ax.plot([xw_outer, x_left], [yws, yws], ls=":", lw=2.0)
            self.ax.text(x_left - 0.05, yws - 0.03*H, f"Hw={Hw:.2f} m", fontsize=9)
            self.ax.text(x_left - 0.05, yws - 0.12*H, "outer-face water", fontsize=8)

        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel("x (m) →")
        self.ax.set_ylabel("z (m)")
        # dynamic limits based on wall geometry
        x_min = min(-0.4*H, -1.0)
        x_max = max(1.2*H, xb + 1.0)
        y_min = -1.1*H
        y_max = 0.2*H

        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(y_min, y_max)
        self.canvas.draw()
        
    def compute(self):
        try:
            # build layers
            layers = build_layers(self.layer_rows)
            if not layers:
                raise ValueError("At least one layer with positive thickness is required.")
            H = sum(layer["thk"] for layer in layers)
            alpha = float(self.alpha.get()); beta = float(self.beta.get()); delta = float(self.delta.get()); gamma_phi = float(self.gamma_phi.get())
            kh = float(self.kh.get()); kv_abs = float(self.kv_abs.get()); aashto_factor = float(self.aashto_factor.get())
            zwt = float(self.zwt.get()); gamma_w = float(self.gamma_w.get()); q = float(self.q.get())
            # FORCE Hw = 0
            Hw = 0.0
            self.Hw.set(0.0)  # ensure the variable stays 0
            kv = -kv_abs if self.kv_negative.get() else kv_abs
            delta_d = design_wall_friction_deg(delta, gamma_phi)

            inner_flow = self.inner_flow_mode.get()
            en_kv = kv
            aashto_kv = 0.0 if not self.aashto_allow_kv.get() else kv
            pren_zwt = zwt
            pren_Hw = Hw  # always 0
            retained_water_mode = self.water_action_mode.get()
            pren_alphaH = kh
            allow_qc_to_en_aashto = self.allow_qc_to_en_aashto.get()

            en_q = q if allow_qc_to_en_aashto else 0.0
            pren_q = q
            pren_c = True
            aashto_q = q if allow_qc_to_en_aashto else 0.0

            # temporary fixed logic flags for the current transitional build
            en_use_c = allow_qc_to_en_aashto
            pren_use_c = True
            pren_use_vertical = False
            aashto_use_c = allow_qc_to_en_aashto

            self._clear_tree(self.tree_active); self._clear_tree(self.tree_passive); self._clear_tree(self.z_tree); self._clear_tree(self.z_tree_copy); self._clear_tree(self.tree_summary)

            warnings = []
            ena_nr = enp_nr = prena_nr = prenp_nr = aask_nr = False

            # EN (pointwise implementation using local θ(z) from prEN)
            try:
                ena_prof = pointwise_method_profile(
                    "EN", "active", layers, H, alpha, beta, delta_d, kh, en_kv, gamma_w, zwt, en_q,
                    en_use_c, kh=kh, inner_flow=inner_flow,
                    include_retained_dynamic=(retained_water_mode == "hydrodynamic")
                )
                ena = {"K": ena_prof["base_K_gamma"], "theta_deg": ena_prof["base_theta_deg"], "gamma_star": None,
                       "Ews": 0.0, "Ewd": 0.0, "equation": "pointwise"}
                Ed_a_core = None
                Ed_a, yEd_a = ena_prof["P"], ena_prof["ybar_base"]
                Eaq = trapz(ena_prof["z"], ena_prof["qterm"])
                Ewa = trapz(ena_prof["z"], [ena_prof["u"][i] + ena_prof["ud"][i] for i in range(len(ena_prof["z"]))])
                Eac = trapz(ena_prof["z"], ena_prof["cterm"])
            except Exception as e:
                ena = None
                Ed_a_core = Eaq = Ewa = Eac = Ed_a = yEd_a = None
                ena_prof = {"z":[], "sigma":[]}
                ena_nr = _is_nr_error(e)
                warnings.append(f"EN active: {e}")

            try:
                enp_prof = pointwise_method_profile(
                    "EN", "passive", layers, H, alpha, beta, delta_d, kh, en_kv, gamma_w, zwt, en_q,
                    en_use_c, kh=kh, inner_flow=inner_flow,
                    include_retained_dynamic=(retained_water_mode == "hydrodynamic")
                )
                enp = {"K": enp_prof["base_K_gamma"], "theta_deg": enp_prof["base_theta_deg"], "gamma_star": None,
                       "Ews": 0.0, "Ewd": 0.0, "equation": "pointwise"}
                Ed_p_core = None
                Ed_p, yEd_p = enp_prof["P"], enp_prof["ybar_base"]
                Epq = trapz(enp_prof["z"], enp_prof["qterm"])
                Ewp = trapz(enp_prof["z"], [enp_prof["u"][i] + enp_prof["ud"][i] for i in range(len(enp_prof["z"]))])
                Epc = trapz(enp_prof["z"], enp_prof["cterm"])
            except Exception as e:
                enp = None
                Ed_p_core = Epq = Ewp = Epc = Ed_p = yEd_p = None
                enp_prof = {"z":[], "sigma":[]}
                enp_nr = _is_nr_error(e)
                warnings.append(f"EN passive: {e}")

            # prEN
            try:
                prena = pren_profile(
                    "active", layers, H, beta, delta, pren_alphaH, gamma_w, pren_zwt,
                    pren_q, pren_c, kh=kh, inner_flow=inner_flow,
                    include_retained_dynamic=(retained_water_mode == "hydrodynamic")
                )
            except Exception as e:
                prena = None
                prena_nr = _is_nr_error(e)
                warnings.append(f"prEN active: {e}")

            try:
                prenp = pren_profile(
                    "passive", layers, H, beta, delta, pren_alphaH, gamma_w, pren_zwt,
                    pren_q, pren_c, kh=kh, inner_flow=inner_flow,
                    include_retained_dynamic=(retained_water_mode == "hydrodynamic")
                )
            except Exception as e:
                prenp = None
                prenp_nr = _is_nr_error(e)
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

            # AASHTO (pointwise implementation using local θ(z) from prEN with kh reduced by AASHTO factor)
            kh_a = aashto_factor * kh
            theta_mo = math.degrees(math.atan(kh_a))
            aashto_adm = True
            try:
                aashto_prof = pointwise_method_profile(
                    "AASHTO", "active", layers, H, alpha, beta, delta_d, kh_a, aashto_kv, gamma_w, zwt, aashto_q,
                    aashto_use_c, kh=kh, inner_flow=inner_flow,
                    include_retained_dynamic=(retained_water_mode == "hydrodynamic")
                )
                aask = {"K": aashto_prof["base_K_gamma"], "theta_deg": aashto_prof["base_theta_deg"], "gamma_star": None,
                        "Ews": 0.0, "Ewd": 0.0, "equation": "pointwise"}
                P_AE, yP_AE = aashto_prof["P"], aashto_prof["ybar_base"]
            except Exception as e:
                aask = None
                P_AE = None
                yP_AE = None
                aashto_prof = None
                aask_nr = _is_nr_error(e)
                warnings.append(f"AASHTO active: {e}")

            # populate results tables
            Ed_a_disp = Ed_a
            if aask is not None and P_AE is not None:
                P_AE_disp = P_AE
            else:
                P_AE_disp = None

            self.tree_active.insert("", "end", values=(
                "EN 1998-5", f"{kh:.3f}", f"{en_kv:.3f}",
                _fmt_res3(Ed_a_disp, nr=ena_nr),
                _fmt_res4(ena['K'] if ena else None, nr=ena_nr),
                _fmt_res4(ena_prof['base_K_q'] if ena else (0.0 if not allow_qc_to_en_aashto else None), nr=ena_nr if allow_qc_to_en_aashto else False),
                _fmt_res4(ena_prof['base_K_c'] if ena else (0.0 if not allow_qc_to_en_aashto else None), nr=ena_nr if allow_qc_to_en_aashto else False),
                _fmt_theta(ena['theta_deg'] if ena else None, nr=ena_nr)
            ))
            self.tree_active.insert("", "end", values=(
                "prEN 1998-5", f"{pren_alphaH:.3f}", f"{kv if pren_use_vertical else 0.0:.3f}",
                _fmt_res3(prena['P'] if prena else None, nr=prena_nr),
                _fmt_res4(prena['base_K_gamma'] if prena else None, nr=prena_nr),
                _fmt_res4(prena['base_K_q'] if prena else None, nr=prena_nr),
                _fmt_res4(prena['base_K_c'] if prena else None, nr=prena_nr),
                _fmt_theta(prena['base_theta_deg'] if prena else None, nr=prena_nr)
            ))
            self.tree_active.insert("", "end", values=(
                "AASHTO", f"{kh_a:.3f}", f"{aashto_kv:.3f}",
                _fmt_res3(P_AE_disp, nr=aask_nr),
                _fmt_res4(aask['K'] if aask else None, nr=aask_nr),
                _fmt_res4(aashto_prof['base_K_q'] if aask else (0.0 if not allow_qc_to_en_aashto else None), nr=aask_nr if allow_qc_to_en_aashto else False),
                _fmt_res4(aashto_prof['base_K_c'] if aask else (0.0 if not allow_qc_to_en_aashto else None), nr=aask_nr if allow_qc_to_en_aashto else False),
                _fmt_theta(aask['theta_deg'] if aask else None, nr=aask_nr)
            ))
            self.tree_active.insert("", "end", values=(
                "CUT", f"{kh:.3f}", f"{en_kv:.3f}",
                _fmt_res3(cuta['P'] if cuta else None),
                _fmt_res4(cuta['base_K_gamma'] if cuta else None),
                _fmt_res4(cuta['base_K_q'] if cuta else None),
                _fmt_res4(0.0 if cuta else None),
                _fmt_theta(cuta['base_theta_deg'] if cuta else None)
            ))

            self.tree_passive.insert("", "end", values=(
                "EN 1998-5", f"{kh:.3f}", f"{en_kv:.3f}",
                _fmt_res3(Ed_p, nr=enp_nr),
                _fmt_res4(enp['K'] if enp else None, nr=enp_nr),
                _fmt_res4(enp_prof['base_K_q'] if enp else (0.0 if not allow_qc_to_en_aashto else None), nr=enp_nr if allow_qc_to_en_aashto else False),
                _fmt_res4(enp_prof['base_K_c'] if enp else (0.0 if not allow_qc_to_en_aashto else None), nr=enp_nr if allow_qc_to_en_aashto else False),
                _fmt_theta(enp['theta_deg'] if enp else None, nr=enp_nr)
            ))
            self.tree_passive.insert("", "end", values=(
                "prEN 1998-5", f"{pren_alphaH:.3f}", f"{kv if pren_use_vertical else 0.0:.3f}",
                _fmt_res3(prenp['P'] if prenp else None, nr=prenp_nr),
                _fmt_res4(prenp['base_K_gamma'] if prenp else None, nr=prenp_nr),
                _fmt_res4(prenp['base_K_q'] if prenp else None, nr=prenp_nr),
                _fmt_res4(prenp['base_K_c'] if prenp else None, nr=prenp_nr),
                _fmt_theta(prenp['base_theta_deg'] if prenp else None, nr=prenp_nr)
            ))
            self.tree_passive.insert("", "end", values=("AASHTO", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"))
            self.tree_passive.insert("", "end", values=(
                "CUT", f"{kh:.3f}", f"{en_kv:.3f}",
                _fmt_res3(cutp['P'] if cutp else None),
                _fmt_res4(cutp['base_K_gamma'] if cutp else None),
                _fmt_res4(cutp['base_K_q'] if cutp else None),
                _fmt_res4(0.0 if cutp else None),
                _fmt_theta(cutp['base_theta_deg'] if cutp else None)
            ))

            # Practical notes for engineering use
            active_lines = ["Practical notes"]
            if warnings:
                active_lines += [f"• {w}" for w in warnings]
            else:
                active_lines += ["• No warning for the current active-side solution."]
            active_lines += ["", "=== EN 1998-5 ==="]
            if ena is not None:
                active_lines += [
                    f"• Governing equation at base: {ena['equation']}",
                    f"• Base coefficient Kγ = {ena['K']:.6f}",
                    f"• Base seismic angle θ = {ena['theta_deg']:.4f}°",
                    f"• Resultant force = {Ed_a:.6f}",
                    f"• Point of application above base = {yEd_a:.6f} m"
                ]
            active_lines += ["", "=== prEN 1998-5 ==="]
            if prena is not None:
                active_lines += [
                    f"• Base coefficients: K_AEγ = {prena['base_K_gamma']:.6f}, K_AEq = {prena['base_K_q']:.6f}, K_AEc = {prena['base_K_c']:.6f}",
                    f"• Base seismic angle θeq = {prena['base_theta_deg']:.4f}°",
                    f"• Resultant force = {prena['P']:.6f}",
                    f"• Point of application above base = {prena['ybar_base']:.6f} m"
                ]
            active_lines += ["", "=== AASHTO ==="]
            if P_AE is not None and aask is not None:
                active_lines += [
                    f"• kh input = {kh:.3f}, reduction factor = {aashto_factor:.3f}, kh used = {kh_a:.3f}",
                    f"• Base seismic angle θ = {aask['theta_deg']:.3f}°",
                    f"• Resultant force = {P_AE:.6f}",
                    f"• Point of application above base = {yP_AE:.6f} m"
                ]
            active_lines += ["", "=== CUT ==="]
            if cuta is not None:
                active_lines += [
                    "• Active CUT formulation is used with δ ignored.",
                    f"• Base values: K_XE = {cuta['base_K_gamma']:.6f}, φ_m = {cuta['base_phi_m_deg']:.6f}°, c_m = {cuta['base_c_m']:.6f}",
                    f"• Base seismic angle θeq = {cuta['base_theta_deg']:.6f}°",
                    f"• Resultant force = {cuta['P']:.6f}",
                    f"• Point of application above base = {cuta['ybar_base']:.6f} m"
                ]
            active_lines += ["", "• NR means no real solution."]

            passive_lines = ["Practical notes"]
            if warnings:
                passive_lines += [f"• {w}" for w in warnings]
            else:
                passive_lines += ["• No warning for the current passive-side solution."]
            passive_lines += ["", "=== EN 1998-5 ==="]
            if enp is not None:
                passive_lines += [
                    f"• Governing equation at base: {enp['equation']}",
                    f"• Base coefficient Kγ = {enp['K']:.6f}",
                    f"• Base seismic angle θ = {enp['theta_deg']:.4f}°",
                    f"• Resultant force = {Ed_p:.6f}",
                    f"• Point of application above base = {yEd_p:.6f} m"
                ]
            passive_lines += ["", "=== prEN 1998-5 ==="]
            if prenp is not None:
                passive_lines += [
                    f"• Base coefficients: K_PEγ = {prenp['base_K_gamma']:.6f}, K_PEq = {prenp['base_K_q']:.6f}, K_PEc = {prenp['base_K_c']:.6f}",
                    f"• Base seismic angle θeq = {prenp['base_theta_deg']:.4f}°",
                    f"• Resultant force = {prenp['P']:.6f}",
                    f"• Point of application above base = {prenp['ybar_base']:.6f} m"
                ]
            passive_lines += ["", "=== AASHTO ===", "• Seismic passive pressure by Mononobe–Okabe is not used here.", "• Use an alternative passive design method.", "", "=== CUT ==="]
            if cutp is not None:
                passive_lines += [
                    "• Passive CUT formulation is used with δ ignored.",
                    f"• Base values: K_XE = {cutp['base_K_gamma']:.6f}, φ_m = {cutp['base_phi_m_deg']:.6f}°, c_m = {cutp['base_c_m']:.6f}",
                    f"• Base seismic angle θeq = {cutp['base_theta_deg']:.6f}°",
                    f"• Resultant force = {cutp['P']:.6f}",
                    f"• Point of application above base = {cutp['ybar_base']:.6f} m"
                ]
            passive_lines += ["", "• NR means no real solution."]
            self._set_text(self.text_active, "\n".join(active_lines))
            self._set_text(self.text_passive, "\n".join(passive_lines))
            
            # z tables (independent inputs for each tab)
            def populate_z_tree(tree, z_value):
                zq = max(0.001, min(H, float(z_value)))

                svq_h, uq_h = sigma_v_u_layered(zq, layers, pren_zwt, gamma_w)
                _, _, uq_d, _ = retained_side_u_total(
                    zq, H, layers, pren_zwt, gamma_w, kh, inner_flow,
                    include_dynamic=(retained_water_mode == "hydrodynamic")
                )
                effq = max(0.0, svq_h - uq_h)

                # w = 0 since Hw = 0
                w_active = 0.0
                w_passive = 0.0

                def insert_row(method, sigma_eff, u_val, ud_val, w_val, kq_term, kc_term, sigma_total, kgamma, kq_val, kc_val, nr=False, na=False):
                    tree.insert("", "end", values=(
                        method,
                        _fmt_cell3(sigma_eff, nr=nr, na=na),
                        _fmt_cell3(u_val, nr=nr, na=na),
                        _fmt_cell3(ud_val, nr=nr, na=na),
                        _fmt_cell3(kq_term, nr=nr, na=na),
                        _fmt_cell3(kc_term, nr=nr, na=na),
                        _fmt_cell3(sigma_total, nr=nr, na=na),
                        _fmt_cell3(kgamma, nr=nr, na=na),
                        _fmt_cell3(kq_val, nr=nr, na=na),
                        _fmt_cell3(kc_val, nr=nr, na=na)
                    ))

                if cuta is not None:
                    cut_sigma_raw = interpolate_piecewise(cuta["z"], cuta["sigma_raw"], zq)
                    cut_u = interpolate_piecewise(cuta["z"], cuta["u"], zq)
                    cut_ud = interpolate_piecewise(cuta["z"], cuta["ud"], zq)
                    cut_qterm = interpolate_piecewise(cuta["z"], cuta["qterm"], zq)
                    cut_kg = interpolate_piecewise(cuta["z"], cuta["K_gamma"], zq)
                    cut_kq = interpolate_piecewise(cuta["z"], cuta["K_q"], zq)
                    cut_sigma_eff = cut_sigma_raw - cut_qterm - cut_u - cut_ud
                    if cut_sigma_raw < 0.0:
                        insert_row("CUT active", "Tension", cut_u, cut_ud, 0.0,
                                   cut_qterm, 0.0, "Tension", cut_kg, cut_kq, 0.0)
                    else:
                        insert_row("CUT active", cut_sigma_eff, cut_u, cut_ud, 0.0,
                                   cut_qterm, 0.0, cut_sigma_raw, cut_kg, cut_kq, 0.0)
                else:
                    insert_row("CUT active", None, uq_h, uq_d, 0.0, None, None, None, None, None, None)

                if aashto_prof is not None and aashto_prof.get("z"):
                    try:
                        coeff_aashto = en_active_coeffs_with_theta(
                            layer_at_z(layers, max(zq,1e-9))["phi"], beta, alpha, delta_d,
                            pren_theta_eq(kh_a, svq_h, uq_h)
                        )
                        if allow_qc_to_en_aashto:
                            Kq_use, Kc_use = derive_pren_qc_from_K(coeff_aashto["K_gamma"], layer_at_z(layers, max(zq,1e-9))["phi"], beta, "active")
                            coeff_aashto = {**coeff_aashto, "K_q": Kq_use, "K_c": Kc_use}
                        sigma_eff = coeff_aashto["K_gamma"] * (1.0 - aashto_kv) * effq
                        kq_term = coeff_aashto["K_q"] * aashto_q
                        kc_term = coeff_aashto["K_c"] * layer_at_z(layers, max(zq,1e-9))["c"] if aashto_use_c else 0.0
                        sigma_total = sigma_eff + uq_h + uq_d + kq_term - kc_term
                        insert_row("AASHTO active", sigma_eff, uq_h, uq_d, 0.0, kq_term, kc_term, sigma_total,
                                   coeff_aashto["K_gamma"], coeff_aashto["K_q"] if allow_qc_to_en_aashto else 0.0,
                                   coeff_aashto["K_c"] if allow_qc_to_en_aashto else 0.0, nr=aask_nr)
                    except Exception:
                        insert_row("AASHTO active", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=aask_nr)
                else:
                    insert_row("AASHTO active", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=aask_nr)

                if ena_prof["z"]:
                    try:
                        coeff_en_a = en_active_coeffs_with_theta(
                            layer_at_z(layers, max(zq,1e-9))["phi"], beta, alpha, delta_d,
                            pren_theta_eq(kh, svq_h, uq_h)
                        )
                        if allow_qc_to_en_aashto:
                            Kq_use, Kc_use = derive_pren_qc_from_K(coeff_en_a["K_gamma"], layer_at_z(layers, max(zq,1e-9))["phi"], beta, "active")
                            coeff_en_a = {**coeff_en_a, "K_q": Kq_use, "K_c": Kc_use}
                        sigma_eff = coeff_en_a["K_gamma"] * (1.0 - en_kv) * effq
                        kq_term = coeff_en_a["K_q"] * en_q
                        kc_term = coeff_en_a["K_c"] * layer_at_z(layers, max(zq,1e-9))["c"] if en_use_c else 0.0
                        sigma_total = sigma_eff + uq_h + uq_d + kq_term - kc_term
                        insert_row("EN active", sigma_eff, uq_h, uq_d, 0.0, kq_term, kc_term, sigma_total,
                                   coeff_en_a["K_gamma"], coeff_en_a["K_q"] if allow_qc_to_en_aashto else 0.0,
                                   coeff_en_a["K_c"] if allow_qc_to_en_aashto else 0.0, nr=ena_nr)
                    except Exception:
                        insert_row("EN active", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=ena_nr)
                else:
                    insert_row("EN active", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=ena_nr)

                coeff = None
                sigma_eff = kq_term = kc_term = sigma_total = None
                if prena is not None:
                    try:
                        coeff = pren_active_coeffs(
                            layer_at_z(layers, max(zq,1e-9))["phi"], beta, delta,
                            pren_theta_eq(pren_alphaH, svq_h, uq_h)
                        )
                        sigma_eff = coeff["K_gamma"] * (svq_h - uq_h)
                        kq_term = coeff["K_q"] * pren_q
                        kc_term = coeff["K_c"] * layer_at_z(layers, max(zq,1e-9))["c"] if pren_use_c else 0.0
                        sigma_total = sigma_eff + uq_h + uq_d + w_active + kq_term - kc_term
                    except Exception:
                        coeff = None
                insert_row(
                    "prEN active", sigma_eff, uq_h, uq_d, w_active, kq_term, kc_term, sigma_total,
                    coeff['K_gamma'] if coeff else None,
                    coeff['K_q'] if coeff else None,
                    coeff['K_c'] if coeff else None,
                    nr=prena_nr
                )

                if cutp is not None:
                    cut_sigma_raw = interpolate_piecewise(cutp["z"], cutp["sigma_raw"], zq)
                    cut_u = interpolate_piecewise(cutp["z"], cutp["u"], zq)
                    cut_ud = interpolate_piecewise(cutp["z"], cutp["ud"], zq)
                    cut_qterm = interpolate_piecewise(cutp["z"], cutp["qterm"], zq)
                    cut_kg = interpolate_piecewise(cutp["z"], cutp["K_gamma"], zq)
                    cut_kq = interpolate_piecewise(cutp["z"], cutp["K_q"], zq)
                    cut_sigma_eff = cut_sigma_raw - cut_qterm - cut_u - cut_ud
                    if cut_sigma_raw < 0.0:
                        insert_row("CUT passive", "Tension", cut_u, cut_ud, 0.0,
                                   cut_qterm, 0.0, "Tension", cut_kg, cut_kq, 0.0)
                    else:
                        insert_row("CUT passive", cut_sigma_eff, cut_u, cut_ud, 0.0,
                                   cut_qterm, 0.0, cut_sigma_raw, cut_kg, cut_kq, 0.0)
                else:
                    insert_row("CUT passive", None, uq_h, uq_d, 0.0, None, None, None, None, None, None)

                insert_row("AASHTO passive", None, None, None, None, None, None, None, None, None, None, na=True)
                if enp_prof["z"]:
                    try:
                        coeff_en_p = en_passive_coeffs_with_theta(
                            layer_at_z(layers, max(zq,1e-9))["phi"], beta, alpha,
                            pren_theta_eq(kh, svq_h, uq_h)
                        )
                        if allow_qc_to_en_aashto:
                            Kq_use, Kc_use = derive_pren_qc_from_K(coeff_en_p["K_gamma"], layer_at_z(layers, max(zq,1e-9))["phi"], beta, "passive")
                            coeff_en_p = {**coeff_en_p, "K_q": Kq_use, "K_c": Kc_use}
                        sigma_eff = coeff_en_p["K_gamma"] * (1.0 + en_kv) * effq
                        kq_term = coeff_en_p["K_q"] * en_q
                        kc_term = coeff_en_p["K_c"] * layer_at_z(layers, max(zq,1e-9))["c"] if en_use_c else 0.0
                        sigma_total = sigma_eff + uq_h + uq_d + kq_term + kc_term
                        insert_row("EN passive", sigma_eff, uq_h, uq_d, 0.0, kq_term, kc_term, sigma_total,
                                   coeff_en_p["K_gamma"], coeff_en_p["K_q"] if allow_qc_to_en_aashto else 0.0,
                                   coeff_en_p["K_c"] if allow_qc_to_en_aashto else 0.0, nr=enp_nr)
                    except Exception:
                        insert_row("EN passive", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=enp_nr)
                else:
                    insert_row("EN passive", None, uq_h, uq_d, 0.0, None, None, None, None, None, None, nr=enp_nr)

                coeffp = None
                sigma_eff = kq_term = kc_term = sigma_total = None
                if prenp is not None:
                    try:
                        coeffp = pren_passive_coeffs(
                            layer_at_z(layers, max(zq,1e-9))["phi"], beta, delta,
                            pren_theta_eq(pren_alphaH, svq_h, uq_h)
                        )
                        sigma_eff = coeffp["K_gamma"] * (svq_h - uq_h)
                        kq_term = coeffp["K_q"] * pren_q
                        kc_term = coeffp["K_c"] * layer_at_z(layers, max(zq,1e-9))["c"] if pren_use_c else 0.0
                        sigma_total = sigma_eff + uq_h + uq_d + w_passive + kq_term + kc_term
                    except Exception:
                        coeffp = None
                insert_row(
                    "prEN passive", sigma_eff, uq_h, uq_d, w_passive, kq_term, kc_term, sigma_total,
                    coeffp['K_gamma'] if coeffp else None,
                    coeffp['K_q'] if coeffp else None,
                    coeffp['K_c'] if coeffp else None,
                    nr=prenp_nr
                )

            populate_z_tree(self.z_tree, self.z_query.get())
            populate_z_tree(self.z_tree_copy, self.z_query_data.get())
            trace_text_active = build_cut_trace_for_z_mode(
                self.z_query_trace.get(), "active", layers, H, beta, kh, kv, gamma_w, zwt, q,
                inner_flow, retained_water_mode
            )
            trace_text_passive = build_cut_trace_for_z_mode(
                self.z_query_trace.get(), "passive", layers, H, beta, kh, kv, gamma_w, zwt, q,
                inner_flow, retained_water_mode
            )
            self._set_text(self.text_trace_active, trace_text_active)
            self._set_text(self.text_trace_passive, trace_text_passive)

            # merged resultant summary for Report tab
            self.tree_summary.insert("", "end", values=(
                "CUT",
                _fmt_res3(cuta['P'] if cuta else None),
                _fmt_res3(cuta['ybar_base'] if cuta else None),
                _fmt_res3(cutp['P'] if cutp else None),
                _fmt_res3(cutp['ybar_base'] if cutp else None)
            ))
            self.tree_summary.insert("", "end", values=(
                "AASHTO",
                _fmt_res3(P_AE_disp, nr=aask_nr),
                _fmt_res3(yP_AE, nr=aask_nr),
                "N/A",
                "N/A"
            ))
            self.tree_summary.insert("", "end", values=(
                "EN1998-5",
                _fmt_res3(Ed_a, nr=ena_nr),
                _fmt_res3(yEd_a, nr=ena_nr),
                _fmt_res3(Ed_p, nr=enp_nr),
                _fmt_res3(yEd_p, nr=enp_nr)
            ))
            self.tree_summary.insert("", "end", values=(
                "prEN1998-5",
                _fmt_res3(prena['P'] if prena else None, nr=prena_nr),
                _fmt_res3(prena['ybar_base'] if prena else None, nr=prena_nr),
                _fmt_res3(prenp['P'] if prenp else None, nr=prenp_nr),
                _fmt_res3(prenp['ybar_base'] if prenp else None, nr=prenp_nr)
            ))

            # geometry / plots
            self.draw_geometry(H, alpha, beta, zwt, pren_Hw, layers)
            self.axd1.clear(); self.axd2.clear()

            ena_plot = ena_prof
            prena_plot = prena if prena is not None else None
            aashto_plot = aashto_prof if aashto_prof is not None else None
            enp_plot = enp_prof
            prenp_plot = prenp if prenp is not None else None
            if self.show_en_active.get() and ena_plot["z"]:
                self.axd1.plot(
                    ena_plot["sigma"], ena_plot["z"], '--o', linewidth=2, markersize=3, markevery=25,
                    label="EN active", color=METHOD_COLORS["EN active"]
                )
            if self.show_pren_active.get() and prena_plot is not None:
                self.axd1.plot(
                    prena_plot["sigma"], prena_plot["z"], '-', linewidth=2.2,
                    label="prEN active", color=METHOD_COLORS["prEN active"]
                )
            if aashto_adm and self.show_aashto_active.get() and aashto_plot is not None:
                self.axd1.plot(
                    aashto_plot["sigma"], aashto_plot["z"], ':s', linewidth=2.2, markersize=3, markevery=25,
                    label="AASHTO active", color=METHOD_COLORS["AASHTO active"]
                )
            if cuta is not None:
                self.axd1.plot(
                    cuta["sigma"], cuta["z"], '-', linewidth=2.6,
                    label="CUT active", color=METHOD_COLORS["CUT active"]
                )
            if self.show_en_passive.get() and enp_plot["z"]:
                self.axd2.plot(
                    enp_plot["sigma"], enp_plot["z"], '--o', linewidth=2, markersize=3, markevery=25,
                    label="EN passive", color=METHOD_COLORS["EN passive"]
                )
            if self.show_pren_passive.get() and prenp_plot is not None:
                self.axd2.plot(
                    prenp_plot["sigma"], prenp_plot["z"], '-', linewidth=2.2,
                    label="prEN passive", color=METHOD_COLORS["prEN passive"]
                )
            if cutp is not None:
                self.axd2.plot(
                    cutp["sigma"], cutp["z"], '-', linewidth=2.6,
                    label="CUT passive", color=METHOD_COLORS["CUT passive"]
                )
            for ax, title, xlabel in [(self.axd1, "Active-side distributions", "Active earth pressure (kPa)"), (self.axd2, "Passive-side distributions", "Passive earth pressure (kPa)")]:
                ax.axvline(0.0, color="black", linewidth=3.2, alpha=0.95)
                ax.invert_yaxis(); ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel("Depth from top (m)"); ax.grid(True, alpha=0.3)
                if ax.lines: ax.legend(loc="best")
            self.canvas_dist.draw()

        except Exception as e:
            import traceback
            msg = f"Warnings\n• {e}\n\n{traceback.format_exc()}"
            self._set_text(self.text_active, msg)
            self._set_text(self.text_passive, msg)
            self._set_text(self.text_trace_active, msg)
            self._set_text(self.text_trace_passive, msg)

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()