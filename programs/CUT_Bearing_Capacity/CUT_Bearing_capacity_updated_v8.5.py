#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import tkinter as tk
from tkinter import ttk, messagebox
import os, sys
import webbrowser

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller bundle """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)



PROGRAM_NAME = "CUT_Bearing_capacity"
VERSION = "v8.5 (Program), v3 (Manual)"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"
ABOUT_TEXT = f"""{PROGRAM_NAME}
Version: {VERSION}
Author: {AUTHOR}

Educational tool — no warranty. Use at your own risk. Free of charge."""
APP_TITLE = PROGRAM_NAME
PAD = 8

def safe_float(s: str, default: float = 0.0) -> float:
    try:
        txt = str(s).strip()
        if txt == "":
            return float(default)
        return float(txt)
    except Exception:
        return float(default)
        return float(default)

# ---------- Two-layer equivalent soil helpers ----------
def tan_deg(angle_deg: float) -> float:
    return math.tan(math.radians(angle_deg))

def KA_rankine(phi_deg: float) -> float:
    return tan_deg(45.0 - phi_deg / 2.0) ** 2

def KP_rankine(phi_deg: float) -> float:
    return tan_deg(45.0 + phi_deg / 2.0) ** 2

def integral_Iz_closed(B: float, z1: float, z2: float) -> float:
    if z2 <= z1:
        return 0.0
    eps = 1e-12 * B
    z1 = max(z1, eps)
    z2 = max(z2, eps)

    def F(z: float) -> float:
        return (B * math.log(B * B + z * z) + z * math.atan(B / z)) / math.pi

    return F(z2) - F(z1)

def compute_two_layer_equivalent(B, DfA, DfP, c1, phi1_deg, gamma1, H1, c2, phi2_deg, gamma2):
    """
    Convert a two-layer soil into an equivalent homogeneous soil:
      ceq, phi_eq_deg, gamma_eq
    using the logic of CUT_Bearing_capacity_2_strata_3_limit.py.
    """
    phi1_rad = math.radians(phi1_deg)

    H_hom1 = (
        0.5 * B
        * math.exp((math.pi / 4.0 - phi1_rad / 2.0) * math.tan(phi1_rad))
        / math.cos(math.radians(45.0 + phi1_deg / 2.0))
    )

    # Case 1: mechanism fully inside layer 1
    if H1 >= H_hom1:
        H = H_hom1
        phi_eq_deg = phi1_deg
        gamma_eq = gamma1

        KA1 = KA_rankine(phi1_deg)
        KP1 = KP_rankine(phi1_deg)

        I1 = integral_Iz_closed(B, 0.0, H)
        I0 = KA1 * I1

        Nc1 = 2.0 * (math.sqrt(KA1) + math.sqrt(KP1)) * H / I0
        Ngamma1 = (KP1 - KA1) * (H ** 2) / (B * I0)
        Nq1 = (
            (DfA / DfP) * KA1 * I1 / I0
            + (KP1 / KA1 - DfA / DfP) * KA1 * H / I0
        )

        qu = (
            c1 * Nc1
            + 0.5 * B * gamma1 * Ngamma1
            + gamma1 * DfP * Nq1
        )

        return {
            "ceq": c1,
            "phi_eq_deg": phi_eq_deg,
            "gamma_eq": gamma_eq,
            "regime": "homogeneous_layer_1",
            "qu_two_layer": qu,
            "H_hom1": H_hom1,
            "H1_input": H1,
            "I1": I1,
            "I2": 0.0,
        }

    # Case 2: actual two-layer mechanism
    t1 = tan_deg(45.0 + phi2_deg / 2.0)
    t2 = tan_deg(45.0 + phi1_deg / 2.0)
    HI = (B / 2.0) * t1 + H1 * (1.0 - t1 / t2)

    phi_eq_rad = 2.0 * math.atan(2.0 * HI / B) - math.pi / 2.0
    phi_eq_deg = math.degrees(phi_eq_rad)

    H = (
        0.5 * B
        * math.exp(
            (math.pi / 4.0 - math.radians(phi_eq_deg) / 2.0)
            * math.tan(math.radians(phi_eq_deg))
        )
        / math.cos(math.radians(45.0 + phi_eq_deg / 2.0))
    )

    if H <= H1:
        I1 = integral_Iz_closed(B, 0.0, H_hom1)
        return {
            "ceq": c1,
            "phi_eq_deg": phi1_deg,
            "gamma_eq": gamma1,
            "regime": "homogeneous_layer_1",
            "qu_two_layer": float("nan"),
            "H_hom1": H_hom1,
            "H1_input": H1,
            "I1": I1,
            "I2": 0.0,
        }

    KA1 = KA_rankine(phi1_deg)
    KP1 = KP_rankine(phi1_deg)
    KA2 = KA_rankine(phi2_deg)
    KP2 = KP_rankine(phi2_deg)

    I1 = integral_Iz_closed(B, 0.0, H1)
    I2 = integral_Iz_closed(B, H1, H)
    I0 = KA1 * I1 + KA2 * I2

    Nc1 = 2.0 * (math.sqrt(KA1) + math.sqrt(KP1)) * H1 / I0
    Ngamma1 = (KP1 - KA1) * (H1 ** 2) / (B * I0)
    Nq1 = (
        (DfA / DfP) * KA1 * I1 / I0
        + (KP1 / KA1 - DfA / DfP) * KA1 * H1 / I0
    )

    Nc2 = 2.0 * (math.sqrt(KA2) + math.sqrt(KP2)) * (H - H1) / I0
    Ngamma2 = (gamma2 / gamma1) * (KP2 - KA2) * (H ** 2 - H1 ** 2) / (B * I0)
    Nq2 = (
        (DfA / DfP) * KA2 * I2 / I0
        + (KP2 / KA2 - DfA / DfP) * KA2 * (H - H1) / I0
        + (1.0 - gamma2 / gamma1) * (KP2 - KA2) * (H1 * (H - H1)) / (DfP * I0)
    )

    qu = (
        c1 * Nc1
        + c2 * Nc2
        + 0.5 * B * gamma1 * (Ngamma1 + Ngamma2)
        + gamma1 * DfP * (Nq1 + Nq2)
    )

    gamma_eq = 0.5 * (gamma1 + gamma2)

    KAeq = KA_rankine(phi_eq_deg)
    KPeq = KP_rankine(phi_eq_deg)
    I0eq = KAeq * (I1 + I2)

    Nc1_eq = 2.0 * (math.sqrt(KAeq) + math.sqrt(KPeq)) * H1 / I0eq
    Nc2_eq = 2.0 * (math.sqrt(KAeq) + math.sqrt(KPeq)) * (H - H1) / I0eq
    Ngamma1_eq = (KPeq - KAeq) * (H1 ** 2) / (B * I0eq)
    Ngamma2_eq = (KPeq - KAeq) * (H ** 2 - H1 ** 2) / (B * I0eq)

    Nq1_eq = (
        (DfA / DfP) * KAeq * I1 / I0eq
        + (KPeq / KAeq - DfA / DfP) * KAeq * H1 / I0eq
    )

    Nq2_eq = (
        (DfA / DfP) * KAeq * I2 / I0eq
        + (KPeq / KAeq - DfA / DfP) * KAeq * (H - H1) / I0eq
    )

    Nc_tot_eq = Nc1_eq + Nc2_eq
    Ngamma_tot_eq = Ngamma1_eq + Ngamma2_eq
    Nq_tot_eq = Nq1_eq + Nq2_eq

    qu_noc_eq = 0.5 * B * gamma_eq * Ngamma_tot_eq + gamma_eq * DfP * Nq_tot_eq
    ceq = (qu - qu_noc_eq) / Nc_tot_eq if abs(Nc_tot_eq) > 1e-12 else float("nan")

    return {
        "ceq": ceq,
        "phi_eq_deg": phi_eq_deg,
        "gamma_eq": gamma_eq,
        "regime": "two_layer",
        "qu_two_layer": qu,
        "H_hom1": H_hom1,
        "H1_input": H1,
        "I1": I1,
        "I2": I2,
    }

# ---------- scrollable frame ----------
class ScrollFrame(ttk.Frame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", self._on_frame_configure)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._bind_mousewheel(self.canvas)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Button-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self._drag_data = {"y": 0, "scroll_y": 0}

    def _on_frame_configure(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfigure(self.win, width=e.width)

    def _bind_mousewheel(self, w):
        w.bind_all("<MouseWheel>", self._on_wheel)
        w.bind_all("<Button-4>", self._on_wheel)
        w.bind_all("<Button-5>", self._on_wheel)

    def _on_wheel(self, e):
        if getattr(e, "num", None) == 4:
            self.canvas.yview_scroll(-2, "units")
        elif getattr(e, "num", None) == 5:
            self.canvas.yview_scroll(2, "units")
        else:
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _on_button_press(self, event):
        self._drag_data["y"] = event.y
        self._drag_data["scroll_y"] = self.canvas.yview()[0]

    def _on_mouse_move(self, event):
        dy = event.y - self._drag_data["y"]
        height = self.canvas.winfo_height()
        if height > 0:
            move_fraction = -dy / height
            new_scroll = self._drag_data["scroll_y"] + move_fraction
            self.canvas.yview_moveto(new_scroll)

# ---------- EN helpers ----------
def N_factors_original_drained(phi_deg: float):
    phi = math.radians(phi_deg)
    if phi_deg <= 1e-12:
        return 5.14, 1.0, 0.0
    Nq = math.exp(math.pi * math.tan(phi)) * (math.tan(math.pi / 4 + phi / 2) ** 2)
    Nc = (Nq - 1.0) / (math.tan(phi) + 1e-12)
    Ng = 2.0 * (Nq + 1.0) * math.tan(phi)
    return Nc, Nq, Ng

def N_factors_original_undrained():
    return math.pi + 2.0, 1.0, 0.0

# ---------- Cyprus NA geometry/influence ----------
def IB_over_B(phi_deg: float, footing_type: str = "Rigid"):
    s = math.sin(math.radians(phi_deg))
    if footing_type.lower() == "flexible":
        return 0.5 * s**2 + 0.26 * s + 0.354
    else:
        return -0.39 * s**3 + 0.77 * s**2 - 0.18 * s + 0.6

def H_distance(B: float, phi_deg: float):
    phi = math.radians(phi_deg)
    num = math.exp((math.pi / 4.0 - phi / 2.0) * math.tan(phi))
    den = math.cos(math.pi / 4.0 + phi / 2.0) or 1e-12
    return (B / 2.0) * num / den

def Hmax_distance(B: float, phi_deg: float):
    phi = math.radians(phi_deg)
    den = 2.0 * math.cos(math.pi / 4.0 + phi / 2.0) or 1e-12
    return (B * math.cos(phi) * math.exp((math.pi / 4.0 + phi / 2.0) * math.tan(phi))) / den

def effective_surcharge_and_gamma(Df, B, Dw, gam_dry, gam_sat, gam_w):
    if Df < 0:
        raise ValueError("Df must be ≥ 0")
    g_sub = gam_sat - gam_w
    if Df == 0:
        return 0.0, gam_dry
    if Dw <= 0.0:
        return g_sub * Df, g_sub
    if 0.0 < Dw < Df:
        return gam_dry * Dw + g_sub * (Df - Dw), g_sub
    qeff = gam_dry * Df
    if Dw >= Df + 1.5 * B:
        geff = gam_dry
    else:
        t = max(0.0, min(1.0, (Dw - Df) / (1.5 * B)))
        geff = g_sub * (1 - t) + gam_dry * t
    return qeff, geff

# ---------- Cyprus NA: dilation/load/seismic/water ----------
def cyprus_kappa(phi_deg, psi_deg):
    if abs(phi_deg) < 1e-12:
        return 1.0
    if psi_deg <= 0:
        return 1.0
    if psi_deg >= phi_deg:
        return 1.12
    return 1.0 + 0.12 * (psi_deg / max(phi_deg, 1e-12))

def cyprus_f1(B, L, theta_deg):
    R  = B / max(L, 1e-12)
    th = math.radians(theta_deg)
    f0  = R / ((1.0 + R) ** 2)
    f90 = max(0.0, 1.0 - 0.75 * R)
    return (math.cos(th)**2) * f0 + (math.sin(th)**2) * f90

def cyprus_alpha_psi(delta_deg, psi_deg, phi_deg):
    if 0 <= delta_deg <= 45:
        return 1.0
    if -45 <= delta_deg < 0:
        if abs(psi_deg - phi_deg) < 1e-6:
            return 1.46
        if abs(psi_deg) < 1e-6:
            return 1.36
        t = min(max(psi_deg / max(phi_deg, 1e-12), 0.0), 1.0)
        return 1.36 + 0.10 * t
    return 1.0

def cyprus_shape_factors(phi_deg, Beff, Leff):
    r = Beff / max(Leff, 1e-12)
    t = math.tan(math.radians(phi_deg))
    sc_rect = 1 + (3.16*t*t + 0.27*t + 0.16)*r - (1.28*t*t + 0.22*t + 0.08)*r*r
    sg_rect = 1 + (1.2*t*t  - 0.28*t - 0.22)*r - (0.2*t*t  + 0.16*t - 0.06)*r*r
    sq_rect = 1 + 1.9*(t*t)*math.sqrt(max(r, 0.0))
    if abs(Beff - Leff) < 1e-9:
        sc, sg, sq = sc_rect, sg_rect, sq_rect
    else:
        sc, sg, sq = sc_rect, sg_rect, sq_rect
    return sc, sq, sg

def cyprus_depth_factors(phi_deg, Beff, Df, psi_deg):
    kappa = cyprus_kappa(phi_deg, psi_deg)
    v = min(1.4, kappa * (1.0 + 0.2 * (Df / max(Beff, 1e-12))))
    return v, v, v, kappa  # dc, dq, dγ, κ

def cyprus_inclination_factors(phi_deg, delta_deg, Beff, Leff, theta_deg, psi_deg):
    f1 = cyprus_f1(Beff, Leff, theta_deg)
    ic = (1.0 - f1 * math.tan(math.radians(((45.0 + phi_deg / 2.0) / 100.0) * delta_deg))) ** 3
    iq = (1.0 - f1 * math.tan(math.radians((2.0 / 3.0) * delta_deg))) ** 3
    apsi = cyprus_alpha_psi(delta_deg, psi_deg, phi_deg)
    ig = apsi * (1.0 - f1 * math.tan(math.radians(abs(delta_deg)))) ** 3
    return ic, iq, ig

def cyprus_seismic_factors(kh, kh_lim):
    if kh_lim <= 0 or kh <= 0:
        return 1.0, 1.0, 1.0
    x = max(0.0, 1.0 - kh/kh_lim)
    return x**0.2, x**0.2, x**0.4


def cyprus_w_factors(dw, Df, Hstar, geff, gamma_dry):
    """Cyprus NA water factors based on adjusted wall height H* (earth-pressure logic)."""
    eps = 1e-12
    ratio = geff / max(gamma_dry, eps)  # scales Cyprus total-γ terms to effective γ
    # Water at or above base level
    if dw <= Df + 1e-12:
        wc = 1.0
        wy = ratio
        wq = ratio + (1.0 - ratio) * (dw / max(Df, 1e-12)) if Df > eps else ratio
        return wc, wq, wy

    # Water below base
    wc, wq = 1.0, 1.0
    sub = dw - Df  # depth below base
    if Hstar <= eps:
        wy = 1.0
    elif sub <= Hstar + 1e-12:
        t = sub / Hstar
        wy = ratio + (2.0 - t) * (1.0 - ratio) * t
    else:
        wy = 1.0
    return wc, wq, wy

# ---------- Coulomb earth-pressure (vertical wall, δw=0) ----------
def coulomb_Ka(phi_deg, beta_deg, deltaw_deg=0.0):
    phi  = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    if abs(phi) < 1e-12:
        return 1.0
    cb = math.cos(beta)
    if cb <= 0.0:
        return float("inf")
    root = math.sqrt(max((math.sin(phi) * math.sin(phi - beta)) / cb, 0.0))
    return (math.cos(phi) ** 2) / (1.0 + root) ** 2

def coulomb_Kp(phi_deg, beta_deg, deltaw_deg=0.0):
    phi  = math.radians(phi_deg)
    beta = math.radians(beta_deg)
    if abs(phi) < 1e-12:
        return 1.0
    cb = math.cos(beta)
    if cb <= 0.0:
        return float("inf")
    root = math.sqrt(max((math.sin(phi) * math.sin(phi + beta)) / cb, 0.0))
    val  = 1.0 - root
    return (math.cos(phi) ** 2) / max(val * val, 1e-12)


# ---------- Soil compressibility helpers from Eq. (20) ----------
def sc_rankine_active(phi_rad: float) -> float:
    s = math.sin(phi_rad)
    return (1.0 - s) / (1.0 + s)

def sc_rankine_passive(phi_rad: float) -> float:
    s = math.sin(phi_rad)
    return (1.0 + s) / (1.0 - s)

def sc_influence_integral(phi_rad: float, footing_type: str, B: float) -> float:
    s = math.sin(phi_rad)
    ft = footing_type.strip().lower()

    if ft == "rigid":
        I = -0.39 * s**3 + 0.77 * s**2 - 0.18 * s + 0.6
    elif ft == "flexible":
        I = 0.6 * s**2 + 0.27 * s + 0.347
    else:
        raise ValueError("Footing type must be 'Rigid' or 'Flexible'.")

    return I * B   # ✅ dimensional correction

def compute_soil_compressibility_factors(c, phi_deg, gamma, Df, B, L, f_cs, footing_type, Df_A, Df_P, mode="edge", lambda3=0.5):
    if B <= 0:
        raise ValueError("B must be > 0.")
    if Df_A < 0:
        raise ValueError("DfA must be >= 0.")
    if Df_P <= 0:
        raise ValueError("DfP must be > 0.")
    if c < 0:
        raise ValueError("c must be >= 0.")
    if not (0.0 <= phi_deg < 89.9):
        raise ValueError("phi must be between 0 and 89.9 degrees.")
    if not (0.0 <= f_cs <= 1.0):
        raise ValueError("f_cs must be between 0 and 1.")

    phi = math.radians(phi_deg)
    c_cr = f_cs * c
    phi_cr = math.atan(f_cs * math.tan(phi))

    r_o = B / (2.0 * math.cos(math.pi / 4.0 + phi / 2.0))

    if abs(math.sin(phi_cr)) < 1e-12:
        s_lg_tot = 0.0
    else:
        s_lg_tot = (r_o / math.sin(phi_cr)) * (
            math.exp((math.pi / 2.0) * math.tan(phi_cr)) - 1.0
        )

    H_cr = (
        B
        / (2.0 * math.cos(math.pi / 4.0 + phi_cr / 2.0))
        * math.exp((math.pi / 4.0 - phi_cr / 2.0) * math.tan(phi_cr))
    )
    H_o = (
        B
        / (2.0 * math.cos(math.pi / 4.0 + phi / 2.0))
        * math.exp((math.pi / 4.0 - phi / 2.0) * math.tan(phi))
    )

    f_ep = 0.16 + 1.5 * f_cs - 0.66 * f_cs**2

    if mode == "local":
        if not (0.5 <= lambda3 <= 1.0):
            raise ValueError("For local shear, lambda3 must be between 0.5 and 1.0.")

        sin_phi = math.sin(phi)
        sin_45_minus_phi2 = math.sin(math.radians(45.0) - phi / 2.0)

        if abs(sin_phi) < 1e-12:
            Slg_tot3 = 0.0
        else:
            Slg_tot3 = (r_o / sin_phi) * (
                math.exp((math.pi / 2.0) * math.tan(phi)) - 1.0
            )

        if abs(sin_45_minus_phi2) < 1e-12:
            S3 = 0.0
        else:
            S3 = r_o * math.exp((math.pi / 2.0) * math.tan(phi)) + Df_P / sin_45_minus_phi2

        phi_waA_loc = phi
        c_waA_loc = c

        denom_loc = Slg_tot3 + S3
        if abs(denom_loc) < 1e-12:
            phi_waP_loc = phi
            c_waP_loc = c
        else:
            phi_waP_loc = (
                phi * Slg_tot3 + 0.5 * (phi + phi_cr) * S3 * lambda3
            ) / denom_loc
            c_waP_loc = (
                c * Slg_tot3 + 0.5 * c * S3 * lambda3
            ) / denom_loc

        K_IA_wa = (1.0 - math.sin(f_ep * phi_waA_loc)) / (1.0 + math.sin(f_ep * phi_waA_loc))
        K_IP_wa = (1.0 + math.sin(f_ep * phi_waP_loc)) / (1.0 - math.sin(f_ep * phi_waP_loc))
        c_waA_used = c_waA_loc
    else:
        s_lg_A = (r_o / math.sin(phi_cr)) * (math.exp((math.pi/4 - phi_cr/2) * math.tan(phi_cr)) - 1.0)
        phi_wa_A = (r_o * phi + s_lg_A * (phi + phi_cr) / 2.0) / (r_o + s_lg_A)
        c_wa_A = (r_o * c + s_lg_A * (c + 0.0) / 2.0) / (r_o + s_lg_A)

        K_IA_wa = (1.0 - math.sin(f_ep * phi_wa_A)) / (1.0 + math.sin(f_ep * phi_wa_A))
        K_IP_wa = (1.0 + math.sin(f_ep * phi_cr)) / (1.0 - math.sin(f_ep * phi_cr))
        c_waA_used = c_wa_A

    K_A = sc_rankine_active(phi)
    K_P = sc_rankine_passive(phi)

    I_I_phi = sc_influence_integral(phi, footing_type, B)

    if c == 0:
        c_c = float("nan")
    else:
        c_c = (
            (c_waA_used / c)
            * (K_A / (math.sqrt(K_IA_wa) * (math.sqrt(K_A) + math.sqrt(K_P))))
            * (H_cr / H_o)
        )

    c_gamma = ((1.0 - K_IP_wa / K_IA_wa) / (1.0 - K_P / K_A)) * (H_cr / H_o) ** 2

    cq_num = (Df_A / Df_P) * (1.0 - I_I_phi / H_cr) - (K_IP_wa / K_IA_wa)
    cq_den = (Df_A / Df_P) * (1.0 - I_I_phi / H_cr) - (K_P / K_A)
    c_q = (H_cr / H_o) * (cq_num / cq_den)

    return {
        "c_c": c_c,
        "c_q": c_q,
        "c_gamma": c_gamma,
        "c_cr": c_cr,
        "phi_cr_deg": math.degrees(phi_cr),
    }


# ---------- EN factor sets ----------
def original_drained_factors(phi_deg, alpha_deg, beta_deg, Beff, Leff, Df, T, N, theta_deg):
    Nc, Nq, Ng = N_factors_original_drained(phi_deg)
    phi = math.radians(phi_deg)
    a = math.radians(alpha_deg)

    bq = (1.0 - a * math.tan(phi))**2
    bg = bq
    bc = bq - (1.0 - bq) / (Nc * math.tan(phi) + 1e-12)

    r = Df / max(Beff, 1e-12)
    if r <= 1.0:
        dq = 1.0 + 2.0 * math.tan(phi) * (1.0 - math.sin(phi))**2 * r
    else:
        dq = 1.0 + 2.0 * math.tan(phi) * (1.0 - math.sin(phi))**2 * math.atan(r)
    dc = dq - (1.0 - dq) / (Nc * math.tan(phi) + 1e-12)
    dg = 1.0

    gq = (1.0 - math.tan(math.radians(beta_deg)))**2
    gg = gq
    gc = gq - (1.0 - gq) / (Nc * math.tan(phi) + 1e-12)

    mB = (2.0 + (Beff/max(Leff,1e-12))) / (1.0 + (Beff/max(Leff,1e-12)))
    mL = (2.0 + (Leff/max(Beff,1e-12))) / (1.0 + (Leff/max(Beff,1e-12)))
    th = math.radians(theta_deg)
    m = (mL * (math.cos(th)**2)) + (mB * (math.sin(th)**2))
    ratio = max(0.0, min(1.0, T / max(N, 1e-12)))
    iq = (1.0 - ratio)**m
    ig = (1.0 - ratio)**(m+1.0)
    ic = iq - (1.0 - iq) / (Nc * math.tan(phi) + 1e-12)

    sq = 1.0 + (Beff/max(Leff,1e-12)) * math.sin(phi)
    sg = 1.0 - 0.3 * (Beff/max(Leff,1e-12))
    if abs(Nq - 1.0) < 1e-8:
        sc = 1.0
    else:
        sc = (sq * Nq - 1.0) / (Nq - 1.0)

    return dict(Nc=Nc, Nq=Nq, Ng=Ng, bc=bc, bq=bq, bg=bg, dc=dc, dq=dq, dg=dg,
                gc=gc, gq=gq, gg=gg, ic=ic, iq=iq, ig=ig, sc=sc, sq=sq, sg=sg)

def original_undrained_factors(alpha_deg, beta_deg, Beff, Leff, Df, T, Aeff, c):
    Nc, Nq, Ng = N_factors_original_undrained()
    bcu = 1.0 - 2.0 * math.radians(alpha_deg) / (math.pi + 2.0)
    dcu = 1.0 + 0.33 * math.atan(Df / max(Beff,1e-12))
    gcu = max(1.0 - 2.0 * math.radians(beta_deg) / (math.pi + 2.0), 0.0)
    if c > 0 and Aeff > 0:
        val = max(0.0, min(1.0, 1.0 - T / (Aeff * c)))
        icu = 0.5 * (1.0 + math.sqrt(val))
    else:
        icu = 1.0
    scu = 1.0 + 0.2 * (Beff / max(Leff, 1e-12))
    return dict(Nc=Nc, Nq=Nq, Ng=Ng, bcu=bcu, dcu=dcu, gcu=gcu, icu=icu, scu=scu)

# ---------- GUI ----------
class App(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=PAD)
        master.title(f"{APP_TITLE} - v8.5")
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        root = self
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        # PanedWindow for draggable vertical separator
        pw = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        pw.grid(row=0, column=0, sticky="nsew", padx=PAD, pady=PAD)

        # Left (Inputs)
        inp_frame = ttk.LabelFrame(pw, text="Inputs")
        inp_sf = ScrollFrame(inp_frame)
        inp_sf.pack(fill="both", expand=True)

        # Fixed footer for left-side buttons (outside the scroll area)
        inp_footer = ttk.Frame(inp_frame)
        inp_footer.pack(side="bottom", fill="x")
        # Right (Outputs)
        out_frame = ttk.LabelFrame(pw, text="Outputs")
        out_sf = ScrollFrame(out_frame)
        out_sf.pack(fill="both", expand=True)

        # Add panes with initial sizes
        pw.add(inp_frame, weight=2)
        pw.add(out_frame, weight=3)

        # ---- Inputs (single column) ----
        inp = inp_sf.inner
        inp.columnconfigure(0, weight=1)
        inp.columnconfigure(1, weight=1)
        r = 0

        def add_row(label_text, var, width=16):
            nonlocal r
            lab = ttk.Label(inp, text=label_text)
            lab.grid(row=r, column=0, sticky="w", padx=(4, 2), pady=2)
            ent = ttk.Entry(inp, textvariable=var, width=width)
            ent.grid(row=r, column=1, sticky="w", pady=2)
            r += 1
            return lab, ent

        # ====== Geometry & GWT ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Geometry & GWT  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        self.Beff = tk.StringVar(value="2.0"); add_row("B, B' or D (m)", self.Beff); 
        self.Leff = tk.StringVar(value="20.0"); add_row("L or L′ (m)", self.Leff); 
        self.Df   = tk.StringVar(value="1.0"); add_row("Df (Df=DfP; on failure side) (m)", self.Df); 
        self.DfP  = tk.StringVar(value="1.0"); add_row("DfA (DfA>Df) (m)", self.DfP); 
        self.Dw   = tk.StringVar(value="10.0"); add_row("Dw (from ground surface) (m)", self.Dw); 
        self.alpha = tk.StringVar(value="0"); add_row("α base (deg); +=unfavorable", self.alpha); 

        ttk.Label(inp, text="Footing type (CUT method)").grid(row=r, column=0, sticky="w", padx=(4,2), pady=2)
        self.footing_type = tk.StringVar(value="Rigid")
        ttk.Combobox(
            inp,
            textvariable=self.footing_type,
            values=("Rigid", "Flexible"),
            width=22,
            state="readonly"
        ).grid(row=r, column=1, sticky="w", pady=2)
        r += 1

        # Circular footing checkbox
        self.is_circular = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            inp,
            text="Check the box if the footing is circular; B=D; L is ignored",
            variable=self.is_circular
        ).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        # ====== Soil data ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Soil data  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        ttk.Label(inp, text="Soil profile").grid(row=r, column=0, sticky="w", padx=(4,2), pady=2)
        self.soil_layers = tk.StringVar(value="1 layer")
        ttk.Combobox(
            inp,
            textvariable=self.soil_layers,
            values=("1 layer", "2 layers"),
            width=22,
            state="readonly"
        ).grid(row=r, column=1, sticky="w", pady=2)
        r += 1

        self.coh = tk.StringVar(value="20")
        self.phi = tk.StringVar(value="30")
        self.psi1 = tk.StringVar(value="0")
        self.gamma_dry = tk.StringVar(value="18.0")
        self.gamma_sat = tk.StringVar(value="20.0")

        self.c1 = tk.StringVar(value="20")
        self.phi1 = tk.StringVar(value="30")
        self.psi2 = tk.StringVar(value="0")
        self.gamma1_layer = tk.StringVar(value="18")
        self.H1_layer = tk.StringVar(value="2.0")
        self.c2 = tk.StringVar(value="10")
        self.phi2 = tk.StringVar(value="35")
        self.gamma2_layer = tk.StringVar(value="19")
        self.gamma_sat1_layer = tk.StringVar(value="20")
        self.gamma_sat2_layer = tk.StringVar(value="21")
        self.gamma_w = tk.StringVar(value="9.81")

        table = ttk.Frame(inp)
        table.grid(row=r, column=0, columnspan=2, sticky="w", padx=(4,2), pady=(2,2))
        table_cols = [0, 12, 12, 12, 12, 12, 14]
        for j, (hdr, w) in enumerate(zip(("s/n", "c", "φ", "ψ", "γ", "γsat", "H"), table_cols)):
            ttk.Label(table, text=hdr, font=("TkDefaultFont", 9, "bold"), width=w).grid(row=0, column=j, sticky="w", padx=2, pady=(0,2))

        self.layer1_label = ttk.Label(table, text="Layer 1", width=12)
        self.layer1_label.grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.ent_c1_table = ttk.Entry(table, textvariable=self.coh, width=12)
        self.ent_c1_table.grid(row=1, column=1, sticky="w", padx=2, pady=2)
        self.ent_phi1_table = ttk.Entry(table, textvariable=self.phi, width=12)
        self.ent_phi1_table.grid(row=1, column=2, sticky="w", padx=2, pady=2)
        self.ent_psi1_table = ttk.Entry(table, textvariable=self.psi1, width=12)
        self.ent_psi1_table.grid(row=1, column=3, sticky="w", padx=2, pady=2)
        self.ent_gamma1_table = ttk.Entry(table, textvariable=self.gamma_dry, width=12)
        self.ent_gamma1_table.grid(row=1, column=4, sticky="w", padx=2, pady=2)
        self.ent_gammasat1_table = ttk.Entry(table, textvariable=self.gamma_sat, width=12)
        self.ent_gammasat1_table.grid(row=1, column=5, sticky="w", padx=2, pady=2)
        self.layer1_H_label = ttk.Label(table, text="Infinite", width=14)
        self.layer1_H_label.grid(row=1, column=6, sticky="w", padx=2, pady=2)
        self.layer1_H_ent = ttk.Entry(table, textvariable=self.H1_layer, width=12)
        self.layer1_H_ent.grid(row=1, column=6, sticky="w", padx=2, pady=2)

        self.layer2_label = ttk.Label(table, text="Layer 2", width=12)
        self.layer2_label.grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.ent_c2_table = ttk.Entry(table, textvariable=self.c2, width=12)
        self.ent_c2_table.grid(row=2, column=1, sticky="w", padx=2, pady=2)
        self.ent_phi2_table = ttk.Entry(table, textvariable=self.phi2, width=12)
        self.ent_phi2_table.grid(row=2, column=2, sticky="w", padx=2, pady=2)
        self.ent_psi2_table = ttk.Entry(table, textvariable=self.psi2, width=12)
        self.ent_psi2_table.grid(row=2, column=3, sticky="w", padx=2, pady=2)
        self.ent_gamma2_table = ttk.Entry(table, textvariable=self.gamma2_layer, width=12)
        self.ent_gamma2_table.grid(row=2, column=4, sticky="w", padx=2, pady=2)
        self.ent_gammasat2_table = ttk.Entry(table, textvariable=self.gamma_sat2_layer, width=12)
        self.ent_gammasat2_table.grid(row=2, column=5, sticky="w", padx=2, pady=2)
        self.layer2_H_label = ttk.Label(table, text="Infinite", width=14)
        self.layer2_H_label.grid(row=2, column=6, sticky="w", padx=2, pady=2)

        r += 1
        self.lab_gamma_w, self.ent_gamma_w = add_row("γw (kN/m³)", self.gamma_w)

        self.allow_en_special = tk.BooleanVar(value=False)
        self.allow_en_special_chk = ttk.Checkbutton(
            inp,
            text="Allow EN for 2-layer/seismic using c_m and φ_m",
            variable=self.allow_en_special
        )
        self.allow_en_special_chk.grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        def update_soil_profile_visibility(*args):
            is_two = (self.soil_layers.get() == "2 layers")
            row2_widgets = [
                self.layer2_label,
                self.ent_c2_table,
                self.ent_phi2_table,
                self.ent_psi2_table,
                self.ent_gamma2_table,
                self.ent_gammasat2_table,
                self.layer2_H_label,
            ]
            if is_two:
                self.ent_c1_table.configure(textvariable=self.c1)
                self.ent_phi1_table.configure(textvariable=self.phi1)
                self.ent_gamma1_table.configure(textvariable=self.gamma1_layer)
                self.ent_gammasat1_table.configure(textvariable=self.gamma_sat1_layer)
                self.layer1_H_label.grid_remove()
                self.layer1_H_ent.grid()
                self.allow_en_special_chk.grid()
                for w in row2_widgets:
                    w.grid()
            else:
                self.ent_c1_table.configure(textvariable=self.coh)
                self.ent_phi1_table.configure(textvariable=self.phi)
                self.ent_gamma1_table.configure(textvariable=self.gamma_dry)
                self.ent_gammasat1_table.configure(textvariable=self.gamma_sat)
                self.layer1_H_ent.grid_remove()
                self.layer1_H_label.configure(text="Infinite")
                self.layer1_H_label.grid()
                for w in row2_widgets:
                    w.grid_remove()
                self.allow_en_special_chk.grid_remove()
                self.allow_en_special.set(False)
        self.soil_layers.trace_add("write", update_soil_profile_visibility)

        ttk.Label(inp, text="Failure mode").grid(row=r, column=0, sticky="w", padx=(4,2), pady=2)
        self.failure_mode = tk.StringVar(value="General shear")
        ttk.Combobox(
            inp,
            textvariable=self.failure_mode,
            values=("General shear", "Local shear", "Punching shear"),
            width=22,
            state="readonly"
        ).grid(row=r, column=1, sticky="w", pady=2)
        r += 1

        self.fcs = tk.StringVar(value="0.6666667")
        self.fcs_lab, self.fcs_ent = add_row("f_cs (for local/punching shear)", self.fcs)

        self.lambda3 = tk.StringVar(value="0.5")
        self.lambda3_lab, self.lambda3_ent = add_row("λ3 (0.5 ≤ λ3 ≤ 1.0)", self.lambda3)

        def update_failure_mode_visibility(*args):
            mode_now = self.failure_mode.get()
            if mode_now in ("Local shear", "Punching shear"):
                self.fcs_lab.grid()
                self.fcs_ent.grid()
            else:
                self.fcs_lab.grid_remove()
                self.fcs_ent.grid_remove()

            if mode_now == "Local shear":
                self.lambda3_lab.grid()
                self.lambda3_ent.grid()
            else:
                self.lambda3_lab.grid_remove()
                self.lambda3_ent.grid_remove()

        self.failure_mode.trace_add("write", update_failure_mode_visibility)
        update_failure_mode_visibility()

        update_soil_profile_visibility()

        # ====== Loading inclination ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Loading inclination  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        self.N = tk.StringVar(value="5000"); add_row("N (kN)", self.N); 
        self.T = tk.StringVar(value="0"); add_row("T (kN) [ignored if δ used]", self.T); 
        self.use_delta = tk.BooleanVar(value=False)
        ttk.Checkbutton(inp, text="Use δ (deg) instead of T", variable=self.use_delta).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        self.delta_in = tk.StringVar(value="0"); add_row("δ (deg) [used if ticked]; δ=0 means vertical T", self.delta_in); 
        self.theta = tk.StringVar(value="90"); add_row("θ (between T and L′) (deg)", self.theta); 


        # ====== Ground inclination ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Ground inclination  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        # Dedicated EN β field (used by EN g-factors AND by Cyprus when source='β')
        self.beta_en = tk.StringVar(value="0"); add_row("β (EN1997; +=unfavorable) (deg)", self.beta_en); 

        # Dropdown to choose source of KA/KP
        ttk.Label(inp, text="Source for KA & KP (CUT method)").grid(row=r, column=0, sticky="w", padx=(4,2), pady=2)
        self.k_source = tk.StringVar(value="β same with ΕΝ")
        self.k_source_dropdown = ttk.Combobox(
            inp,
            textvariable=self.k_source,
            values=("β same with ΕΝ", "βA & βP", "KA & KP"),
            width=22,
            state="readonly"
        )
        self.k_source_dropdown.grid(row=r, column=1, sticky="w", pady=2)
        r += 1

        # βA/βP fields (used only when source='βA/βP')
        self.betaA = tk.StringVar(value="0")
        self.betaA_lab, self.betaA_ent = add_row("βA (active; +=unfavorable) (deg)", self.betaA); 

        self.betaP = tk.StringVar(value="0")
        self.betaP_lab, self.betaP_ent = add_row("βP (passive; −=unfavorable) (deg)", self.betaP); 

        # KA/KP manual (used only when source='KA&KP')
        self.KA_user = tk.StringVar(value="0")
        self.KA_lab, self.KA_ent = add_row("KA (manual)", self.KA_user); 

        self.KP_user = tk.StringVar(value="0")
        self.KP_lab, self.KP_ent = add_row("KP (manual)", self.KP_user); 

        def update_visibility(*args):
            source = self.k_source.get()
            self.betaA_lab.grid_remove()
            self.betaA_ent.grid_remove()
            self.betaP_lab.grid_remove()
            self.betaP_ent.grid_remove()
            self.KA_lab.grid_remove()
            self.KA_ent.grid_remove()
            self.KP_lab.grid_remove()
            self.KP_ent.grid_remove()
            if "βA & βP" in source:
                self.betaA_lab.grid()
                self.betaA_ent.grid()
                self.betaP_lab.grid()
                self.betaP_ent.grid()
            elif "KA & KP" in source:
                self.KA_lab.grid()
                self.KA_ent.grid()
                self.KP_lab.grid()
                self.KP_ent.grid()

        self.k_source.trace_add("write", update_visibility)
        update_visibility()

        # ====== Seismic excitation ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Seismic excitation  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        self.kh = tk.StringVar(value="0.0"); add_row("k_h", self.kh); 
        self.kv  = tk.StringVar(value="0.0"); add_row("k_v (positive downward)", self.kv); 
        self.khlim = tk.StringVar(value=""); add_row("k_h,lim (blank = auto)", self.khlim); 
        ttk.Label(
            inp,
            text=(
                "The forces T (horizontal) and N (vertical) resulting from the static analysis of the superstructure "
                "should result from the same {k_h, k_v} combination."
            ),
            wraplength=320,
            foreground="gray",
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=(4, 2))
        r += 1

        # ====== Reinforced earth (beta) ======
        sep = ttk.Frame(inp)
        sep.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sep, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sep, text="  Reinforced earth (beta)  ", foreground="gray").pack(side="left")
        ttk.Separator(sep, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        self.use_reinf = tk.BooleanVar(value=False)
        ttk.Checkbutton(inp, text="Enable reinforced earth", variable=self.use_reinf).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        self.n_layers = tk.StringVar(value="4"); add_row("n (layers)", self.n_layers); 
        self.p_tens = tk.StringVar(value="100"); add_row("p (kN/m per layer)", self.p_tens); 

        # ====== Resistance Factor Design ======
        sec = ttk.Frame(inp)
        sec.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        ttk.Label(sec, text="  Resistance Factor Design  ", foreground="gray").pack(side="left")
        ttk.Separator(sec, orient="horizontal").pack(fill="x", expand=True, side="left")
        r += 1

        self.res_factor = tk.StringVar(value="1.0"); add_row("Resistance factor (use it if N and T are factored values)", self.res_factor); 

        # Buttons fixed at bottom of left side (outside the scroll area)
        logo_img = tk.PhotoImage(file=resource_path("cut_logo.png")).subsample(3, 3)
        home_img = tk.PhotoImage(file=resource_path("home.png")).subsample(10, 10)

        def open_manual():
            try:
                import os, subprocess, sys
                manual_path = resource_path("CUT_Bearing_Capacity_User_Manual_v3.pdf")
                if sys.platform.startswith("win"):
                    os.startfile(manual_path)
                elif sys.platform == "darwin":
                    subprocess.call(["open", manual_path])
                else:
                    subprocess.call(["xdg-open", manual_path])
            except Exception as e:
                messagebox.showerror("Error", f"Unable to open CUT_Bearing_Capacity_User_Manual_v3.pdf: {e}")

        def open_cut_k_coulomb():
            try:
                import tkinter as tk
                import CUT_K_Coulomb as ck   # integrated module

                # Create a new child window of the main app
                win = tk.Toplevel(self.winfo_toplevel())
                win.title("CUT_K_Coulomb")

                # Launch the CUT_K_Coulomb UI in that window
                ck.App(win)

            except Exception as e:
                messagebox.showerror("Error", f"Unable to open integrated CUT_K_Coulomb:\n{e}")

        def open_home():
            webbrowser.open("https://cut-apps.streamlit.app/")

        ttk.Separator(inp_footer, orient="horizontal").pack(fill="x", padx=4, pady=(6, 4))
        btn_row = ttk.Frame(inp_footer)
        btn_row.pack(fill="x", padx=4, pady=(0, 8))

        ttk.Button(btn_row, image=logo_img, command=self.compute).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Export (PDF)", command=self.make_report).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="User Manual", command=open_manual).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="CUT_K_Coulomb", command=open_cut_k_coulomb).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="About", command=lambda: messagebox.showinfo("About", ABOUT_TEXT)).pack(side="left")
        ttk.Button(btn_row, image=home_img, command=open_home).pack(side="left", padx=(8, 0))

        self.logo_img = logo_img
        self.home_img = home_img

        # ---- Outputs ----
        out = out_sf.inner
        for i in range(4):
            out.columnconfigure(i, weight=1)
        ttk.Label(out, text="Factor", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w", padx=PAD, pady=(PAD, 2))
        ttk.Label(out, text="EN 1997-3", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=1, sticky="w", padx=PAD, pady=(PAD, 2))
        ttk.Label(out, text="CUT method", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, sticky="w", padx=PAD, pady=(PAD, 2))
        ttk.Label(out, text="Mobilized shear strength of soil", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=3, sticky="w", padx=PAD, pady=(PAD, 2))

        row_specs = [
            ("— N factors —", ["Nc", "Nq", "Nγ", "Nr (reinforcement)"]),
            ("— compressibility factors —", ["cc", "cq", "cγ", "Failure mode"]),
            ("— b (base inclination) —", ["bc", "bq", "bγ"]),
            ("— d (depth) —", ["dc", "dq", "dγ", "dr"]),
            ("— g (ground inclination) —", ["gc", "gq", "gγ"]),
            ("— i (load inclination) —", ["ic", "iq", "iγ"]),
            ("— s (shape) —", ["sc", "sq", "sγ"]),
            ("— w (GWT) —", ["wc", "wq", "wγ"]),
            ("— ε (seismic) & k_h,lim —", ["εc", "εq", "εγ", "k_h,lim"]),
            ("— misc —", [
                "δ used (deg)", "DfA/DfP", "KA used", "KP used",
                "H* (virtual wall height, depth-adjusted)",
                "H* max (depth-adjusted)",
                "Soil mode", "c_eq", "φ_eq", "γ_eq", "Two-layer regime",
                "EN special option", "EN status"
            ]),
        ]
        self.vars = {"orig": {}, "cyp": {}, "mob": {}}
        rg = 1
        for title, labels in row_specs:
            ttk.Separator(out, orient="horizontal").grid(row=rg, column=0, columnspan=4, sticky="ew", pady=(6, 2))
            ttk.Label(out, text=title, font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=0, columnspan=4, sticky="w", padx=PAD)
            rg += 1
            for lab in labels:
                ttk.Label(out, text=lab).grid(row=rg, column=0, sticky="w", padx=PAD)
                v1 = tk.StringVar(value="-")
                v2 = tk.StringVar(value="-")
                v3 = tk.StringVar(value="-")
                ttk.Label(out, textvariable=v1).grid(row=rg, column=1, sticky="w", padx=PAD)
                ttk.Label(out, textvariable=v2).grid(row=rg, column=2, sticky="w", padx=PAD)
                ttk.Label(out, textvariable=v3).grid(row=rg, column=3, sticky="w", padx=PAD)
                self.vars["orig"][lab] = v1
                self.vars["cyp"][lab] = v2
                self.vars["mob"][lab] = v3
                rg += 1

        ttk.Separator(out, orient="horizontal").grid(row=rg, column=0, columnspan=4, sticky="ew", pady=(6, 2)); rg += 1
        ttk.Label(out, text="— mobilized (SMF) —", font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=0, columnspan=4, sticky="w", padx=PAD); rg += 1
        for lab in ["SMF", "c_m (kPa)", "φ_m (deg)"]:
            ttk.Label(out, text=lab, font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=0, sticky="w", padx=PAD)
            v1 = tk.StringVar(value="n/a"); v2 = tk.StringVar(value="n/a"); v3 = tk.StringVar(value="-")
            ttk.Label(out, textvariable=v1, font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=1, sticky="w", padx=PAD)
            ttk.Label(out, textvariable=v2, font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=2, sticky="w", padx=PAD)
            ttk.Label(out, textvariable=v3, font=("TkDefaultFont", 9, "bold")).grid(row=rg, column=3, sticky="w", padx=PAD)
            self.vars["orig"][lab] = v1
            self.vars["cyp"][lab] = v2
            self.vars["mob"][lab] = v3
            rg += 1
        ttk.Separator(out, orient="horizontal").grid(row=rg, column=0, columnspan=4, sticky="ew", pady=(6, 6)); rg += 1
        ttk.Label(out, text="q_ult (kPa)", font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=0, sticky="w", padx=PAD)
        self.qult_orig = tk.StringVar(value="-")
        self.qult_cyp = tk.StringVar(value="-")
        self.qult_mob = tk.StringVar(value="-")
        ttk.Label(out, textvariable=self.qult_orig, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=1, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.qult_cyp, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=2, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.qult_mob, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=3, sticky="w", padx=PAD)
        rg += 1

        # --- Add R_N below q_ult ---
        ttk.Label(out, text="R_N (kN)", font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=0, sticky="w", padx=PAD)
        self.RN_orig = tk.StringVar(value="-")
        self.RN_cyp = tk.StringVar(value="-")
        self.RN_mob = tk.StringVar(value="-")
        ttk.Label(out, textvariable=self.RN_orig, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=1, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.RN_cyp, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=2, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.RN_mob, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=3, sticky="w", padx=PAD)
        rg += 1
        
        # --- Add R_N / N (safety ratio) below R_N ---
        ttk.Label(out, text="R_N / N (safety ratio)", font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=0, sticky="w", padx=PAD)
        self.RNoverN_orig = tk.StringVar(value="-")
        self.RNoverN_cyp  = tk.StringVar(value="-")
        self.RNoverN_mob  = tk.StringVar(value="-")
        ttk.Label(out, textvariable=self.RNoverN_orig, font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=1, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.RNoverN_cyp,  font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=2, sticky="w", padx=PAD)
        ttk.Label(out, textvariable=self.RNoverN_mob,  font=("TkDefaultFont", 11, "bold")).grid(row=rg, column=3, sticky="w", padx=PAD)
        rg += 1

    # ---------- helper for mobilized column ----------


    def _cyprus_qult_with_params(self, c_val, phi_deg, kv_override, kh_override, params, return_factors=False):
        # params: dictionary with keys used in compute() to avoid re-parsing UI again.
        import math
        Beff = params["Beff"]; Leff = params["Leff"]; Df = params["Df"]; DfA = params["DfA"]; DfP = params["DfP"]
        Dw = params["Dw"]; psi = params["psi"]; gd = params["gd"]; gs = params["gs"]; gw = params["gw"]
        alpha = params["alpha"]; beta_en = params["beta_en"]; theta = params["theta"]
        source_key = params["source_key"]
        KA_user = params["KA_user"]; KP_user = params["KP_user"]
        betaA = params["betaA"]; betaP = params["betaP"]
        delta_used = params["delta_used"]; res_pf = params["res_pf"]
        use_reinf = params["use_reinf"]; n_layers = params["n_layers"]; p_tens = params["p_tens"]
        footing_type = params["footing_type"]; is_circular = params.get("is_circular", False)
        failure_mode = params.get("failure_mode", "General shear")
        f_cs = params.get("f_cs", 1.0)
        lambda3 = params.get("lambda3", 0.5)

        kv = kv_override
        kh = kh_override

        gd_eff = gd * (1.0 + kv)
        gs_eff = gs * (1.0 + kv)

        # KA/KP from dropdown source, but using phi_deg for the soil friction
        if source_key == "KAKP":
            KA_used = KA_user; KP_used = KP_user
        elif source_key == "B_AP":
            KA_used = coulomb_Ka(phi_deg, betaA, 0.0)
            KP_used = coulomb_Kp(phi_deg, betaP, 0.0)
        else:
            KA_used = coulomb_Ka(phi_deg, beta_en, 0.0)
            KP_used = coulomb_Kp(phi_deg, -beta_en, 0.0)

        # Cyprus NA N-factors (depend on phi)
        H = H_distance(Beff, phi_deg)
        rHB = H / max(Beff, 1e-12)
        invJ = 1.0 / max(IB_over_B(phi_deg, footing_type), 1e-12)
        df_ratio = DfA / max(DfP, 1e-12)
        Nq_c = df_ratio + (KP_used / max(KA_used, 1e-12) - df_ratio) * rHB * invJ
        Ng_c = (KP_used - KA_used) / max(KA_used, 1e-12) * (rHB ** 2) * invJ
        Nc_c = 2.0 * (math.sqrt(KP_used) + math.sqrt(KA_used)) / max(KA_used, 1e-12) * rHB * invJ
        Nr_c = invJ / max(KA_used, 1e-12)

        # Shape factors
        sc_c, sq_c, sg_c = cyprus_shape_factors(phi_deg, Beff, Leff)
        if is_circular:
            circ_factor = 4.0 / math.pi
            sc_c *= circ_factor
            sq_c *= circ_factor
            sg_c *= circ_factor

        dc_c, dq_c, dg_c, _ = cyprus_depth_factors(phi_deg, Beff, Df, psi)
        dr_c = dc_c
        ic_c, iq_c, ig_c = cyprus_inclination_factors(phi_deg, delta_used, Beff, Leff, theta, psi)

        # b-factors
        phi_rad = math.radians(phi_deg)
        if abs(phi_deg) <= 1e-12:
            bq_c = 1.0; bg_c = 1.0; bc_c = 1.0
        else:
            a = math.radians(alpha)
            Nc_approx = (math.exp(math.pi * math.tan(phi_rad)) * (math.tan(math.pi/4 + phi_rad/2)**2) - 1.0) / (math.tan(phi_rad) + 1e-12)
            bq_c = (1.0 - a * math.tan(phi_rad))**2
            bg_c = bq_c
            bc_c = bq_c - (1.0 - bq_c) / (Nc_approx * math.tan(phi_rad) + 1e-12)

        gc_c, gq_c, gg_c = 1.0, 1.0, 1.0

        # Compressibility factors for the CUT method
        if failure_mode in ("Local shear", "Punching shear"):
            mode = "local" if failure_mode == "Local shear" else "edge"
            comp = compute_soil_compressibility_factors(
                c=c_val, phi_deg=phi_deg, gamma=gd, Df=Df, B=Beff, L=Leff,
                f_cs=f_cs, footing_type=footing_type, Df_A=DfA, Df_P=DfP,
                mode=mode, lambda3=lambda3
            )
            cc_factor = comp["c_c"]
            cq_factor = comp["c_q"]
            cg_factor = comp["c_gamma"]
            failure_mode_short = "Local" if failure_mode == "Local shear" else "Punching"
        else:
            cc_factor = 1.0
            cq_factor = 1.0
            cg_factor = 1.0
            failure_mode_short = "General"

        # seismic factors
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
            ec_c, eq_c, eg_c = 1.0, 1.0, 1.0

        # surcharge and gamma
        q_total = gd_eff * Df
        gamma_total = gd_eff
        v_loc = cyprus_depth_factors(phi_deg, Beff, Df, psi)[0]
        Hstar_local = H_distance(Beff, phi_deg) * v_loc
        _, geff_cyp_local = effective_surcharge_and_gamma(Df, Beff, Dw, gd_eff, gs_eff, gw)
        wc, wq, wy = cyprus_w_factors(Dw, Df, Hstar_local, geff_cyp_local, gd_eff)

        # reinforcement
        if use_reinf and n_layers > 0.0 and p_tens > 0.0 and Beff > 0.0:
            q_r = (n_layers * p_tens / Beff) * Nr_c
            term_r_c = q_r
        else:
            term_r_c = 0.0

        term_c_c = (c_val * cc_factor * Nc_c * bc_c * dc_c * gc_c * ic_c * sc_c * ec_c * wc) / max(res_pf, 1e-12)
        term_q_c = (q_total * cq_factor * wq * Nq_c * bq_c * dq_c * gq_c * iq_c * sq_c * eq_c) / max(res_pf, 1e-12)
        term_g_c = (0.5 * gamma_total * cg_factor * wy * Beff * Ng_c * bg_c * dg_c * gg_c * ig_c * sg_c * eg_c) / max(res_pf, 1e-12)

        qult_c = term_c_c + term_q_c + term_g_c + term_r_c
        if return_factors:
            H = H_distance(Beff, phi_deg)
            Hstar = H * (cyprus_depth_factors(phi_deg, Beff, Df, psi)[0])
            Hmax_star = Hmax_distance(Beff, phi_deg) * (cyprus_depth_factors(phi_deg, Beff, Df, psi)[0])
            factors = {
                "Nc": Nc_c, "Nq": Nq_c, "Nγ": Ng_c, "Nr (reinforcement)": Nr_c,
                "bc": bc_c, "bq": bq_c, "bγ": bg_c,
                "dc": dc_c, "dq": dq_c, "dγ": dg_c, "dr": dr_c,
                "gc": gc_c, "gq": gq_c, "gγ": gg_c,
                "ic": ic_c, "iq": iq_c, "iγ": ig_c,
                "sc": sc_c, "sq": sq_c, "sγ": sg_c,
                "wc": wc, "wq": wq, "wγ": wy,
                "εc": ec_c, "εq": eq_c, "εγ": eg_c, "k_h,lim": kh_lim,
                "δ used (deg)": params.get("delta_used", 0.0),
                "DfA/DfP": DfA / max(DfP, 1e-12),
                "KA used": KA_used,
                "KP used": KP_used,
                "H* (virtual wall height, depth-adjusted)": Hstar,
                "H* max (depth-adjusted)": Hmax_star,
                "cc": cc_factor,
                "cq": cq_factor,
                "cγ": cg_factor,
                "Failure mode": failure_mode_short,
            }
            return qult_c, factors

        return qult_c


    def make_report(self):
        from tkinter import filedialog
        from datetime import datetime

        # -----------------------------
        # Generate timestamped filename
        # -----------------------------
        now = datetime.now()
        default_name = f"CUT_Bearing_Capacity_Report_{now:%Y%m%d_%H%M}.pdf"

        # -----------------------------
        # Ask user where to save file
        # -----------------------------
        file_path = filedialog.asksaveasfilename(
            title="Save Report As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=default_name
        )

        if not file_path:
            return  # user cancelled

        pdf_path = file_path

        # -----------------------------
        # Begin PDF building
        # -----------------------------
        try:
            import os, sys
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except Exception:
            messagebox.showerror(
                "Missing library",
                "Report creation requires ReportLab.\nInstall with:\n\npip install reportlab"
            )
            return

        out_dir = os.path.dirname(__file__)

        # Helpers
        def _val(x):
            try:
                return x.get()
            except Exception:
                return str(x)

        def make_2col_table(data):
            t = Table(data, colWidths=[220, 280])
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            return t

        def make_outputs_table(rows):
            # rows is a list of [Factor, EN, CUT, MOB]
            t = Table([["Factor", "EN 1997-3", "CUT method", "Mobilized"]] + rows,
                      colWidths=[180, 120, 120, 120])
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            return t

        def make_soil_profile_table():
            rows = [["Layer", "c (kPa)", "φ (deg)", "ψ (deg)", "γ (kN/m³)", "γsat (kN/m³)", "H (m)"]]
            if self.soil_layers.get() == "2 layers":
                rows.append([
                    "Layer 1",
                    _val(self.c1),
                    _val(self.phi1),
                    _val(self.psi1),
                    _val(self.gamma1_layer),
                    _val(self.gamma_sat1_layer),
                    _val(self.H1_layer),
                ])
                rows.append([
                    "Layer 2",
                    _val(self.c2),
                    _val(self.phi2),
                    _val(self.psi2),
                    _val(self.gamma2_layer),
                    _val(self.gamma_sat2_layer),
                    "Infinite",
                ])
            else:
                rows.append([
                    "Layer 1",
                    _val(self.coh),
                    _val(self.phi),
                    _val(self.psi1),
                    _val(self.gamma_dry),
                    _val(self.gamma_sat),
                    "Infinite",
                ])
            t = Table(rows, colWidths=[60, 70, 70, 70, 80, 85, 65])
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ]))
            return t

        # -----------------------------
        # INPUTS
        # -----------------------------
        is_circ = bool(self.is_circular.get())

        geom_inputs = [
            ["B, B′ or D (m)", _val(self.Beff)],
            ["L or L′ (m)", _val(self.Leff)],
            ["Df (m)", _val(self.Df)],
            ["DfA (m)", _val(self.DfP)],
            ["Dw (m)", _val(self.Dw)],
            ["α base (deg)", _val(self.alpha)],
            ["Footing type (CUT method)", _val(self.footing_type)],
        ]
        if is_circ:
            geom_inputs.append(["Footing shape", "Circular (B=D; L ignored)"])

        soil_inputs_general = [["Soil profile", _val(self.soil_layers)]]
        if self.soil_layers.get() == "2 layers":
            soil_inputs_general += [
                ["γ_w (kN/m³)", _val(self.gamma_w)],
                ["Allow EN for 2-layer/seismic via c_m, φ_m", str(self.allow_en_special.get())],
                ["Failure mode", _val(self.failure_mode)],
                ["f_cs", _val(self.fcs) if self.failure_mode.get() in ("Local shear", "Punching shear") else "1.0"],
                ["λ3", _val(self.lambda3) if self.failure_mode.get() == "Local shear" else "-"],
            ]
        else:
            soil_inputs_general += [
                ["γ_w (kN/m³)", _val(self.gamma_w)],
                ["Allow EN for 2-layer/seismic via c_m, φ_m", str(self.allow_en_special.get())],
                ["Failure mode", _val(self.failure_mode)],
                ["f_cs", _val(self.fcs) if self.failure_mode.get() in ("Local shear", "Punching shear") else "1.0"],
                ["λ3", _val(self.lambda3) if self.failure_mode.get() == "Local shear" else "-"],
            ]

        loading_inputs = [
            ["N (kN)", _val(self.N)],
            ["T (kN)", _val(self.T)],
            ["Use δ instead of T", str(self.use_delta.get())],
            ["δ (deg)", _val(self.delta_in)],
            ["θ (deg)", _val(self.theta)],
        ]

        ground_inputs = [
            ["β (EN) (deg)", _val(self.beta_en)],
            ["Source for CUT KA & KP", _val(self.k_source)],
        ]

        source = self.k_source.get()
        if "βA & βP" in source:
            ground_inputs += [
                ["βA (deg)", _val(self.betaA)],
                ["βP (deg)", _val(self.betaP)],
            ]
        elif "KA & KP" in source:
            ground_inputs += [
                ["KA (manual)", _val(self.KA_user)],
                ["KP (manual)", _val(self.KP_user)],
            ]

        seismic_inputs = [
            ["k_h", _val(self.kh)],
            ["k_v", _val(self.kv)],
            ["k_h,lim", _val(self.khlim)],
        ]

        reinf_inputs = [
            ["Reinforced earth?", str(self.use_reinf.get())],
            ["n (layers)", _val(self.n_layers)],
            ["p (kN/m per layer)", _val(self.p_tens)],
        ]

        resist_inputs = [
            ["Resistance factor", _val(self.res_factor)],
        ]

        def get_row(factor_name):
            return [
                factor_name,
                self.vars["orig"][factor_name].get(),
                self.vars["cyp"][factor_name].get(),
                self.vars["mob"][factor_name].get(),
            ]

        categories = [
            ("N factors", ["Nc", "Nq", "Nγ", "Nr (reinforcement)"]),
            ("Compressibility factors", ["cc", "cq", "cγ", "Failure mode"]),
            ("b (base inclination)", ["bc", "bq", "bγ"]),
            ("d (depth)", ["dc", "dq", "dγ", "dr"]),
            ("g (ground inclination)", ["gc", "gq", "gγ"]),
            ("i (load inclination)", ["ic", "iq", "iγ"]),
            ("s (shape)", ["sc", "sq", "sγ"]),
            ("w (GWT)", ["wc", "wq", "wγ"]),
            ("ε (seismic) & k_h,lim", ["εc", "εq", "εγ", "k_h,lim"]),
            ("misc", [
                "δ used (deg)", "DfA/DfP", "KA used", "KP used",
                "H* (virtual wall height, depth-adjusted)",
                "H* max (depth-adjusted)",
                "Soil mode", "c_eq", "φ_eq", "γ_eq", "Two-layer regime",
                "EN special option", "EN status"
            ]),
            ("Mobilized shear strength of soil", ["SMF", "c_m (kPa)", "φ_m (deg)"]),
        ]

        # -----------------------------
        # BUILD PDF DOCUMENT
        # -----------------------------
        styles = getSampleStyleSheet()
        elements = []

        logo_path = os.path.join(out_dir, "cut_logo.png")
        if os.path.exists(logo_path):
            logo = Image(logo_path)
            max_w = 120.0
            iw, ih = logo.imageWidth, logo.imageHeight
            if iw > 0 and ih > 0:
                scale = min(max_w / iw, 1.0)
                logo.drawWidth = iw * scale
                logo.drawHeight = ih * scale
            elements.append(logo)
            elements.append(Spacer(1, 12))

        elements.append(Paragraph("<b>CUT Bearing Capacity Report</b>", styles["Title"]))
        elements.append(Paragraph(now.strftime("%Y-%m-%d %H:%M"), styles["Normal"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("<b>About</b>", styles["Heading2"]))
        elements.append(Paragraph(ABOUT_TEXT.replace("\n", "<br/>"), styles["BodyText"]))
        elements.append(Spacer(1, 12))

        # -----------------------------
        # INPUT SECTIONS
        # -----------------------------
        elements.append(Paragraph("<b>Inputs</b>", styles["Heading2"]))
        elements.append(Spacer(1, 6))

        sections = [
            ("Geometry & GWT", geom_inputs),
            ("Soil data", soil_inputs_general),
            ("Loading inclination", loading_inputs),
            ("Ground inclination", ground_inputs),
            ("Seismic excitation", seismic_inputs),
            ("Reinforced earth (beta)", reinf_inputs),
            ("Resistance Factor Design", resist_inputs),
        ]

        for title, table_data in sections:
            elements.append(Paragraph(f"<b>{title}</b>", styles["Heading3"]))
            if title == "Soil data":
                elements.append(make_2col_table(soil_inputs_general))
                elements.append(Spacer(1, 6))
                elements.append(make_soil_profile_table())
            else:
                elements.append(make_2col_table(table_data))
            elements.append(Spacer(1, 12))

        # -----------------------------
        # OUTPUT SECTIONS
        # -----------------------------
        elements.append(Paragraph("<b>Outputs</b>", styles["Heading2"]))
        elements.append(Spacer(1, 6))

        for title, keys in categories:
            rows = []
            for k in keys:
                try:
                    rows.append(get_row(k))
                except KeyError:
                    rows.append([k, "-", "-", "-"])
            elements.append(Paragraph(f"<b>{title}</b>", styles["Heading3"]))
            elements.append(make_outputs_table(rows))
            elements.append(Spacer(1, 10))

        # -----------------------------
        # q_ult table
        # -----------------------------
        q_rows = [["q_ult (kPa)", self.qult_orig.get(), self.qult_cyp.get(), self.qult_mob.get()]]
        t_qult = Table(q_rows, colWidths=[180, 120, 120, 120])
        t_qult.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('BACKGROUND', (0,0), (-1,-1), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ]))
        elements.append(t_qult)

        # -----------------------------
        # R_N table
        # -----------------------------
        RN_rows = [["R_N (kN)", self.RN_orig.get(), self.RN_cyp.get(), self.RN_mob.get()]]
        t_RN = Table(RN_rows, colWidths=[180, 120, 120, 120])
        t_RN.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(t_RN)

        # -----------------------------
        # R_N / N table
        # -----------------------------
        SR_rows = [["R_N / N (safety ratio)", self.RNoverN_orig.get(), self.RNoverN_cyp.get(), self.RNoverN_mob.get()]]
        t_SR = Table(SR_rows, colWidths=[180, 120, 120, 120])
        t_SR.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(t_SR)

        # -----------------------------
        # Footnote
        # -----------------------------
        foot = (
            "EN uses effective stresses (w = 1; water-table effect is in γ*). "
            "CUT method uses total-stress + w-factors."
        )
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(foot, styles["BodyText"]))

        # -----------------------------
        # WRITE PDF
        # -----------------------------
        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            doc.build(elements)
            messagebox.showinfo("Report", f"PDF saved:\n{pdf_path}")
        except Exception as e:
            messagebox.showerror("Report error", f"Could not create report:\n{e}")


    # ---------- compute ----------

    def compute(self):
        try:
            Beff = safe_float(self.Beff.get(), 0.0)
            Leff = safe_float(self.Leff.get(), 0.0)
            is_circular = self.is_circular.get()
            if is_circular:
                Leff = Beff

            Df = safe_float(self.Df.get(), 0.0)
            DfA = safe_float(self.DfP.get(), Df)
            DfP = Df
            Dw = safe_float(self.Dw.get(), 0.0)

            soil_mode = self.soil_layers.get()

            if soil_mode == "1 layer":
                c_val = safe_float(self.coh.get(), 0.0)
                phi = safe_float(self.phi.get(), 0.0)
                gd = safe_float(self.gamma_dry.get(), 18.0)
                psi = safe_float(self.psi1.get(), 0.0)
                eq_info = {
                    "mode": "1_layer",
                    "ceq": c_val,
                    "phi_eq_deg": phi,
                    "gamma_eq": gd,
                    "regime": "single_layer_input",
                    "I1": 0.0,
                    "I2": 0.0,
                }
            else:
                c1 = safe_float(self.c1.get(), 0.0)
                phi1 = safe_float(self.phi1.get(), 0.0)
                gamma1 = safe_float(self.gamma1_layer.get(), 18.0)
                H1 = safe_float(self.H1_layer.get(), 0.0)
                c2 = safe_float(self.c2.get(), 0.0)
                phi2 = safe_float(self.phi2.get(), 0.0)
                gamma2 = safe_float(self.gamma2_layer.get(), 18.0)
                if H1 <= 0:
                    raise ValueError("For 2-layer soil, H1 must be > 0.")
                eq_info = compute_two_layer_equivalent(
                    B=Beff, DfA=DfA, DfP=DfP,
                    c1=c1, phi1_deg=phi1, gamma1=gamma1, H1=H1,
                    c2=c2, phi2_deg=phi2, gamma2=gamma2,
                )
                c_val = eq_info["ceq"]
                phi = eq_info["phi_eq_deg"]
                gd = eq_info["gamma_eq"]
                psi1 = safe_float(self.psi1.get(), 0.0)
                psi2 = safe_float(self.psi2.get(), 0.0)
                I1 = eq_info.get("I1", 0.0)
                I2 = eq_info.get("I2", 0.0)
                denom_psi = I1 + I2
                if abs(denom_psi) < 1e-12:
                    psi = psi1
                else:
                    psi = (psi1 * I1 + psi2 * I2) / denom_psi

            if soil_mode == "1 layer":
                gs = safe_float(self.gamma_sat.get(), 20.0)
            else:
                gamma_sat1 = safe_float(self.gamma_sat1_layer.get(), 20.0)
                gamma_sat2 = safe_float(self.gamma_sat2_layer.get(), 20.0)
                if eq_info.get("regime") == "homogeneous_layer_1":
                    gs = gamma_sat1
                else:
                    gs = 0.5 * (gamma_sat1 + gamma_sat2)
            kv = safe_float(self.kv.get(), 0.0)
            gd_eff = gd * (1.0 + kv)
            gs_eff = gs * (1.0 + kv)
            gw = safe_float(self.gamma_w.get(), 9.81)

            Nn = safe_float(self.N.get(), 1.0)
            alpha = safe_float(self.alpha.get(), 0.0)

            res_pf = safe_float(self.res_factor.get(), 1.0)
            if res_pf <= 0:
                res_pf = 1e-12

            raw_source = self.k_source.get().strip()
            label_norm = raw_source.replace(" ", "").replace("&", "").replace("και", "").lower()
            if "kakp" in label_norm:
                source_key = "KAKP"
            elif ("βaβp" in label_norm) or ("βαβp" in label_norm) or ("ba bp" in raw_source.lower()):
                source_key = "B_AP"
            else:
                source_key = "B_EN"

            beta_en_txt = self.beta_en.get().strip()
            beta_en = float(beta_en_txt) if beta_en_txt != "" else 0.0

            betaA_txt = self.betaA.get().strip()
            betaP_txt = self.betaP.get().strip()
            KA_user_txt = self.KA_user.get().strip()
            KP_user_txt = self.KP_user.get().strip()

            theta = safe_float(self.theta.get(), 0.0)
            kh = safe_float(self.kh.get(), 0.0)
            khlim_in = self.khlim.get().strip()

            use_reinf = self.use_reinf.get()
            n_layers = max(0.0, safe_float(self.n_layers.get(), 0.0))
            p_tens = max(0.0, safe_float(self.p_tens.get(), 0.0))

            if self.use_delta.get():
                delta_in = safe_float(self.delta_in.get(), 0.0)
                Tt = Nn * math.tan(math.radians(abs(delta_in)))
                delta_used = abs(delta_in)
            else:
                Tt = safe_float(self.T.get(), 0.0)
                delta_used = math.degrees(math.atan(Tt / Nn)) if abs(Nn) > 1e-12 else 0.0

            failure_mode = self.failure_mode.get()
            footing_type = self.footing_type.get()

            if failure_mode in ("Local shear", "Punching shear"):
                f_cs = safe_float(self.fcs.get(), 1.0)
                if not (0.0 <= f_cs <= 1.0):
                    raise ValueError("For local/punching shear, f_cs must be between 0 and 1.")

                lambda3 = safe_float(self.lambda3.get(), 0.5)
                if failure_mode == "Local shear" and not (0.5 <= lambda3 <= 1.0):
                    raise ValueError("For local shear, λ3 must be between 0.5 and 1.0.")

                auto_switch = False

                if f_cs >= 0.80:
                    self.failure_mode.set("General shear")
                    self.fcs.set("1.0")
                    failure_mode = "General shear"
                    f_cs = 1.0
                    auto_switch = True

                if failure_mode in ("Local shear", "Punching shear"):
                    mode = "local" if failure_mode == "Local shear" else "edge"
                    c_en = f_cs * c_val
                    phi_en = math.degrees(math.atan(f_cs * math.tan(math.radians(phi))))
                    comp = compute_soil_compressibility_factors(
                        c=c_val, phi_deg=phi, gamma=gd, Df=Df, B=Beff, L=Leff,
                        f_cs=f_cs, footing_type=footing_type, Df_A=DfA, Df_P=DfP,
                        mode=mode, lambda3=lambda3
                    )
                    cc_factor = comp["c_c"]
                    cq_factor = comp["c_q"]
                    cg_factor = comp["c_gamma"]
                    mob_smf = f_cs
                    mob_c = c_en
                    mob_phi = phi_en
                    failure_mode_short = "Local" if failure_mode == "Local shear" else "Punching"
                else:
                    c_en = c_val
                    phi_en = phi
                    cc_factor = 1.0
                    cq_factor = 1.0
                    cg_factor = 1.0
                    mob_smf = 1.0
                    mob_c = c_val
                    mob_phi = phi
                    failure_mode_short = "General"

                    if auto_switch:
                        self.after(
                            10,
                            lambda: messagebox.showwarning(
                                "Warning",
                                "f_cs ≥ 0.80 approaches general shear conditions.\n"
                                "Model automatically switched to 'General shear' mode."
                            )
                        )
            else:
                f_cs = 1.0
                lambda3 = 0.5
                c_en = c_val
                phi_en = phi
                cc_factor = 1.0
                cq_factor = 1.0
                cg_factor = 1.0
                mob_smf = 1.0
                mob_c = c_val
                mob_phi = phi
                failure_mode_short = "General"

            Aeff = Beff * Leff
            qeff_en, geff_en = effective_surcharge_and_gamma(Df, Beff, Dw, gd, gs, gw)

            def compute_en_results(c_strength, phi_strength):
                undrained_local = (abs(phi_strength) <= 1e-6)
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
                return {
                    "undrained": undrained_local,
                    "Nc": Nc_l, "Nq": Nq_l, "Nγ": Ng_l,
                    "bc": bc_l, "bq": bq_l, "bγ": bg_l,
                    "dc": dc_l, "dq": dq_l, "dγ": dg_l,
                    "gc": gc_l, "gq": gq_l, "gγ": gg_l,
                    "ic": ic_l, "iq": iq_l, "iγ": ig_l,
                    "sc": sc_l, "sq": sq_l, "sγ": sg_l,
                    "term_c": term_c_l, "term_q": term_q_l, "term_g": term_g_l,
                    "qult": qult_l,
                }

            en_base = compute_en_results(c_en, phi_en)
            Nc_o, Nq_o, Ng_o = en_base["Nc"], en_base["Nq"], en_base["Nγ"]
            bc_o, bq_o, bg_o = en_base["bc"], en_base["bq"], en_base["bγ"]
            dc_o, dq_o, dg_o = en_base["dc"], en_base["dq"], en_base["dγ"]
            gc_o, gq_o, gg_o = en_base["gc"], en_base["gq"], en_base["gγ"]
            ic_o, iq_o, ig_o = en_base["ic"], en_base["iq"], en_base["iγ"]
            sc_o, sq_o, sg_o = en_base["sc"], en_base["sq"], en_base["sγ"]
            undrained_en = en_base["undrained"]

            betaA = 0.0
            betaP = 0.0
            KA_label = 0.0
            KP_label = 0.0

            # CUT method: always use the given peak strengths; compressibility enters through cc, cq, cγ
            if source_key == "KAKP":
                KA_used = float(KA_user_txt) if KA_user_txt != "" else 0.0
                KP_used = float(KP_user_txt) if KP_user_txt != "" else 0.0
                if KA_used <= 0 or KP_used <= 0:
                    raise ValueError("For 'KA & KP' source, please provide positive KA and KP.")
                KA_label = KA_used
                KP_label = KP_used
            elif source_key == "B_AP":
                betaA = float(betaA_txt) if betaA_txt != "" else 0.0
                betaP = float(betaP_txt) if betaP_txt != "" else 0.0
                KA_used = coulomb_Ka(phi, betaA, 0.0)
                KP_used = coulomb_Kp(phi, betaP, 0.0)
                KA_label = KA_used
                KP_label = KP_used
            else:
                betaA = beta_en
                betaP = -beta_en
                KA_used = coulomb_Ka(phi, betaA, 0.0)
                KP_used = coulomb_Kp(phi, betaP, 0.0)
                KA_label = KA_used
                KP_label = KP_used

            H = H_distance(Beff, phi)
            rHB = H / max(Beff, 1e-12)
            invJ = 1.0 / max(IB_over_B(phi, footing_type), 1e-12)

            df_ratio = DfA / max(DfP, 1e-12)
            Nq_c = df_ratio + (KP_used / max(KA_used, 1e-12) - df_ratio) * rHB * invJ
            Ng_c = (KP_used - KA_used) / max(KA_used, 1e-12) * (rHB ** 2) * invJ
            Nc_c = 2.0 * (math.sqrt(KP_used) + math.sqrt(KA_used)) / max(KA_used, 1e-12) * rHB * invJ
            Nr_c = invJ / max(KA_used, 1e-12)

            sc_c, sq_c, sg_c = cyprus_shape_factors(phi, Beff, Leff)
            if is_circular:
                circ_factor = 4.0 / math.pi
                sc_c *= circ_factor
                sq_c *= circ_factor
                sg_c *= circ_factor

            dc_c, dq_c, dg_c, _ = cyprus_depth_factors(phi, Beff, Df, psi)
            dr_c = dc_c
            ic_c, iq_c, ig_c = cyprus_inclination_factors(phi, delta_used, Beff, Leff, theta, psi)

            bc_c, bq_c, bg_c = bc_o, bq_o, bg_o
            gc_c, gq_c, gg_c = 1.0, 1.0, 1.0

            if khlim_in:
                try:
                    kh_lim = float(khlim_in)
                except Exception:
                    kh_lim = 0.0
            else:
                v_loc = cyprus_depth_factors(phi, Beff, Df, psi)[0]
                Hmax_star_local = Hmax_distance(Beff, phi) * v_loc
                f = max(0.0, min(1.0, (Df + Hmax_star_local - Dw) / max(Hmax_star_local, 1e-12)))
                geff_tmp = (1.0 - f) * gd_eff + f * gs_eff
                denom = max(geff_tmp * max(Hmax_star_local, 1e-12), 1e-12)
                kh_lim = math.tan(math.radians(phi)) + (c_val / denom)
            ec_c, eq_c, eg_c = cyprus_seismic_factors(kh, kh_lim)

            # EN 1997-3 base evaluation (used directly only in the standard case)
            term_c_o = en_base["term_c"]
            term_q_o = en_base["term_q"]
            term_g_o = en_base["term_g"]
            qult_o = en_base["qult"]

            # CUT method with compressibility embedded
            q_total = gd_eff * Df
            gamma_total = gd_eff
            v_loc = cyprus_depth_factors(phi, Beff, Df, psi)[0]
            Hstar_local = H_distance(Beff, phi) * v_loc
            _, geff_cyp_local = effective_surcharge_and_gamma(Df, Beff, Dw, gd_eff, gs_eff, gw)
            wc, wq, wy = cyprus_w_factors(Dw, Df, Hstar_local, geff_cyp_local, gd_eff)

            term_c_c = (c_val * cc_factor * Nc_c * bc_c * dc_c * gc_c * ic_c * sc_c * ec_c * wc) / res_pf
            term_q_c = (q_total * cq_factor * wq * Nq_c * bq_c * dq_c * gq_c * iq_c * sq_c * eq_c) / res_pf
            term_g_c = (0.5 * gamma_total * cg_factor * wy * Beff * Ng_c * bg_c * dg_c * gg_c * ig_c * sg_c * eg_c) / res_pf

            if use_reinf and n_layers > 0.0 and p_tens > 0.0 and Beff > 0.0:
                q_r = (n_layers * p_tens / Beff) * Nr_c
                term_r_c = q_r
            else:
                term_r_c = 0.0

            qult_c = term_c_c + term_q_c + term_g_c + term_r_c

            en_special_case = (soil_mode == "2 layers") or (abs(kh) > 1e-12) or (abs(kv) > 1e-12)
            en_special_allowed = bool(self.allow_en_special.get())
            if en_special_case and not en_special_allowed:
                en_out = None
                en_comp_comment = "n/a"
                en_status = "disabled"
            else:
                en_out = en_base
                en_comp_comment = "via strength"
                en_status = "standard"

            def setv(dic, key, val, suffix: str = ""):
                try:
                    s = f"{float(val):.4f}"
                except Exception:
                    s = str(val)
                if suffix:
                    s = f"{s} {suffix}"
                dic[key].set(s)

            # N
            if en_out is not None:
                setv(self.vars["orig"], "Nc", en_out["Nc"])
                setv(self.vars["orig"], "Nq", en_out["Nq"])
                setv(self.vars["orig"], "Nγ", en_out["Nγ"])
            else:
                self.vars["orig"]["Nc"].set("n/a")
                self.vars["orig"]["Nq"].set("n/a")
                self.vars["orig"]["Nγ"].set("n/a")
            setv(self.vars["cyp"],  "Nc", Nc_c)
            setv(self.vars["cyp"],  "Nq", Nq_c)
            setv(self.vars["cyp"],  "Nγ", Ng_c)
            self.vars["orig"]["Nr (reinforcement)"].set("n/a")
            setv(self.vars["cyp"],  "Nr (reinforcement)", Nr_c)
            self.vars["mob"]["Nr (reinforcement)"].set("n/a")

            # compressibility factors
            self.vars["orig"]["cc"].set(en_comp_comment)
            self.vars["orig"]["cq"].set(en_comp_comment)
            self.vars["orig"]["cγ"].set(en_comp_comment)
            self.vars["orig"]["Failure mode"].set(failure_mode_short if en_out is not None else "n/a")
            setv(self.vars["cyp"], "cc", cc_factor)
            setv(self.vars["cyp"], "cq", cq_factor)
            setv(self.vars["cyp"], "cγ", cg_factor)
            self.vars["cyp"]["Failure mode"].set(failure_mode_short)
            self.vars["mob"]["cc"].set("via c_m,φ_m")
            self.vars["mob"]["cq"].set("via c_m,φ_m")
            self.vars["mob"]["cγ"].set("via c_m,φ_m")
            self.vars["mob"]["Failure mode"].set(failure_mode_short)

            # b
            if en_out is not None:
                setv(self.vars["orig"], "bc", en_out["bc"])
                setv(self.vars["orig"], "bq", en_out["bq"])
                setv(self.vars["orig"], "bγ", en_out["bγ"])
            else:
                self.vars["orig"]["bc"].set("n/a")
                self.vars["orig"]["bq"].set("n/a")
                self.vars["orig"]["bγ"].set("n/a")
            setv(self.vars["cyp"], "bc", bc_c, "(EN bc)")
            setv(self.vars["cyp"], "bq", bq_c, "(EN bq)")
            setv(self.vars["cyp"], "bγ", bg_c, "(EN bγ)")

            # d (+dr)
            if en_out is not None:
                setv(self.vars["orig"], "dc", en_out["dc"])
                setv(self.vars["orig"], "dq", en_out["dq"])
                setv(self.vars["orig"], "dγ", en_out["dγ"])
            else:
                self.vars["orig"]["dc"].set("n/a")
                self.vars["orig"]["dq"].set("n/a")
                self.vars["orig"]["dγ"].set("n/a")
            setv(self.vars["cyp"],  "dc", dc_c)
            setv(self.vars["cyp"],  "dq", dq_c)
            setv(self.vars["cyp"],  "dγ", dg_c)
            self.vars["orig"]["dr"].set("n/a")
            setv(self.vars["cyp"],  "dr", dr_c)

            # g
            if en_out is not None:
                setv(self.vars["orig"], "gc", en_out["gc"])
                setv(self.vars["orig"], "gq", en_out["gq"])
                setv(self.vars["orig"], "gγ", en_out["gγ"])
            else:
                self.vars["orig"]["gc"].set("n/a")
                self.vars["orig"]["gq"].set("n/a")
                self.vars["orig"]["gγ"].set("n/a")
            setv(self.vars["cyp"], "gc", gc_c, "(Nc; integrated)")
            setv(self.vars["cyp"], "gq", gq_c, "(Nq; integrated)")
            setv(self.vars["cyp"], "gγ", gg_c, "(Nγ; integrated)")

            # i
            if en_out is not None:
                setv(self.vars["orig"], "ic", en_out["ic"])
                setv(self.vars["orig"], "iq", en_out["iq"])
                setv(self.vars["orig"], "iγ", en_out["iγ"])
            else:
                self.vars["orig"]["ic"].set("n/a")
                self.vars["orig"]["iq"].set("n/a")
                self.vars["orig"]["iγ"].set("n/a")
            setv(self.vars["cyp"],  "ic", ic_c)
            setv(self.vars["cyp"],  "iq", iq_c)
            setv(self.vars["cyp"],  "iγ", ig_c)

            # s
            if en_out is not None:
                setv(self.vars["orig"], "sc", en_out["sc"])
                setv(self.vars["orig"], "sq", en_out["sq"])
                setv(self.vars["orig"], "sγ", en_out["sγ"])
            else:
                self.vars["orig"]["sc"].set("n/a")
                self.vars["orig"]["sq"].set("n/a")
                self.vars["orig"]["sγ"].set("n/a")
            self.vars["cyp"]["sc"].set(f"{sc_c:.4f}")
            self.vars["cyp"]["sq"].set(f"{sq_c:.4f}")
            self.vars["cyp"]["sγ"].set(f"{sg_c:.4f}")

            # w
            if en_out is not None:
                self.vars["orig"]["wc"].set("incl. in γ*")
                self.vars["orig"]["wq"].set("incl. in γ*")
                self.vars["orig"]["wγ"].set("incl. in γ*")
            else:
                self.vars["orig"]["wc"].set("n/a")
                self.vars["orig"]["wq"].set("n/a")
                self.vars["orig"]["wγ"].set("n/a")
            setv(self.vars["cyp"], "wc", wc)
            setv(self.vars["cyp"], "wq", wq)
            setv(self.vars["cyp"], "wγ", wy)

            # ε
            self.vars["orig"]["εc"].set("n/a")
            self.vars["orig"]["εq"].set("n/a")
            self.vars["orig"]["εγ"].set("n/a")
            self.vars["orig"]["k_h,lim"].set("n/a")
            setv(self.vars["cyp"], "εc", ec_c)
            setv(self.vars["cyp"], "εq", eq_c)
            setv(self.vars["cyp"], "εγ", eg_c)
            setv(self.vars["cyp"], "k_h,lim", kh_lim)

            # misc
            for side in ("orig", "cyp"):
                self.vars[side]["δ used (deg)"].set(f"{delta_used:.4f}")
            self.vars["orig"]["DfA/DfP"].set("1.0000" if en_out is not None else "n/a")
            self.vars["cyp"]["DfA/DfP"].set(f"{(DfA / max(DfP, 1e-12)):.4f}")
            self.vars["orig"]["KA used"].set("n/a")
            self.vars["orig"]["KP used"].set("n/a")
            self.vars["cyp"]["KA used"].set(f"{KA_label:.4f}")
            self.vars["cyp"]["KP used"].set(f"{KP_label:.4f}")

            Hstar = H * (cyprus_depth_factors(phi, Beff, Df, psi)[0])
            Hmax_star = Hmax_distance(Beff, phi) * (cyprus_depth_factors(phi, Beff, Df, psi)[0])
            self.vars["orig"]["H* (virtual wall height, depth-adjusted)"].set("n/a")
            self.vars["orig"]["H* max (depth-adjusted)"].set("n/a")
            self.vars["cyp"]["H* (virtual wall height, depth-adjusted)"].set(f"{Hstar:.4f}")
            self.vars["cyp"]["H* max (depth-adjusted)"].set(f"{Hmax_star:.4f}")

            for side in ("orig", "cyp", "mob"):
                self.vars[side]["Soil mode"].set(soil_mode)
                self.vars[side]["c_eq"].set(f"{c_val:.4f}")
                self.vars[side]["φ_eq"].set(f"{phi:.4f}")
                self.vars[side]["γ_eq"].set(f"{gd:.4f}")
                self.vars[side]["Two-layer regime"].set(eq_info.get("regime", "-"))
                self.vars[side]["EN status"].set("-")
            self.vars["orig"]["EN special option"].set("ticked" if self.allow_en_special.get() else "unticked")
            self.vars["cyp"]["EN special option"].set("-")
            self.vars["mob"]["EN special option"].set("-")
            self.vars["orig"]["EN status"].set(en_status)


            # Mobilized shear strength of soil column:
            # back-calculate SMF so that q_ult with {kh,kv} equals q_ult with kh=kv=0.
            params = dict(
                Beff=Beff, Leff=Leff, Df=Df, DfA=DfA, DfP=DfP, Dw=Dw, psi=psi,
                gd=gd, gs=gs, gw=gw, alpha=alpha, beta_en=beta_en, theta=theta,
                source_key=source_key,
                KA_user=KA_label if source_key=="KAKP" else 0.0,
                KP_user=KP_label if source_key=="KAKP" else 0.0,
                betaA=betaA if isinstance(betaA, (int,float)) else 0.0,
                betaP=betaP if isinstance(betaP, (int,float)) else 0.0,
                delta_used=delta_used, res_pf=res_pf,
                use_reinf=use_reinf, n_layers=n_layers, p_tens=p_tens,
                footing_type=footing_type, is_circular=is_circular,
                failure_mode=failure_mode, f_cs=f_cs, lambda3=lambda3
            )

            target_qu = float(f"{qult_c:.3f}")

            def qu_smf(smf):
                c_m = smf * c_val
                phi_m = math.degrees(math.atan(smf * math.tan(math.radians(phi))))
                qu = self._cyprus_qult_with_params(
                    c_m, phi_m, kv_override=0.0, kh_override=0.0, params=params
                )
                return float(f"{qu:.3f}"), c_m, phi_m, qu

            prev_smf = 1.0
            prev_qu_r, prev_cm, prev_phim, prev_qu = qu_smf(prev_smf)
            bracket = None
            if prev_qu_r == target_qu:
                bracket = (1.0, 1.0)
            else:
                smf = 0.9
                while smf >= 0.0:
                    qu_r, cm, phim, qu_val = qu_smf(smf)
                    if qu_r == target_qu:
                        bracket = (smf, smf)
                        prev_smf, prev_qu_r, prev_cm, prev_phim, prev_qu = smf, qu_r, cm, phim, qu_val
                        break
                    if qu_r < target_qu and prev_qu_r > target_qu:
                        bracket = (prev_smf, smf)
                        break
                    prev_smf, prev_qu_r, prev_cm, prev_phim, prev_qu = smf, qu_r, cm, phim, qu_val
                    smf = round(smf - 0.1, 10)

            def refine(lo, hi, step):
                best = None
                smf = hi
                while smf >= lo - 1e-12:
                    qu_r, cm, phim, qu_val = qu_smf(smf)
                    err = abs(qu_r - target_qu)
                    if (best is None) or (err < best[0] - 1e-12) or (abs(err-best[0])<1e-12 and smf>best[1]):
                        best = (err, smf, cm, phim, qu_val, qu_r)
                    if qu_r < target_qu:
                        return best, max(0.0, smf), min(1.0, smf + step)
                    smf = round(smf - step, 10)
                return best, lo, hi

            if bracket is None:
                best = None
                smf = 1.0
                while smf >= -1e-12:
                    qu_r, cm, phim, qu_val = qu_smf(max(0.0, smf))
                    err = abs(qu_r - target_qu)
                    if (best is None) or (err < best[0] - 1e-12) or (abs(err-best[0])<1e-12 and smf>best[1]):
                        best = (err, max(0.0, smf), cm, phim, qu_val, qu_r)
                    smf = round(smf - 0.00001, 10)
                _, smf_best, cm_best, phim_best, qu_best, qu_r_best = best
            else:
                hi, lo = bracket
                best01, lo1, hi1 = refine(min(lo, hi), max(lo, hi), 0.01)
                best001, lo2, hi2 = refine(lo1, hi1, 0.00001)
                _, smf_best, cm_best, phim_best, qu_best, qu_r_best = best001

            qu_full, mob = self._cyprus_qult_with_params(
                cm_best, phim_best, kv_override=0.0, kh_override=0.0, params=params, return_factors=True
            )

            if en_special_case and en_special_allowed:
                # Apply Terzaghi f_cs rule ALSO in EN special mode
                if failure_mode in ("Local shear", "Punching shear"):
                    en_c_special = f_cs * cm_best
                    en_phi_special = math.degrees(
                        math.atan(f_cs * math.tan(math.radians(phim_best)))
                    )
                else:
                    en_c_special = cm_best
                    en_phi_special = phim_best

                en_out = compute_en_results(en_c_special, en_phi_special)
                en_comp_comment = "via c_m,φ_m + f_cs"
                en_status = "via c_m, φ_m (with f_cs)"

            # overwrite EN output fields with the final EN basis (standard, disabled, or via c_m, φ_m)
            for key in ("Nc", "Nq", "Nγ", "bc", "bq", "bγ", "dc", "dq", "dγ", "gc", "gq", "gγ", "ic", "iq", "iγ", "sc", "sq", "sγ"):
                if en_out is None:
                    self.vars["orig"][key].set("n/a")
            if en_out is not None:
                setv(self.vars["orig"], "Nc", en_out["Nc"])
                setv(self.vars["orig"], "Nq", en_out["Nq"])
                setv(self.vars["orig"], "Nγ", en_out["Nγ"])
                setv(self.vars["orig"], "bc", en_out["bc"])
                setv(self.vars["orig"], "bq", en_out["bq"])
                setv(self.vars["orig"], "bγ", en_out["bγ"])
                setv(self.vars["orig"], "dc", en_out["dc"])
                setv(self.vars["orig"], "dq", en_out["dq"])
                setv(self.vars["orig"], "dγ", en_out["dγ"])
                setv(self.vars["orig"], "gc", en_out["gc"])
                setv(self.vars["orig"], "gq", en_out["gq"])
                setv(self.vars["orig"], "gγ", en_out["gγ"])
                setv(self.vars["orig"], "ic", en_out["ic"])
                setv(self.vars["orig"], "iq", en_out["iq"])
                setv(self.vars["orig"], "iγ", en_out["iγ"])
                setv(self.vars["orig"], "sc", en_out["sc"])
                setv(self.vars["orig"], "sq", en_out["sq"])
                setv(self.vars["orig"], "sγ", en_out["sγ"])
                self.vars["orig"]["wc"].set("incl. in γ*")
                self.vars["orig"]["wq"].set("incl. in γ*")
                self.vars["orig"]["wγ"].set("incl. in γ*")
                self.vars["orig"]["Failure mode"].set(failure_mode_short)
                self.vars["orig"]["DfA/DfP"].set("1.0000")
            else:
                self.vars["orig"]["wc"].set("n/a")
                self.vars["orig"]["wq"].set("n/a")
                self.vars["orig"]["wγ"].set("n/a")
                self.vars["orig"]["Failure mode"].set("n/a")
                self.vars["orig"]["DfA/DfP"].set("n/a")
            self.vars["orig"]["cc"].set(en_comp_comment)
            self.vars["orig"]["cq"].set(en_comp_comment)
            self.vars["orig"]["cγ"].set(en_comp_comment)
            self.vars["orig"]["EN status"].set(en_status)

            def setm(key, val):
                try:
                    self.vars["mob"][key].set(f"{float(val):.4f}")
                except Exception:
                    self.vars["mob"][key].set(str(val))

            for key in self.vars["mob"].keys():
                if key in mob:
                    setm(key, mob[key])

            self.vars["mob"]["Failure mode"].set(failure_mode_short)
            self.vars["mob"]["SMF"].set(f"{smf_best:.5f}")
            self.vars["mob"]["c_m (kPa)"].set(f"{cm_best:.3f}")
            self.vars["mob"]["φ_m (deg)"].set(f"{phim_best:.3f}")
            if en_out is not None:
                qult_o = en_out["qult"]
                self.qult_orig.set(f"{qult_o:.3f}")
            else:
                self.qult_orig.set("n/a")
            self.qult_cyp.set(f"{qult_c:.3f}")
            self.qult_mob.set(f"{qult_c:.3f}")

            if is_circular:
                area = math.pi * Beff**2 / 4.0
            else:
                area = Beff * Leff

            RN_cyp = qult_c * area
            RN_mob = qult_c * area
            if en_out is not None:
                RN_orig = qult_o * area
                self.RN_orig.set(f"{RN_orig:.3f}")
            else:
                self.RN_orig.set("n/a")
            self.RN_cyp.set(f"{RN_cyp:.3f}")
            self.RN_mob.set(f"{RN_mob:.3f}")

            if Nn > 0:
                if en_out is not None:
                    self.RNoverN_orig.set(f"{RN_orig / Nn:.3f}")
                else:
                    self.RNoverN_orig.set("n/a")
                self.RNoverN_cyp.set(f"{RN_cyp / Nn:.3f}")
                self.RNoverN_mob.set(f"{RN_mob / Nn:.3f}")
            else:
                self.RNoverN_orig.set("n/a" if en_out is None else "-")
                self.RNoverN_cyp.set("-")
                self.RNoverN_mob.set("-")

        except Exception as e:
            messagebox.showerror("Error", f"Computation failed: {e}")

def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    # Start maximized when possible
    try:
        root.state("zoomed")
    except Exception:
        try:
            root.attributes("-zoomed", True)
        except Exception:
            pass
    App(root)
    root.minsize(900, 600)
    root.mainloop()

if __name__ == "__main__":
    main()