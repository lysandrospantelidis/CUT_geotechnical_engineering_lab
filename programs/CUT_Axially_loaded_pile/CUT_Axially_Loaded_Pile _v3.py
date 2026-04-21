
# Pantelidis Axially Loaded Pile — GUI (v2.9.2)
# ------------------------------------------------------------------
# Includes:
# - Inputs/Outputs UI with k_v (seismic), layers table (editable in-place), factors & loads.
# - Pile data (two rows): Row1 (Pile type + Diameter D), Row2 (Displacement + a-mode + a-const).
# - Add/Delete layer(s) on same line as SRC controls; SRC bounded in [0,1].
# - Run, Visualization, Manual, Export, About buttons (Visualization opens a schematic).
# - K0 chart (Original vs Modified) with x-range controls under chart.
# - q_s(z) chart with x-range controls under chart.
# - Per-slice and Per-layer (factored) tables.
# - Tip resistance input is NON-factored; totals use factored values.
# - H computed internally from layer thicknesses.
# - Displacement piles: K_mod = K_base * OCR^a (+ displacement add-on); for non-displacement, OCR=1 and no add-on.
# - a-mode: constant or sin(phi); enforce a <= 1 (error if > 1). Default a = 1.
# - Report PDF includes all outputs and both charts, with y-axis inverted (z=0 at top) ONLY in the PDF.
# - Labels in report: gammaR shown as γ_R; axial load shown as "Axial pile load, V_k (kN)".
#
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, filedialog
import webbrowser
from PIL import Image, ImageTk
import os
import sys

PROGRAM_NAME = "CUT Axially Loaded Pile (v2.9.2)"

ABOUT_TEXT = """CUT_Axially_Loaded_Pile
Version: v3
Author: Dr Lysandros Pantelidis, Cyprus University of Technology

Educational tool — no warranty. Use at your own risk. Free of charge."""
GAMMA_W = 9.81  # kN/m^3

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller EXE.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def rad(deg):
    return deg * math.pi / 180.0

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def nice_ticks(vmin, vmax, n=6):
    if vmin == vmax:
        vmin -= 1.0
        vmax += 1.0
    span = vmax - vmin
    raw = span / max(1, n)
    if raw == 0:
        inc = 1.0
    else:
        mag = 10 ** math.floor(math.log10(abs(raw)))
        norm = raw / mag
        if norm < 1.5:
            inc = 1.0 * mag
        elif norm < 3:
            inc = 2.0 * mag
        elif norm < 7:
            inc = 5.0 * mag
        else:
            inc = 10.0 * mag
    start = math.floor(vmin / inc) * inc
    end = math.ceil(vmax / inc) * inc
    vals = []
    v = start
    for _ in range(1000):
        if v > end + 1e-9:
            break
        vals.append(v)
        v += inc
    return vals

# ------------------ Mother K0 (Pantelidis) ------------------
def phi_m_deg_fric(phi_deg, ah, kv):
    phi = rad(phi_deg)
    if abs(1.0 - kv) < 1e-12:
        return phi_deg
    tan_theta1 = 0.0 / (1.0 - kv)  # ah=0
    num = 1.0 - (1.0 - math.sin(phi)) * (1.0 + tan_theta1 * math.tan(phi))
    den = 1.0 + (1.0 - math.sin(phi))**2 * (1.0 + tan_theta1 * math.tan(phi))
    x = clamp(num / den if den != 0 else 0.0, -1.0, 1.0)
    return math.degrees(math.asin(x))

def cbrt_complex(z):
    if isinstance(z, complex):
        r = abs(z)
        if r == 0:
            return 0.0
        theta = math.atan2(z.imag, z.real)
        return r**(1.0/3.0) * complex(math.cos(theta/3.0), math.sin(theta/3.0))
    else:
        return z**(1.0/3.0) if z >= 0 else -(-z)**(1.0/3.0)


def _A0_B1_new(phi_deg, c, kv, sigma_v_eff, m, kh=0.0):
    phi = rad(phi_deg)
    s = math.sin(phi)
    t = math.tan(phi)
    if m is None:
        xi = 0.0
        xi2 = -1.0
    else:
        m = float(m)
        xi  = (m - 1.0) / (m + 1.0) - 1.0
        xi2 = 2.0 / m - 1.0
    xi1 = 1.0 + xi
    ratio = (1.0 + s) / max(1e-12, (1.0 - s))
    A0 = (ratio ** xi1) * (1.0 + xi * s + xi2 * (kh / max(1e-12, 1.0 - kv)) * t * (2.0 + xi * (1.0 + s)))
    tan_p = math.tan(math.pi/4.0 + phi / 2.0)
    tan_m = math.tan(math.pi/4.0 - phi / 2.0)
    pow_term = (tan_p / max(1e-12, tan_m)) ** xi1
    B1 = (2.0 * c / (max(1e-12, (1.0 - kv) * sigma_v_eff))) * tan_m * pow_term
    return A0, B1

def _solve_K_general_with_A0B1(z, c, phi_deg, gamma, kv, m, sigma_v_eff):
    phi = rad(phi_deg)
    A0, B1 = _A0_B1_new(phi_deg, c, kv, sigma_v_eff, m, kh=0.0)
    lam = 0 if A0 >= 1.0 else 1
    sgn = 2 * lam - 1
    if abs(c) < 1e-9:
        phim_deg = phi_m_deg_fric(phi_deg, 0.0, kv)
        phim = rad(phim_deg)
        denom = (1.0 + sgn * math.sin(phim))
        return (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0

    tphi = math.tan(phi)
    if abs(B1) < 1e-18:
        phim_deg = phi_m_deg_fric(phi_deg, 0.0, kv)
        phim = rad(phim_deg)
        denom = (1.0 + sgn * math.sin(phim))
        return (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0

    e1 = (1.0 - A0) / B1
    e2 = (1.0 + A0) / (sgn * B1) + 2.0 * c / (max(1e-12, (1.0 - kv) * sigma_v_eff) * sgn * B1 * max(1e-12, tphi))

    a0 = (1.0 + (e2**2) * (tphi**2))
    b0 = (1.0 - (2.0 * sgn * e1 * e2 + e2**2) * (tphi**2))
    c0 = ((e1**2) + 2.0 * sgn * e1 * e2) * (tphi**2)
    d0 = (-(e1**2) * (tphi**2))

    D0 = b0**2 - 3.0 * a0 * c0
    D1 = 2.0 * b0**3 - 9.0 * a0 * b0 * c0 + 27.0 * a0**2 * d0
    inside = D1**2 - 4.0 * (D0**3)
    IMSQRT = math.sqrt(inside) if inside >= 0 else complex(0.0, math.sqrt(-inside))
    D1_sqrt = (D1 - IMSQRT) / 2.0
    C0 = cbrt_complex(D1_sqrt)
    zeta = complex(-0.5, (math.sqrt(3.0))/2.0)
    zeta_lam_C0 = (zeta**lam) * C0 if C0 != 0 else complex(0.0, 0.0)
    two_lam_1_over_3a0 = (-1.0 / (3.0 * sgn * a0)) if abs(a0) > 1e-18 else 0.0
    D0_over = (D0 / zeta_lam_C0) if zeta_lam_C0 != 0 else 0.0
    bo = b0 + zeta_lam_C0 + D0_over
    col = (bo.real * two_lam_1_over_3a0) if isinstance(bo, complex) else (bo * two_lam_1_over_3a0)
    col = clamp(col, -1.0, 1.0)
    phim = math.asin(col)

    cm_mob = c * math.tan(phim) / max(1e-12, tphi)
    denom = (1.0 + sgn * math.sin(phim))
    base = (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0
    corr = sgn * 2.0 * cm_mob * math.tan(math.pi/4.0 - sgn * phim / 2.0) / (max(1e-12, sigma_v_eff) * max(1e-12, (1.0 - kv)))
    return base - corr

def koe_at_rest_pantelidis(z, c, phi_deg, gamma, kv, *, sigma_v_eff=None, m=1.0):
    if sigma_v_eff is None:
        sigma_v_eff = max(1e-8, gamma * max(z, 0.0))
    return _solve_K_general_with_A0B1(z, c, phi_deg, gamma, kv, m, sigma_v_eff)


    sigma_v_eff = max(1e-8, gamma * max(z, 0.0))

    xiA = -1.0
    A0_A = A_Rankine * (1.0 - xiA * math.sin(phi) + ah_av * math.tan(phi) * (2.0 + xiA * Jaky))
    lam = 1 if A0_A < 1.0 else 0
    sgn = 2 * lam - 1

    if abs(c) < 1e-9:
        phim_deg = phi_m_deg_fric(phi_deg, 0.0, kv)
        phim = rad(phim_deg)
        denom = (1.0 + sgn * math.sin(phim))
        if abs(denom) < 1e-12:
            return 0.0
        return (1.0 - sgn * math.sin(phim)) / denom

    cm = c
    B1_A = (sgn * 2.0 * cm / ((1.0 - kv) * sigma_v_eff)) * math.tan(math.pi/4.0 - phi/2.0)
    if abs(B1_A) < 1e-18:
        phim_deg = phi_m_deg_fric(phi_deg, 0.0, kv)
        phim = rad(phim_deg)
        denom = (1.0 + sgn * math.sin(phim))
        if abs(denom) < 1e-12:
            return 0.0
        return (1.0 - sgn * math.sin(phim)) / denom

    e1 = (1.0 - A0_A) / B1_A
    e2 = (1.0 + A0_A) / (sgn * B1_A) + 2.0 * cm / ((1.0 - kv) * sigma_v_eff * sgn * B1_A * math.tan(phi))
    tphi = math.tan(phi)
    a0 = (1.0 + (e2**2) * (tphi**2))
    b0 = (1.0 - (2.0 * sgn * e1 * e2 + e2**2) * (tphi**2))
    c0 = (e1**2 + 2.0 * sgn * e1 * e2) * (tphi**2)
    d0 = (-(e1**2) * (tphi**2))

    D0 = b0**2 - 3.0 * a0 * c0
    D1 = 2.0 * b0**3 - 9.0 * a0 * b0 * c0 + 27.0 * a0**2 * d0
    inside = D1**2 - 4.0 * (D0**3)
    IMSQRT = math.sqrt(inside) if inside >= 0 else complex(0.0, math.sqrt(-inside))
    D1_sqrt = (D1 - IMSQRT) / 2.0
    C0 = cbrt_complex(D1_sqrt)
    zeta = complex(-0.5, (math.sqrt(3.0))/2.0)
    zeta_lam_C0 = (zeta**lam) * C0 if C0 != 0 else complex(0.0, 0.0)
    two_lam_1_over_3a0 = (-1.0 / (3.0 * sgn * a0)) if abs(a0) > 1e-18 else 0.0
    D0_over = (D0 / zeta_lam_C0) if zeta_lam_C0 != 0 else 0.0
    bo = b0 + zeta_lam_C0 + D0_over
    col = (bo.real * two_lam_1_over_3a0) if isinstance(bo, complex) else (bo * two_lam_1_over_3a0)
    col = clamp(col, -1.0, 1.0)
    phim = math.asin(col)
    cm_mob = cm * math.tan(phim) / tphi if abs(tphi) > 1e-12 else cm
    denom = (1.0 + sgn * math.sin(phim))
    base = (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0
    corr = sgn * 2.0 * cm_mob * math.tan(math.pi/4.0 - sgn * phim / 2.0) / (sigma_v_eff * (1.0 - kv))
    K = base - corr
    return K

def sigma_v_eff_at_depth(z, layers, gw_depth):
    if z <= 0:
        return 0.0
    sv = 0.0
    depth_left = z
    z_cursor = 0.0
    for L in layers:
        h = L['h']
        dz = min(h, max(0.0, z - z_cursor))
        if dz <= 0:
            break
        top = z_cursor
        bot = z_cursor + dz
        above = max(0.0, min(bot, gw_depth) - top)
        below = dz - above
        sv += L.get('γ', L.get('gamma', 19.0)) * above
        sv += max(0.0, L.get('γ', L.get('gamma', 19.0)) - GAMMA_W) * below
        z_cursor += dz
        depth_left -= dz
        if depth_left <= 1e-9:
            break
    return sv


def koe_displacement(z, H, L, gw_depth, kv, displacement_m, OCR, a_value, sigma_eff_z):
    # base K must use the same σ′v(z) as K0
    K_base = max(0.0, koe_at_rest_pantelidis(
        z, L['c'], L['φ'], L.get('γ', L.get('gamma', 19.0)), kv,
        sigma_v_eff=sigma_eff_z, m=1.0
    ))

    z_over_H = max(1e-9, z / max(H, 1e-9))
    E = max(1e-9, L.get('E', 1e6))
    nu = clamp(L.get('ν', 0.3), -0.49, 0.49)

    bracket = (math.pi/4.0) * ((1.0 - nu**2) / E) * (((1.0 + z_over_H)**3) * (1.0 - z_over_H) / z_over_H) \
              * H * (1.0 - kv) * max(1e-9, sigma_eff_z)

    addon = displacement_m * (1.0 / bracket) if bracket > 0 else 0.0
    return max(0.0, K_base * (OCR ** a_value) + addon)



def compute_shaft_resistance(params, layers):
    D = params['D']
    kv = params['kv']
    N = params['N']
    pile_type = params['pile_type']
    displacement_m = params['displacement_m']
    gw_depth = params['gw_depth']
    gammaR = params['γ_R']
    axial_load = params['axial_load']
    a_mode = params['a_mode']
    a_const = params['a_const']
    Rt_unfact = params['Rt_unfact']

    H = sum(L['h'] for L in layers)
    R = D / 2.0
    perim = math.pi * D
    Abase = math.pi * R * R

    # Build layer bounds
    bounds = []
    z = 0.0
    for idx, L in enumerate(layers):
        bounds.append({'z0': z, 'z1': z + L['h'], 'L': L, 'idx': idx})
        z += L['h']

    def layer_at(zz):
        for b in bounds:
            if b['z0'] - 1e-9 <= zz <= b['z1'] + 1e-9:
                return b
        return bounds[-1]

    N = max(20, int(N))
    dz = H / N if H > 0 else 0.0
    Rs = 0.0
    details = []
    ko_curve_base = []
    ko_curve_mod = []
    kp_curve = []
    layer_kPa = [0.0 for _ in layers]
    layer_kN = [0.0 for _ in layers]

    for i in range(N):
        z_top = i * dz
        z_bot = (i + 1) * dz
        z_mid = 0.5 * (z_top + z_bot)

        b = layer_at(z_mid)
        L = b['L']; idx = b['idx']

        sigma_eff_z = sigma_v_eff_at_depth(z_mid, layers, gw_depth)

        # K0 and Kp
        K0 = max(0.0, koe_at_rest_pantelidis(
            z_mid, L['c'], L['φ'], L.get('γ', L.get('gamma', 19.0)), kv,
            sigma_v_eff=sigma_eff_z, m=1.0
        ))
        Kp_cap = max(0.0, koe_at_rest_pantelidis(
            z_mid, L['c'], L['φ'], L.get('γ', L.get('gamma', 19.0)), kv,
            sigma_v_eff=sigma_eff_z, m=None
        ))
        # enforce K0 ≤ Kp
        K0 = min(K0, Kp_cap)

        # Modified K for displacement piles only when OCR>1 or displacement>0
        a_OCR = float(L.get('a_OCR', 1.0))
        b_OCR = float(L.get('b_OCR', 1.0))
        c_OCR = float(L.get('c_OCR', 1.0)) if 'c_OCR' in L else 0.0
        z_eff = max(1e-6, z_mid)
        OCR = a_OCR * ((z_eff) ** (-b_OCR)) + c_OCR
        OCR = max(1.0, OCR)
        cap = params.get('OCR_cap', None)

        if cap is not None and cap > 0:
            OCR = min(OCR, cap)
        if pile_type == "Displacement" and (OCR > 1.0 + 1e-12 or displacement_m > 1e-12):
            a_val = (math.sin(rad(L['φ'])) if a_mode == 'sinφ' else a_const)
            K_mod = koe_displacement(z_mid, H, L, gw_depth, kv, displacement_m, OCR, a_val, sigma_eff_z)
        else:
            K_mod = K0

        # Final cap
        K_used = min(max(0.0, K_mod), Kp_cap)

        # store curves
        ko_curve_base.append({'z': z_mid, 'K': K0})
        ko_curve_mod.append({'z': z_mid, 'K': K_used})
        kp_curve.append({'z': z_mid, 'K': Kp_cap})

        sigma_eff = sigma_eff_z
        alpha_c = min(1.0, max(0.0, L.get('α_c', 1.0)))
        alpha_t = min(1.0, max(0.0, L.get('α_tanφ', 1.0)))
        q_local = (alpha_c * L['c']) + K_used * (1.0 - kv) * sigma_eff * (alpha_t * math.tan(rad(L['φ'])))
        dQ = perim * (z_bot - z_top) * q_local

        Rs += dQ
        layer_kPa[idx] += q_local * (z_bot - z_top)
        layer_kN[idx] += dQ
        details.append({'z_mid': z_mid, 'K': K_used, 'q_local': q_local, 'dQ': dQ})

    # Shaft and base
    Rs_fact = Rs / gammaR
    qs_fact = (Rs / max(1e-12, H)) / gammaR  # average factored unit shaft resistance
    Nq = 0.0  # unchanged here (your base calc is elsewhere if needed)
    qb = 0.0
    Rs_fact = Rs / max(1e-12, gammaR)
    Rt_fact = Rt_unfact / max(1e-12, gammaR)
    R_total_fact = Rs_fact + Rt_fact

    safety_shaft = (Rs_fact / max(1e-12, axial_load)) if axial_load > 0 else float('inf')
    safety_total = (R_total_fact / max(1e-12, axial_load)) if axial_load > 0 else float('inf') if axial_load > 0 else float('inf')

    per_layer_results = []
    for i, L in enumerate(layers):
        h = L['h']
        avg_q_kPa = layer_kPa[i] / max(1e-12, h) if h > 0 else 0.0
        q_kPa_fact = avg_q_kPa / max(1e-12, gammaR)
        Q_kN_fact = layer_kN[i] / max(1e-12, gammaR)
        ratio = (layer_kN[i] / max(1e-12, Rs)) if Rs > 0 else 0.0
        per_layer_results.append({
            'idx': i + 1,
            'h': h,
            'q_kPa_fact': q_kPa_fact,
            'Q_kN_fact': Q_kN_fact,
            'ratio': ratio,
        })

    return H, Rs_fact, qs_fact, per_layer_results, safety_shaft, Rt_fact, \
        R_total_fact, safety_total, details, ko_curve_base, ko_curve_mod, kp_curve

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(PROGRAM_NAME)
        try:
            self.state('zoomed')
        except Exception:
            self.geometry("1400x900")

        # === Variables ===
        self.var_kv = tk.DoubleVar(value=0.0)
        self.var_N = tk.IntVar(value=400)
        self.var_gw = tk.DoubleVar(value=2.0)

        self.var_pile_type = tk.StringVar(value="Non-displacement")
        self.var_D = tk.DoubleVar(value=1.0)
        self.var_displacement = tk.DoubleVar(value=0.0)
        self.var_a_mode = tk.StringVar(value="constant")
        self.var_a_const = tk.DoubleVar(value=0.5)

        self.var_gammaR = tk.DoubleVar(value=1.0)
        self.var_axial_load = tk.DoubleVar(value=1000.0)
        self.var_Rt_unfact = tk.DoubleVar(value=0.0)

        # q(z) chart x-range
        self.var_qxmin = tk.StringVar(value="")
        self.var_qxmax = tk.StringVar(value="")

        # K0 chart x-range
        self.var_kxmin = tk.StringVar(value="")
        self.var_kxmax = tk.StringVar(value="")

        # Legend offsets for K chart
        self.var_k_legend_x = tk.StringVar(value="10")
        self.var_k_legend_y = tk.StringVar(value="10")

        # Legend offsets for OCR chart
        self.var_ocr_legend_x = tk.StringVar(value="10")
        self.var_ocr_legend_y = tk.StringVar(value="10")

        # Legend offsets for pile visualization
        self.var_viz_legend_x = tk.StringVar(value="10")
        self.var_viz_legend_y = tk.StringVar(value="10")

        self.var_apply_src_all = tk.BooleanVar(value=False)
        self.var_alpha_c_all = tk.DoubleVar(value=1.0)
        self.var_alpha_tanphi_all = tk.DoubleVar(value=1.0)

        # default layer
        self.layers = [{
            'h': 12.0, 'c': 20.0, 'φ': 30.0, 'γ': 19.0,
            'a_OCR': 1.0, 'b_OCR':  1.0, 'c_OCR': 1.0,
            'α_c': 1.0, 'α_tanφ': 1.0, 'E': 30000.0, 'ν': 0.3
        }]

        # layout: use a horizontal PanedWindow so the divider between
        # inputs (left) and outputs (right) can be adjusted with the mouse.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew")

        left_container = ttk.Frame(paned)
        right_container = ttk.Frame(paned)
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)
        right_container.columnconfigure(0, weight=1)
        right_container.rowconfigure(0, weight=1)

        paned.add(left_container, weight=1)
        paned.add(right_container, weight=2)

        # Pre-create OCR axis/cap variables BEFORE UI that uses them
        self._ocr_xmin_var = tk.StringVar(value="")
        self._ocr_xmax_var = tk.StringVar(value="10")
        self._ocr_cap_var = tk.StringVar(value="")

        # Logo for RUN button
        self.logo_source_img = None
        try:
            logo_path = resource_path("cut_logo.png")
            if os.path.exists(logo_path):
                self.logo_source_img = Image.open(logo_path)
        except Exception:
            self.logo_source_img = None


        self._build_left(left_container)
        self._build_right(right_container)
        try:
            self._draw_visualization(self.canvas_viz)
        except Exception:
            pass
        self._run()


    # ------------------ UI: Left (Inputs) ------------------
    def _build_left(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(11, weight=1)

        ttk.Label(frm, text="Inputs", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # General
        sec_gen = ttk.LabelFrame(frm, text="General")
        sec_gen.grid(row=1, column=0, sticky="ew", pady=6)
        for i in range(3):
            sec_gen.columnconfigure(i, weight=1)
        self._add_entry(sec_gen, "k_v (seismic)", self.var_kv, 0, 0)
        self._add_entry(sec_gen, "Discetization", self.var_N, 0, 1)
        self._add_entry(sec_gen, "Groundwater table (GWT) depth  (m)", self.var_gw, 0, 2)

        # Pile data (two rows)
        sec_pile = ttk.LabelFrame(frm, text="Pile data")
        sec_pile.grid(row=2, column=0, sticky="ew", pady=6)
        for i in range(4):
            sec_pile.columnconfigure(i, weight=1)

        row1 = ttk.Frame(sec_pile)
        row1.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(row1, text="Pile type").pack(side="left")
        ttk.Combobox(row1, textvariable=self.var_pile_type, values=["Non-displacement", "Displacement"], state="readonly", width=18).pack(side="left", padx=6)
        ttk.Label(row1, text="Diameter D (m)").pack(side="left", padx=(12, 4))
        ttk.Entry(row1, textvariable=self.var_D, width=12).pack(side="left")

        row2 = ttk.Frame(sec_pile)
        row2.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(row2, text="Displacement (m) (e.g. D/2 for solid pile)").pack(side="left")
        ttk.Entry(row2, textvariable=self.var_displacement, width=12).pack(side="left", padx=(6, 12))        # a-mode / a-const / OCR cap on their own row
        row2b = ttk.Frame(sec_pile)
        row2b.grid(row=3, column=0, columnspan=10, sticky="ew", pady=(2, 2))
        ttk.Label(row2b, text="a mode (OCR^a)").pack(side="left")
        ttk.Combobox(row2b, textvariable=self.var_a_mode, values=["constant", "sinφ"], state="readonly", width=10).pack(side="left", padx=6)
        ttk.Label(row2b, text="a (constant)").pack(side="left", padx=(12, 4))
        ttk.Entry(row2b, textvariable=self.var_a_const, width=12).pack(side="left")
        ttk.Label(row2b, text="OCR cap").pack(side="left", padx=(12, 4))
        ttk.Entry(row2b, textvariable=self._ocr_cap_var, width=12).pack(side="left")

        # Factors & Loads
        sec_fact = ttk.LabelFrame(frm, text="Factors & Loads")
        sec_fact.grid(row=3, column=0, sticky="ew", pady=6)
        for i in range(3):
            sec_fact.columnconfigure(i, weight=1)
        self._add_entry(sec_fact, "Resistance factor γ_R", self.var_gammaR, 0, 0)
        self._add_entry(sec_fact, "Axial pile load, V_k or V_d (kN)", self.var_axial_load, 0, 1)
        self._add_entry(sec_fact, "Tip resistance Rt (kN) NON-factored", self.var_Rt_unfact, 0, 2)

        note = ttk.Label(frm, text="Note: If a resistance factor is used, the axial load should also be the factored value (V_d).", foreground="#444")
        note.grid(row=5, column=0, sticky="w", pady=(4, 8))

        ttk.Separator(frm).grid(row=6, column=0, sticky="ew", pady=(4, 4))

        # Layers
        hdr = ttk.Frame(frm)
        hdr.grid(row=7, column=0, sticky="ew", pady=(6, 2))
        ttk.Label(hdr, text="Layers (top to bottom) — H is auto = sum(h)", font=("Segoe UI", 12, "bold")).pack(side="left")

        hdr2 = ttk.Frame(frm)
        hdr2.grid(row=8, column=0, sticky="ew", pady=(0, 4))
        ttk.Checkbutton(hdr2, text="Apply the same interface reduction factor to all layers", variable=self.var_apply_src_all).pack(side="left")
        ttk.Label(hdr2, text="α_c").pack(side="left", padx=(8, 4))
        ttk.Entry(hdr2, textvariable=self.var_alpha_c_all, width=8).pack(side="left")
        ttk.Label(hdr2, text="α_tanφ").pack(side="left", padx=(8, 4))
        ttk.Entry(hdr2, textvariable=self.var_alpha_tanphi_all, width=8).pack(side="left")
        ttk.Button(hdr2, text="Delete selected layer(s)", command=self._delete_selected).pack(side="right", padx=(8, 0))
        ttk.Button(hdr2, text="Add layer", command=self._add_layer).pack(side="right")

        # Custom Treeview style to give extra height for two-line headers
        style = ttk.Style()
        style.configure("Layers.Treeview.Heading", padding=(4, 14))
        style.configure("Layers.Treeview", rowheight=22)

        cols = ("z", "h", "c", "φ", "γ", "a_OCR", "b_OCR", "c_OCR", "α_c", "α_tanφ", "E", "ν")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=12, style="Layers.Treeview")
        self.tree.tag_configure("units", foreground="#555555")
        self.tree.grid(row=9, column=0, sticky="nsew")
        frm.rowconfigure(9, weight=1)
        # Two-line headers: first row = symbol, second row = units
        headers = [
            ("#", 40),
            ("h", 55),
            ("c", 65),
            ("φ", 60),
            ("γ or γsat", 90),
            ("a_OCR", 60),
            ("b_OCR", 60),
            ("c_OCR", 60),
            ("α_c", 50),
            ("α_tanφ", 65),
            ("E", 80),
            ("ν", 45),
        ]
        for key, (title, w) in zip(cols, headers):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=w, anchor="center")
        vs = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set, selectmode="extended")
        vs.grid(row=9, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._start_edit_cell)

        # Bottom control row
        bar = ttk.Frame(frm)
        bar.grid(row=10, column=0, sticky="ew", pady=(8, 0))

        for i in range(6):
            bar.columnconfigure(i, weight=1)

        # HOME button (CUT Apps)
        try:
            home_path = resource_path("home.png")
            if os.path.exists(home_path):
                img_home_src = Image.open(home_path)
                HOME_SIZE = 80
                self.img_home = ImageTk.PhotoImage(
                    img_home_src.resize((HOME_SIZE, HOME_SIZE), Image.LANCZOS)
                )

                home_frame = tk.Frame(
                    bar,
                    bd=3,
                    relief="raised",
                    bg="#d9d9d9",
                    highlightthickness=0
                )
                home_frame.grid(row=0, column=0, padx=4, pady=2)

                btn_home = tk.Button(
                    home_frame,
                    image=self.img_home,
                    command=lambda: webbrowser.open("https://cut-apps.streamlit.app/"),
                    bd=0,
                    highlightthickness=0,
                    cursor="hand2",
                    width=HOME_SIZE,
                    height=HOME_SIZE,
                    bg="#ffffff"
                )
                btn_home.pack(padx=2, pady=2)
            else:
                ttk.Button(
                    bar,
                    text="Home",
                    command=lambda: webbrowser.open("https://cut-apps.streamlit.app/")
                ).grid(row=0, column=0, sticky="ew", padx=2)
        except Exception:
            ttk.Button(
                bar,
                text="Home",
                command=lambda: webbrowser.open("https://cut-apps.streamlit.app/")
            ).grid(row=0, column=0, sticky="ew", padx=2)

        # RUN button with same frame style as Bearing Capacity program
        if self.logo_source_img is not None:
            LOGO_SIZE = 80  # adjust size if needed

            # Prepare logo image
            self.img_run = ImageTk.PhotoImage(
                self.logo_source_img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
            )

            # Frame that imitates the BEARING CAPACITY style
            run_frame = tk.Frame(
                bar,
                bd=3,                 # THICK border (like your bearing capacity program)
                relief="raised",      # raised bevel effect
                bg="#d9d9d9",         # typical ttk button background on Windows
                highlightthickness=0
            )
            run_frame.grid(row=0, column=1, padx=4, pady=2)

            # Button inside the frame
            self.btn_run = tk.Button(
                run_frame,
                image=self.img_run,
                command=self._run,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                width=LOGO_SIZE,
                height=LOGO_SIZE,
                bg="#ffffff"
            )
            self.btn_run.pack(padx=2, pady=2)
        else:
            self.btn_run = ttk.Button(bar, text="Run", command=self._run)
            self.btn_run.grid(row=0, column=1, sticky="ew", padx=2)


        ttk.Button(bar, text="Theory and user manual", command=self._open_manual).grid(row=0, column=2, sticky="ew", padx=2)
        ttk.Button(bar, text="Export Report (PDF)", command=self._export_pdf).grid(row=0, column=3, sticky="ew", padx=2)
        ttk.Button(bar, text="Export Slices (Excel)", command=self._export_slices_excel).grid(row=0, column=4, sticky="ew", padx=2)
        ttk.Button(bar, text="About", command=self._show_about).grid(row=0, column=5, sticky="ew", padx=2)

        self._refresh_tree()

    def _show_about(self):
        messagebox.showinfo("About", ABOUT_TEXT)

    # ------------------ UI: Right (Outputs) ------------------
    
    def _build_right(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)

        # Outer notebook: Visualization / Outputs
        outer = ttk.Notebook(frm)
        outer.grid(row=0, column=0, sticky="nsew")

        # === Visualization tab ===
        tab_viz = ttk.Frame(outer)
        outer.add(tab_viz, text="Visualization - Pile")

        self.canvas_viz = tk.Canvas(tab_viz, height=520, bg="white")
        self.canvas_viz.pack(fill="both", expand=True)
        self.canvas_viz.bind("<Configure>", lambda e: self._draw_visualization(self.canvas_viz))

        # Legend offset controls for pile visualization
        viz_leg_controls = ttk.Frame(tab_viz)
        viz_leg_controls.pack(fill="x", pady=4)
        ttk.Label(viz_leg_controls, text="Legend offset x").pack(side="left", padx=(4, 4))
        ent_vx = ttk.Entry(viz_leg_controls, textvariable=self.var_viz_legend_x, width=10)
        ent_vx.pack(side="left")
        ttk.Label(viz_leg_controls, text="Legend offset y").pack(side="left", padx=(12, 4))
        ent_vy = ttk.Entry(viz_leg_controls, textvariable=self.var_viz_legend_y, width=10)
        ent_vy.pack(side="left")
        ttk.Button(viz_leg_controls, text="Apply",
                   command=lambda: self._draw_visualization(self.canvas_viz)
                   ).pack(side="left", padx=(12, 0))
        ent_vx.bind("<Return>", lambda e: self._draw_visualization(self.canvas_viz))
        ent_vy.bind("<Return>", lambda e: self._draw_visualization(self.canvas_viz))

        # Second visualization tab: OCR vs depth
        tab_viz_ocr = ttk.Frame(outer)
        outer.add(tab_viz_ocr, text="Visualization - OCR vs depth")
        self.canvas_ocr = tk.Canvas(tab_viz_ocr, height=520, bg="white")
        self.canvas_ocr.pack(fill="both", expand=True)
        
        # OCR axis limit controls (like other charts)
        frm_ocr_limits = ttk.Frame(tab_viz_ocr)
        frm_ocr_limits.pack(fill="x", pady=4)
        ttk.Label(frm_ocr_limits, text="OCR x-min").grid(row=0, column=0, padx=4, sticky="w")
        ttk.Entry(frm_ocr_limits, textvariable=self._ocr_xmin_var, width=10).grid(row=0, column=1, padx=2)
        ttk.Label(frm_ocr_limits, text="OCR x-max").grid(row=0, column=2, padx=8, sticky="w")
        ttk.Entry(frm_ocr_limits, textvariable=self._ocr_xmax_var, width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frm_ocr_limits, text="Apply", command=self._draw_ocr_chart).grid(row=0, column=4, padx=8)
        self.canvas_ocr.bind("<Configure>", lambda e: self._draw_ocr_chart())

        # Legend offset controls for OCR chart
        frm_ocr_leg = ttk.Frame(tab_viz_ocr)
        frm_ocr_leg.pack(fill="x", pady=(0, 4))
        ttk.Label(frm_ocr_leg, text="Legend offset x").grid(row=0, column=0, padx=4, sticky="w")
        ttk.Entry(frm_ocr_leg, textvariable=self.var_ocr_legend_x, width=10).grid(row=0, column=1, padx=2)
        ttk.Label(frm_ocr_leg, text="Legend offset y").grid(row=0, column=2, padx=8, sticky="w")
        ttk.Entry(frm_ocr_leg, textvariable=self.var_ocr_legend_y, width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frm_ocr_leg, text="Apply", command=self._draw_ocr_chart).grid(row=0, column=4, padx=8)

        # === Outputs tab ===
        tab_out = ttk.Frame(outer)
        outer.add(tab_out, text="Outputs")
        tab_out.columnconfigure(0, weight=1)
        tab_out.rowconfigure(3, weight=1)

        ttk.Label(tab_out, text="Outputs", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Two rows summary
        row1 = ttk.Frame(tab_out)
        row1.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        for i in range(3):
            row1.columnconfigure(i, weight=1)
        row2 = ttk.Frame(tab_out)
        row2.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for i in range(3):
            row2.columnconfigure(i, weight=1)

        self.var_Rs = getattr(self, "var_Rs", tk.StringVar(value="0.0 kN"))
        self.var_qs = getattr(self, "var_qs", tk.StringVar(value="0.0 kPa"))
        self.var_safety_shaft = getattr(self, "var_safety_shaft", tk.StringVar(value="--"))
        self.var_Rt = getattr(self, "var_Rt", tk.StringVar(value="0.0 kN"))
        self.var_Rtot = getattr(self, "var_Rtot", tk.StringVar(value="0.0 kN"))
        self.var_safety_total = getattr(self, "var_safety_total", tk.StringVar(value="--"))

        self._metric(row1, "Shaft resistance (factored), Rs", self.var_Rs, 0, 0)
        self._metric(row1, "Average unit shaft (factored), qs_tot", self.var_qs, 0, 1)
        self._metric(row1, "Safety (shaft only)", self.var_safety_shaft, 0, 2)

        self._metric(row2, "Tip resistance (factored), Rt", self.var_Rt, 0, 0)
        self._metric(row2, "Total pile resistance (factored), Rtot", self.var_Rtot, 0, 1)
        self._metric(row2, "Safety (total)", self.var_safety_total, 0, 2)

        # Inner tabs for charts/tables
        nb = ttk.Notebook(tab_out)
        nb.grid(row=3, column=0, sticky="nsew")

        # q(z) first tab
        tab_q = ttk.Frame(nb)
        nb.add(tab_q, text="Shaft resistance vs depth")
        self.canvas_q = getattr(self, "canvas_q", tk.Canvas(tab_q, height=360, bg="white"))
        self.canvas_q.pack(fill="both", expand=True)
        self.canvas_q.bind("<Configure>", lambda e: self._draw_qchart())
        q_controls = ttk.Frame(tab_q)
        q_controls.pack(fill="x", pady=(6, 0))
        ttk.Label(q_controls, text="q_s x-axis min (blank=auto)").pack(side="left", padx=(4, 4))
        ent_qmin = ttk.Entry(q_controls, textvariable=self.var_qxmin, width=10)
        ent_qmin.pack(side="left")
        ttk.Label(q_controls, text="q_s x-axis max (blank=auto)").pack(side="left", padx=(12, 4))
        ent_qmax = ttk.Entry(q_controls, textvariable=self.var_qxmax, width=10)
        ent_qmax.pack(side="left")
        ttk.Button(q_controls, text="Apply", command=lambda: self._draw_qchart()).pack(side="left", padx=(12, 0))
        ent_qmin.bind("<Return>", lambda e: self._draw_qchart())
        ent_qmax.bind("<Return>", lambda e: self._draw_qchart())

        # K0 chart
        tab_chart = ttk.Frame(nb)
        nb.add(tab_chart, text="K vs depth")
        self.canvas = getattr(self, "canvas", tk.Canvas(tab_chart, height=360, bg="white"))
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_chart())
        chart_controls = ttk.Frame(tab_chart)
        chart_controls.pack(fill="x", pady=(6, 0))
        ttk.Label(chart_controls, text="K0 x-axis min (blank=auto)").pack(side="left", padx=(4, 4))
        ent_min = ttk.Entry(chart_controls, textvariable=self.var_kxmin, width=10)
        ent_min.pack(side="left")
        ttk.Label(chart_controls, text="K0 x-axis max (blank=auto)").pack(side="left", padx=(12, 4))
        ent_max = ttk.Entry(chart_controls, textvariable=self.var_kxmax, width=10)
        ent_max.pack(side="left")
        ttk.Button(chart_controls, text="Apply", command=lambda: self._draw_chart()).pack(side="left", padx=(12, 0))
        ent_min.bind("<Return>", lambda e: self._draw_chart())
        ent_max.bind("<Return>", lambda e: self._draw_chart())

        # Legend offset controls for K chart
        legend_controls = ttk.Frame(tab_chart)
        legend_controls.pack(fill="x", pady=(2, 0))
        ttk.Label(legend_controls, text="Legend offset x").pack(side="left", padx=(4, 4))
        ent_klegx = ttk.Entry(legend_controls, textvariable=self.var_k_legend_x, width=10)
        ent_klegx.pack(side="left")
        ttk.Label(legend_controls, text="Legend offset y").pack(side="left", padx=(12, 4))
        ent_klegy = ttk.Entry(legend_controls, textvariable=self.var_k_legend_y, width=10)
        ent_klegy.pack(side="left")
        ttk.Button(legend_controls, text="Apply",
                   command=lambda: self._draw_chart()).pack(side="left", padx=(12, 0))
        ent_klegx.bind("<Return>", lambda e: self._draw_chart())
        ent_klegy.bind("<Return>", lambda e: self._draw_chart())

        # Slices
        tab_slices = ttk.Frame(nb)
        nb.add(tab_slices, text="Slices (point-level)")
        cols = ("z", "K", "Kp", "q_local", "dQ")
        self.tbl_slices = getattr(self, "tbl_slices", ttk.Treeview(tab_slices, columns=cols, show="headings", height=16))
        for col, txt, w in zip(cols, ["z_mid (m)", "K", "Kp", "q_local (kPa)", "dQ (kN)"], [100, 80, 80, 140, 120]):
            self.tbl_slices.heading(col, text=txt)
            self.tbl_slices.column(col, width=w, anchor="center")
        vs2 = ttk.Scrollbar(tab_slices, orient="vertical", command=self.tbl_slices.yview)
        self.tbl_slices.configure(yscrollcommand=vs2.set)
        self.tbl_slices.pack(side="left", fill="both", expand=True)
        vs2.pack(side="right", fill="y")

        # Per-layer
        tab_layers = ttk.Frame(nb)
        nb.add(tab_layers, text="Per-layer (factored)")
        cols2 = ("idx", "h", "qkpa", "Qkn", "ratio")
        self.tbl_layers = getattr(self, "tbl_layers", ttk.Treeview(tab_layers, columns=cols2, show="headings", height=16))
        for col, txt, w in zip(cols2, ["Layer #", "h (m)", "Shaft res. (kPa) - factored", "Shaft res. (kN) - factored", "Q_layer / V_d"], [80, 120, 220, 220, 160]):
            self.tbl_layers.heading(col, text=txt)
            self.tbl_layers.column(col, width=w, anchor="center")
        vs3 = ttk.Scrollbar(tab_layers, orient="vertical", command=self.tbl_layers.yview)
        self.tbl_layers.configure(yscrollcommand=vs3.set)
        self.tbl_layers.pack(side="left", fill="both", expand=True)
        vs3.pack(side="right", fill="y")
    def _add_entry(self, parent, label, var, r, c):
        f = ttk.Frame(parent, padding=(0, 4))
        f.grid(row=r, column=c, sticky="ew", padx=4, pady=2)
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text=label).grid(row=0, column=0, sticky="w")
        ent = ttk.Entry(f, textvariable=var, width=16)
        ent.grid(row=0, column=1, sticky="ew")
        ent.bind("<Return>", lambda e: self._run())
        return ent

    def _metric(self, parent, title, var, r, c):
        f = ttk.Frame(parent, padding=8, relief="groove")
        f.grid(row=r, column=c, sticky="ew", padx=4)
        ttk.Label(f, text=title).grid(row=0, column=0, sticky="w")
        ttk.Label(f, textvariable=var, font=("Segoe UI", 13, "bold")).grid(row=1, column=0, sticky="w")

    def _refresh_tree(self):
        # clear and reinsert units row + all layers
        for i in self.tree.get_children():
            self.tree.delete(i)
        # units row (non-editable, non-deletable)
        units_vals = (
            "",
            "(m)",
            "(kPa)",
            "(deg)",
            "(kN/m³)",
            "(-)",
            "(-)",
            "(-)",
            "(-)",
            "(-)",
            "(kPa)",
            "(-)",
        )
        self.tree.insert("", "end", iid="__units__", values=units_vals, tags=("units",))
        # actual data rows
        for k, L in enumerate(self.layers, start=1):
            vals = (
                k,
                f"{L['h']}",
                f"{L['c']}",
                f"{L['φ']}",
                f"{L.get('γ', L.get('gamma', 19.0))}",
                f"{L.get('a_OCR', 1.0)}",
                f"{L.get('b_OCR', 1.0)}",
                f"{L.get('c_OCR', 1.0)}",
                f"{L.get('α_c', 1.0)}",
                f"{L.get('α_tanφ', 1.0)}",
                f"{L.get('E', 30000.0)}",
                f"{L.get('ν', 0.3)}",
            )
            self.tree.insert("", "end", values=vals)

    def _add_layer(self):
        self.layers.append({'h': 1.0, 'c': 0.0, 'φ': 30.0, 'γ': 19.0,
                            'a_OCR': 1.0, 'b_OCR': 1.0, 'c_OCR': 1.0,
                            'α_c': 1.0, 'α_tanφ': 1.0, 'E': 30000.0, 'ν': 0.3})
        self._refresh_tree()

    def _delete_selected(self):
        sel = list(self.tree.selection())
        idxs = sorted([self.tree.index(i) for i in sel], reverse=True)
        for i in idxs:
            if i == 0:
                # skip units row
                continue
            li = i - 1
            if 0 <= li < len(self.layers):
                del self.layers[li]
        if not self.layers:
            self._add_layer()
        self._refresh_tree()

    def _start_edit_cell(self, event):
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or column == "#0":
            return
        # do not allow editing of the units row
        if item == "__units__":
            return
        col_index = int(column[1:]) - 1
        if col_index < 0:
            return
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return
        x, y, w, h = bbox
        value = self.tree.set(item, self.tree["columns"][col_index])
        edit = tk.Entry(self.tree)
        edit.insert(0, value)
        edit.select_range(0, tk.END)
        edit.place(x=x, y=y, w=w, h=h)
        edit.focus_set()

        def save_edit(event=None):
            new_val = edit.get()
            edit.destroy()
            idx = self.tree.index(item) - 1
            key = self.tree["columns"][col_index]
            m = {"h": "h", "c": "c", "φ": "φ", "γ": "γ", "a_OCR": "a_OCR", "b_OCR": "b_OCR", "c_OCR": "c_OCR", "α_c": "α_c", "α_tanφ": "α_tanφ", "E": "E", "ν": "ν"}
            if key in m:
                k = m[key]
                try:
                    v = float(new_val)
                    if k in ('α_c','α_tanφ'):
                        if v > 1.0:
                            messagebox.showerror("Invalid α", "α must be <= 1. Setting to 1.0.")
                            v = 1.0
                        if v < 0.0:
                            messagebox.showerror("Invalid α", "α must be >= 0. Setting to 0.0.")
                            v = 0.0
                    self.layers[idx][k] = v
                    self._refresh_tree()
                except ValueError:
                    messagebox.showerror("Invalid", f"Value for {k} must be numeric.")

        edit.bind("<Return>", save_edit)
        edit.bind("<FocusOut>", save_edit)

    def _open_manual(self):
        # Manual is bundled with the EXE via PyInstaller --add-data
        path = resource_path("CUT_Axially_Loaded_Pile_User_Manual.pdf")
        if os.path.exists(path):
            webbrowser.open(path)
        else:
            messagebox.showinfo(
                "Manual not found",
                "The file 'CUT_Axially_Loaded_Pile_User_Manual.pdf' could not be located.\n"
                "Make sure it is included with the executable or added as PyInstaller data."
            )

    def _parse_q_xlim(self):
        xmin_s = self.var_qxmin.get().strip()
        xmax_s = self.var_qxmax.get().strip()
        xmin = None
        xmax = None
        try:
            if xmin_s != "":
                xmin = float(xmin_s)
        except Exception:
            xmin = None
        try:
            if xmax_s != "":
                xmax = float(xmax_s)
        except Exception:
            xmax = None
        if (xmin is not None) and (xmax is not None) and (xmax <= xmin):
            xmin = None
            xmax = None
        return xmin, xmax

    def _parse_xlim(self):
        xmin_s = self.var_kxmin.get().strip()
        xmax_s = self.var_kxmax.get().strip()
        xmin = None
        xmax = None
        try:
            if xmin_s != "":
                xmin = float(xmin_s)
        except Exception:
            xmin = None
        try:
            if xmax_s != "":
                xmax = float(xmax_s)
        except Exception:
            xmax = None
        if (xmin is not None) and (xmax is not None) and (xmax <= xmin):
            xmin = None
            xmax = None
        return xmin, xmax

    # ------------------ compute & draw ------------------
    def _enforce_gwt_split(self, gw_depth: float):
        """If groundwater depth lies strictly inside a layer (no explicit boundary),
        split that layer into two: [top_part, bottom_part]. Copy properties.
        Update the layers list and refresh the UI table.
        """
        if gw_depth is None or gw_depth <= 0:
            return
        z_top = 0.0
        for idx, L in enumerate(list(self.layers)):
            h = float(L['h'])
            z_bot = z_top + h
            # explicit boundary exactly at top or bottom -> do nothing
            if abs(gw_depth - z_top) < 1e-9 or abs(gw_depth - z_bot) < 1e-9:
                return
            if z_top < gw_depth < z_bot:
                # Split into two layers
                h_top = gw_depth - z_top
                h_bot = z_bot - gw_depth
                if h_top <= 1e-6 or h_bot <= 1e-6:
                    return
                L_top = dict(L)
                L_bot = dict(L)
                L_top['h'] = h_top
                L_bot['h'] = h_bot
                # Keep gamma values as entered; header already clarifies γ may be γ or γsat
                # Insert and replace
                self.layers[idx:idx+1] = [L_top, L_bot]
                self._refresh_tree()
                messagebox.showinfo(
                    "Groundwater split",
                    f"GWT at z={gw_depth:.2f} m lies inside a layer. The layer was split to h={h_top:.2f} m above and h={h_bot:.2f} m below."
                )
                return
            z_top = z_bot
    
    def _run(self):
        # Check if GWT lies inside a layer without an explicit boundary
        try:
            gw = float(self.var_gw.get())
            z_top = 0.0
            found_cross = False
            explicit_boundary = False
            for L in self.layers:
                z_bot = z_top + float(L['h'])
                if abs(gw - z_top) < 1e-6 or abs(gw - z_bot) < 1e-6:
                    explicit_boundary = True
                if z_top < gw < z_bot:
                    found_cross = True
                z_top = z_bot
            if found_cross and not explicit_boundary and not getattr(self, "_shown_gwt_note", False):
                messagebox.showinfo(
                    "Groundwater split",
                    "The groundwater table cuts through a layer. The program will treat it as two layers:\n"
                    "• above GWT with γ\n"
                    "• below GWT with γ′ = γ_sat − γ_w\n\n"
                    "Note: The \"γ (or γsat)\" column in the table may refer to either depending on the side of GWT."
                )
                self._shown_gwt_note = True
        except Exception:
            pass
        
        try:
            if self.var_apply_src_all.get():
                ac = float(self.var_alpha_c_all.get())
                at = float(self.var_alpha_tanphi_all.get())
                # clamp
                for name, v in [('α_c', ac), ('α_tanφ', at)]:
                    if v > 1.0:
                        messagebox.showerror('Invalid α', f"{name} must be <= 1. Setting to 1.0.")
                        if name=='α_c': ac = 1.0
                        else: at = 1.0
                    if v < 0.0:
                        messagebox.showerror('Invalid α', f"{name} must be >= 0. Setting to 0.0.")
                        if name=='α_c': ac = 0.0
                        else: at = 0.0
                self.var_alpha_c_all.set(ac)
                self.var_alpha_tanphi_all.set(at)
                for L in self.layers:
                    L['α_c'] = ac
                    L['α_tanφ'] = at
                self._refresh_tree()

            kv = float(self.var_kv.get())
            N = int(self.var_N.get())
            gw = float(self.var_gw.get())
            # enforce GWT split into layers if necessary
            self._enforce_gwt_split(gw)
            D = float(self.var_D.get())
            displacement_m = float(self.var_displacement.get())
            gammaR = float(self.var_gammaR.get())
            axial = float(self.var_axial_load.get())
            a_mode = self.var_a_mode.get()
            a_const = float(self.var_a_const.get())
            if a_mode == "constant" and a_const > 1.0:
                messagebox.showerror("Invalid a", "The exponent a must be <= 1. Please enter a value <= 1.")
                return
            Rt_unfact = float(self.var_Rt_unfact.get())

            if D <= 0 or N < 20:
                raise ValueError("D must be positive and N >= 20.")
            if gammaR <= 0:
                raise ValueError("γ_R must be > 0.")

            if self.var_pile_type.get() == "Displacement":
                for L in self.layers:
                    if 'E' not in L:
                        L['E'] = 30000.0
                    if 'ν' not in L:
                        L['ν'] = 0.3

            params = {
                'D': D, 'kv': kv, 'N': N, 'pile_type': self.var_pile_type.get(),
                'displacement_m': displacement_m, 'gw_depth': gw,
                'γ_R': gammaR, 'axial_load': axial,
                'a_mode': a_mode, 'a_const': a_const, 'Rt_unfact': Rt_unfact
            ,
                'OCR_cap': (float(self._ocr_cap_var.get()) if (self._ocr_cap_var.get() or '').strip() != '' else None)
            }

            (H, Rs, qs, per_layer_results, safety_shaft, Rt_fact,
             Rtot_fact, safety_total, details, kbase, kmod, kpcap) = compute_shaft_resistance(params, self.layers)

            # cache for charts and report
            self._last_H = H
            self._last_kbase = kbase
            self._last_kmod = kmod
            self._last_kpcap = kpcap
            self._last_slices = details
            self._last_layer_results = per_layer_results

            # outputs
            self.var_Rs.set(f"{Rs:,.2f} kN")
            self.var_qs.set(f"{qs:,.2f} kPa")
            self.var_safety_shaft.set(f"{safety_shaft:,.3f}" if safety_shaft == safety_shaft else "--")
            self.var_Rt.set(f"{Rt_fact:,.2f} kN")
            self.var_Rtot.set(f"{Rtot_fact:,.2f} kN")
            self.var_safety_total.set(f"{safety_total:,.3f}" if safety_total == safety_total else "--")

            # tables
            for i in self.tbl_slices.get_children():
                self.tbl_slices.delete(i)
            for s in details:
                kp_here = next((p["K"] for p in getattr(self, "_last_kpcap", []) if abs(p["z"] - s["z_mid"]) < 1e-9), float("nan"))
                self.tbl_slices.insert("", "end", values=(f"{s['z_mid']:.3f}", f"{s['K']:.4f}", f"{kp_here:.4f}", f"{s['q_local']:.2f}", f"{s['dQ']:.2f}"))

            for i in self.tbl_layers.get_children():
                self.tbl_layers.delete(i)
            for r in per_layer_results:
                self.tbl_layers.insert("", "end", values=(r['idx'], f"{r['h']:.3f}", f"{r['q_kPa_fact']:.3f}", f"{r['Q_kN_fact']:.3f}", f"{r['ratio']:.3f}"))

            # redraw charts
            self._draw_chart()
            self._draw_qchart()

            # redraw visualization tabs as well
            try:
                self._draw_visualization(self.canvas_viz)
            except Exception:
                pass
            try:
                self._draw_ocr_chart()
            except Exception:
                pass
                
        except Exception as e:
            messagebox.showerror("Error", str(e))

    
    def _draw_ocr_chart(self):
        if not hasattr(self, "canvas_ocr"):
            return
        c = self.canvas_ocr
        if c is None:
            return
        c.delete("all")
        layers = self.layers[:]
        if not layers:
            return
        H = sum(L['h'] for L in layers)
        if H <= 0:
            return
        # sample
        z_vals = []
        dz = max(0.02, H/300.0)
        z=0.0
        while z <= H + 1e-9:
            z_vals.append(z)
            z += dz
        # helper
        def layer_for(zm):
            zt=0.0
            for L in layers:
                zb = zt + L['h']
                if zm <= zb + 1e-9:
                    return L
                zt = zb
            return layers[-1]
        o_vals = []
        for z in z_vals:
            L = layer_for(z if z>1e-9 else 1e-6)
            a = float(L.get('a_OCR', 1.0))
            b = float(L.get('b_OCR', 1.0))
            c_OCR = float(L.get('c_OCR', 1.0)) if 'c_OCR' in L else 0.0
            zz = max(1e-6, z)
            val = a * ((zz) ** (-b)) + c_OCR
            try:
                cap = float(self._ocr_cap_var.get()) if (self._ocr_cap_var.get() or '').strip() != '' else None

            except Exception:
                cap = None
            if cap is not None and cap > 0:
                val = min(val, cap)
            o_vals.append(val)
        zmin, zmax = 0.0, H
        omin, omax = (min(o_vals), max(o_vals)) if o_vals else (0.0,1.0)
        if omin == omax:
            omin, omax = omin-0.5, omax+0.5
        # apply user overrides if provided
        try:
            xmin_txt = (self._ocr_xmin_var.get() or '').strip()
            xmax_txt = (self._ocr_xmax_var.get() or '').strip()
            if xmin_txt != '':
                omin = float(xmin_txt)
            if xmax_txt != '':
                omax = float(xmax_txt)
            if omax <= omin:
                omax = omin + 1.0
        except Exception:
            pass
        W = c.winfo_width() or 800
        Hp = c.winfo_height() or 520
        padL, padR, padT, padB = 80, 30, 16, 48
        def x_map(v): return padL + (v-omin)/max(1e-12,(omax-omin))*(W-padL-padR)
        def y_map(z): return padT + (z-zmin)/max(1e-12,(zmax-zmin))*(Hp-padT-padB)
        # axes
        c.create_line(x_map(omin), y_map(zmin), x_map(omin), y_map(zmax), fill="#444")
        c.create_line(x_map(omin), y_map(zmax), x_map(omax), y_map(zmax), fill="#444")
        c.create_text((x_map(omin)+x_map(omax))/2, y_map(zmax)+30, text="OCR", anchor="n", fill="#444")
        c.create_text(x_map(omin)-55, y_map(zmin)-10, text="z (m)", anchor="nw", fill="#444")
        # grid
        for ov in nice_ticks(omin, omax, n=6):
            x = x_map(ov)
            c.create_line(x, y_map(zmax), x, y_map(zmax)+6, fill="#444")
            c.create_text(x, y_map(zmax)+18, text=f"{ov:.2f}", anchor="n", fill="#444")
            c.create_line(x, y_map(zmin), x, y_map(zmax), fill="#f0f0f0")
        for zv in nice_ticks(zmin, zmax, n=6):
            y = y_map(zv)
            c.create_line(x_map(omin)-6, y, x_map(omin), y, fill="#444")
            c.create_text(x_map(omin)-10, y, text=f"{zv:.1f}", anchor="e", fill="#444")
            c.create_line(x_map(omin), y, x_map(omax), y, fill="#f3f3f3")
        # curve
        prev=None
        for z, o in zip(z_vals, o_vals):
            x = x_map(o); y = y_map(z)
            if prev is not None:
                c.create_line(prev[0], prev[1], x, y, fill="#8e24aa", width=2)
            prev=(x,y)
        # legend with offsets
        try:
            x_off = float(self.var_ocr_legend_x.get() or "10")
        except Exception:
            x_off = 10.0
        try:
            y_off = float(self.var_ocr_legend_y.get() or "10")
        except Exception:
            y_off = 10.0

        x_leg = x_map(omin) + x_off
        y_leg = y_map(zmin) + y_off

        c.create_rectangle(x_leg, y_leg, x_leg + 280, y_leg + 30, fill="white", outline="#999")
        c.create_line(x_leg + 10, y_leg + 15, x_leg + 50, y_leg + 15, fill="#8e24aa", width=2)
        c.create_text(x_leg + 70, y_leg + 15,
                      text="OCR(z) = a_OCR*z^{-b_OCR}+c_OCR", anchor="w", fill="#333")

    def _draw_qchart(self):
        if not hasattr(self, "_last_slices"):
            return
        data = self._last_slices
        if not data:
            return
        c = self.canvas_q
        c.delete("all")
        z_vals = [s['z_mid'] for s in data]
        q_vals = [s['q_local'] for s in data]
        zmin, zmax = 0.0, max(z_vals) if z_vals else 1.0
        auto_qmin, auto_qmax = (min(q_vals), max(q_vals)) if q_vals else (0.0, 1.0)
        qxmin, qxmax = self._parse_q_xlim()
        qmin = auto_qmin if qxmin is None else qxmin
        qmax = auto_qmax if qxmax is None else qxmax
        if qmin == qmax:
            qmin, qmax = qmin - 1.0, qmax + 1.0

        W = c.winfo_width() or 600
        Hp = c.winfo_height() or 360
        padL, padR, padT, padB = 80, 30, 16, 48

        def x_map(q):
            return padL + (q - qmin) / (qmax - qmin) * (W - padL - padR)

        def y_map(z):
            return padT + (z - zmin) / (zmax - zmin) * (Hp - padT - padB)

        # axes
        c.create_line(x_map(qmin), y_map(zmin), x_map(qmin), y_map(zmax), fill="#444")
        c.create_line(x_map(qmin), y_map(zmax), x_map(qmax), y_map(zmax), fill="#444")
        c.create_text((x_map(qmin) + x_map(qmax)) / 2, y_map(zmax) + 30, text="q_s (kPa)", anchor="n", fill="#444")
        c.create_text(x_map(qmin) - 55, y_map(zmin) - 10, text="z (m)", anchor="nw", fill="#444")

        # grid
        for qv in nice_ticks(qmin, qmax, n=6):
            x = x_map(qv)
            c.create_line(x, y_map(zmax), x, y_map(zmax) + 6, fill="#444")
            c.create_text(x, y_map(zmax) + 18, text=f"{qv:.0f}", anchor="n", fill="#444")
            c.create_line(x, y_map(zmin), x, y_map(zmax), fill="#f0f0f0")
        for zv in nice_ticks(zmin, zmax, n=6):
            y = y_map(zv)
            c.create_line(x_map(qmin) - 6, y, x_map(qmin), y, fill="#444")
            c.create_text(x_map(qmin) - 10, y, text=f"{zv:.1f}", anchor="e", fill="#444")
            c.create_line(x_map(qmin), y, x_map(qmax), y, fill="#f3f3f3")

        # curve
        prev = None
        for s in data:
            x = x_map(s['q_local'])
            y = y_map(s['z_mid'])
            if prev is not None:
                c.create_line(prev[0], prev[1], x, y, fill="#2e7d32", width=2)
            prev = (x, y)

    def _draw_chart(self):
        if not hasattr(self, "_last_kbase"):
            return
        kbase = self._last_kbase
        kmod = self._last_kmod
        H = self._last_H
        c = self.canvas
        c.delete("all")
        if not kbase or not kmod:
            return
        z_vals = [p['z'] for p in kbase]
        k_vals = [p['K'] for p in kbase] + [p['K'] for p in kmod]
        zmin, zmax = 0.0, max(z_vals) if z_vals else H
        auto_kmin, auto_kmax = (min(k_vals), max(k_vals)) if k_vals else (0.0, 1.0)
        xmin_user, xmax_user = self._parse_xlim()
        kmin = auto_kmin if xmin_user is None else xmin_user
        kmax = auto_kmax if xmax_user is None else xmax_user
        if kmin == kmax:
            kmin, kmax = kmin - 1.0, kmax + 1.0

        W = c.winfo_width() or 600
        Hp = c.winfo_height() or 360
        padL, padR, padT, padB = 80, 30, 16, 48

        def x_map(k):
            return padL + (k - kmin) / (kmax - kmin) * (W - padL - padR)

        def y_map(z):
            return padT + (z - zmin) / (zmax - zmin) * (Hp - padT - padB)

        # axes
        c.create_line(x_map(kmin), y_map(zmin), x_map(kmin), y_map(zmax), fill="#444")
        c.create_line(x_map(kmin), y_map(zmax), x_map(kmax), y_map(zmax), fill="#444")
        c.create_text((x_map(kmin) + x_map(kmax)) / 2, y_map(zmax) + 30, text="K", anchor="n", fill="#444")
        c.create_text(x_map(kmin) - 55, y_map(zmin) - 10, text="z (m)", anchor="nw", fill="#444")

        # grid
        for kv in nice_ticks(kmin, kmax, n=6):
            x = x_map(kv)
            c.create_line(x, y_map(zmax), x, y_map(zmax) + 6, fill="#444")
            c.create_text(x, y_map(zmax) + 18, text=f"{kv:.2f}", anchor="n", fill="#444")
            c.create_line(x, y_map(zmin), x, y_map(zmax), fill="#f0f0f0")
        for zv in nice_ticks(zmin, zmax, n=6):
            y = y_map(zv)
            c.create_line(x_map(kmin) - 6, y, x_map(kmin), y, fill="#444")
            c.create_text(x_map(kmin) - 10, y, text=f"{zv:.1f}", anchor="e", fill="#444")
            c.create_line(x_map(kmin), y, x_map(kmax), y, fill="#f3f3f3")

        # curves
        prev = None
        for p in kbase:
            x = x_map(p['K'])
            y = y_map(p['z'])
            if prev is not None:
                c.create_line(prev[0], prev[1], x, y, fill="#1976d2", width=2)
            prev = (x, y)

        prev = None
        for p in kmod:
            x = x_map(p['K'])
            y = y_map(p['z'])
            if prev is not None:
                c.create_line(prev[0], prev[1], x, y, fill="#d32f2f", width=2)
            prev = (x, y)

        # Kp curve
        kpcap = getattr(self, "_last_kpcap", [])
        if kpcap:
            prev = None
            for p in kpcap:
                x = x_map(p['K'])
                y = y_map(p['z'])
                if prev is not None:
                    c.create_line(prev[0], prev[1], x, y, fill="#6a1b9a", width=2)
                prev = (x, y)

        # legend — controlled by x_legend, y_legend
        legend_w, legend_h = 240, 72
        try:
            x_off = float(self.var_k_legend_x.get() or "10")
        except Exception:
            x_off = 10.0
        try:
            y_off = float(self.var_k_legend_y.get() or "10")
        except Exception:
            y_off = 10.0

        x_leg = x_map(kmax) - legend_w - x_off
        y_leg = y_map(zmin) + y_off


        c.create_rectangle(x_leg, y_leg, x_leg + legend_w, y_leg + legend_h, fill="white", outline="#999")

        # K0 (blue)
        c.create_line(x_leg + 10, y_leg + 15, x_leg + 50, y_leg + 15, fill="#1976d2", width=2)
        c.create_text(x_leg + legend_w - 10, y_leg + 15, text="K0 (m=1)", anchor="e", fill="#333")

        # K (red)
        c.create_line(x_leg + 10, y_leg + 35, x_leg + 50, y_leg + 35, fill="#d32f2f", width=2)
        c.create_text(x_leg + legend_w - 10, y_leg + 35, text="K (modified, capped)", anchor="e", fill="#333")

        # Kp (purple)
        c.create_line(x_leg + 10, y_leg + 55, x_leg + 50, y_leg + 55, fill="#6a1b9a", width=2)
        c.create_text(x_leg + legend_w - 10, y_leg + 55, text="Kp (m→∞)", anchor="e", fill="#333")


    # ------------------ Visualization ------------------
    def _open_visualization(self):
        # Visualization lives in the tab's canvas; just redraw it
        try:
            self._draw_visualization(self.canvas_viz)
        except Exception as e:
            messagebox.showerror("Visualization", str(e))

    def _draw_visualization(self, cv):
        # Draw into the given canvas (no new window)
        if cv is None:
            return
        W = int(cv.winfo_width() or 780)
        Hpx = int(cv.winfo_height() or 520)
        cv.delete('all')

        layers = self.layers[:]
        H = sum(L['h'] for L in layers) if layers else 1.0
        gw = float(self.var_gw.get())
        D = float(self.var_D.get())
        kv = float(self.var_kv.get())
        pile_type = self.var_pile_type.get()

        padL, padR, padT, padB = 120, 40, 120, 110
        hplot = Hpx - padT - padB
        wplot = W - padL - padR

        def y_map(zm):
            return padT + (zm / max(H, 1e-12)) * hplot

        # background
        cv.create_rectangle(0, 0, W, y_map(0), fill="#f8f8f8", outline="")
        cv.create_rectangle(0, y_map(0), W, Hpx, fill="#f3efe8", outline="")
        # GWT
        if gw < H:
            cv.create_rectangle(0, y_map(gw), W, Hpx, fill="#e0f2ff", outline="")
            cv.create_line(padL - 10, y_map(gw), W - padR + 10, y_map(gw), fill="#2a7fff", width=2)
            cv.create_text(W - padR, y_map(gw) - 10, text=f"GWT = {gw:.2f} m", anchor="e", fill="#2a7fff", font=("Segoe UI", 9, "bold"))

        # axes
        cv.create_line(padL, padT, padL, Hpx - padB, fill="#444")
        cv.create_line(padL, y_map(0), W - padR, y_map(0), fill="#444")
        cv.create_text(padL - 20, padT, text="z (m)", anchor="ne", fill="#444")
        for i in range(0, 11):
            zv = H * i / 10.0
            y = y_map(zv)
            cv.create_line(padL - 6, y, padL, y, fill="#444")
            cv.create_text(padL - 10, y, text=f"{zv:.1f}", anchor="e", fill="#666", font=("Segoe UI", 9))

        # pile
        scale_v = hplot / max(H, 1e-12)
        pile_w = max(10, min(80, D * scale_v))
        x_center = padL + wplot * 0.30
        x0 = x_center - pile_w / 2
        x1 = x_center + pile_w / 2
        cv.create_rectangle(x0, y_map(0), x1, y_map(H), fill="#ddd", outline="#666")
        cv.create_text(x_center - 90, y_map(H) + 14, text=f"H = {H:.2f} m", anchor="e", font=("Segoe UI", 9, "bold"))
        cv.create_line(x0, y_map(0) + 26, x1, y_map(0) + 26, arrow=tk.BOTH)
        cv.create_text(x_center, y_map(0) + 34, text=f"D = {D:.2f} m", anchor="n", font=("Segoe UI", 9, "bold"))

        # Force arrows: Axial load at head (downward), Tip resistance at toe (upward)
        Vk = float(self.var_axial_load.get())
        Rt_nf = float(self.var_Rt_unfact.get())
        # Axial load arrow (downward) at pile head
        cv.create_line(x_center, padT-20, x_center, y_map(0), arrow=tk.LAST, width=2)
        cv.create_text(x_center - 80, padT-28, text=f"Axial load, V_k = {Vk:.1f} kN", anchor="e", font=("Segoe UI", 9, "bold"))
        # Tip resistance arrow (upward) at pile toe
        cv.create_line(x_center, y_map(H) + 40, x_center, y_map(H), arrow=tk.LAST, width=2)
        cv.create_text(x_center + 80, y_map(H) + 30, text=f"Tip resistance, R_t (non-factored) = {Rt_nf:.1f} kN", anchor="w", font=("Segoe UI", 9, "bold"))

        # layers
        zc = 0.0
        for i, L in enumerate(layers, 1):
            zc_next = zc + L['h']
            cv.create_line(padL - 8, y_map(zc_next), W - padR, y_map(zc_next), fill="#bbb", dash=(4, 2))
            xm = x1 + 30
            cv.create_line(xm, y_map(zc), xm, y_map(zc_next), fill="#666")
            cv.create_line(xm - 6, y_map(zc), xm + 6, y_map(zc), fill="#666")
            cv.create_line(xm - 6, y_map(zc_next), xm + 6, y_map(zc_next), fill="#666")
            cv.create_text(xm + 8, (y_map(zc) + y_map(zc_next)) / 2, text=f"h{i} = {L['h']:.2f} m", anchor="w", font=("Segoe UI", 9, "bold"))

            info = (
                f"Layer {i}:\n"
                f"c={L['c']:.2f} kPa, φ={L['φ']:.1f} deg\n"
                f"γ={L.get('γ', L.get('gamma', 19.0)):.2f} kN/m^3, "
                f"a_OCR={L.get('a_OCR',1.0):.3f}, b_OCR={L.get('b_OCR',1.0):.3f}, "
                f"c_OCR={L.get('c_OCR',1.0):.3f}\n"
                f"α_c={L.get('α_c',1.0):.2f}, α_tanφ={L.get('α_tanφ',1.0):.2f}, "
                f"E={L.get('E',30000.0):.0f} kPa, ν={L.get('ν',0.3):.2f}"
            )
            tx = x1 + 120
            ty = (y_map(zc) + y_map(zc_next)) / 2
            cv.create_text(tx, ty, text=info, anchor="w", font=("Segoe UI", 9), fill="#333")
            zc = zc_next

        head = f"Pile type: {pile_type}    k_v={kv:.3f}    GWT={gw:.2f} m"
        cv.create_text(W/2, padT-70, text=head, anchor="n", font=("Segoe UI", 11, "bold"))

        # legend with offsets
        try:
            x_off = float(self.var_viz_legend_x.get() or "10")
        except Exception:
            x_off = 10.0
        try:
            y_off = float(self.var_viz_legend_y.get() or "10")
        except Exception:
            y_off = 10.0

        legend_w, legend_h = 220, 75
        x_leg = W - legend_w - x_off
        y_leg = Hpx - legend_h - y_off

        cv.create_rectangle(x_leg, y_leg, x_leg + legend_w, y_leg + legend_h,
                            outline="#999", fill="#fff")
        cv.create_rectangle(x_leg + 10, y_leg + 10, x_leg + 30, y_leg + 30,
                            fill="#ddd", outline="#666")
        cv.create_text(x_leg + 35, y_leg + 20, text="Pile",
                       anchor="w", font=("Segoe UI", 9))
        cv.create_line(x_leg + 10, y_leg + 40, x_leg + 30, y_leg + 40,
                       fill="#2a7fff", width=2)
        cv.create_text(x_leg + 35, y_leg + 40, text="Groundwater level",
                       anchor="w", font=("Segoe UI", 9))
        cv.create_line(x_leg + 10, y_leg + 60, x_leg + 30, y_leg + 60,
                       fill="#bbb", dash=(4, 2))
        cv.create_text(x_leg + 35, y_leg + 60, text="Layer boundary",
                       anchor="w", font=("Segoe UI", 9))




    # ------------------ Export Slices to Excel ------------------
    def _export_slices_excel(self):
        try:
            from tkinter import filedialog, messagebox
            import os
            # Try xlsx first
            try:
                import openpyxl
                use_xlsx = True
            except Exception:
                use_xlsx = False
            # Choose filename
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            default_xlsx = f"CUT_Axially_Loaded_Pile_Slices_{ts}.xlsx"
            default_csv  = f"CUT_Axially_Loaded_Pile_Slices_{ts}.csv"
            if use_xlsx:
                path = filedialog.asksaveasfilename(
                    title="Save Slices (point-level)",
                    defaultextension=".xlsx",
                    initialfile=default_xlsx,
                    filetypes=[("Excel Workbook", "*.xlsx"), ("All files", "*.*")],
                )
            else:
                path = filedialog.asksaveasfilename(
                    title="Save Slices (point-level) as CSV",
                    defaultextension=".csv",
                    initialfile=default_csv,
                    filetypes=[("CSV (Excel)", "*.csv"), ("All files", "*.*")],
                )
            if not path:
                return
            # Prepare rows
            rows = []
            rows.append(["z_mid (m)", "K", "Kp", "q_local (kPa)", "dQ (kN)"])
            slices = getattr(self, "_last_slices", [])
            kpcap = getattr(self, "_last_kpcap", [])
            for s in slices:
                kp_here = next((p["K"] for p in kpcap if abs(p["z"] - s["z_mid"]) < 1e-9), float("nan"))
                rows.append([s["z_mid"], s["K"], kp_here, s["q_local"], s["dQ"]])
            # Write file
            if use_xlsx:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = "Slices"
                for r in rows:
                    ws.append(r)
                widths = [12, 10, 10, 16, 12]
                for i, w in enumerate(widths, start=1):
                    ws.column_dimensions[chr(64+i)].width = w
                wb.save(path)
                messagebox.showinfo("Export", f"Slices exported to Excel:\n{path}")
            else:
                import csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                messagebox.showinfo("Export", f"openpyxl not found.\nSaved CSV (Excel-readable):\n{path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))
    # ------------------ Export PDF ------------------

    def _export_pdf(self):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.lib.utils import ImageReader
            from datetime import datetime
            import os
        except Exception:
            messagebox.showinfo("Export", "Install 'reportlab' to enable PDF export.")
            return

        # ---- Save As dialog with timestamp YYYYMMDD_HHMM ----
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"CUT_Axially_Loaded_Pile_Report_{ts}.pdf"
        path = filedialog.asksaveasfilename(
            title="Save report as...",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")]
        )
        if not path:
            return

        PRINTABLE_W = 170.0  # mm (A4 width 210 - 2*20 mm margins)

        def header_like_reference(c):
            W, H = A4
            margin = 20*mm
            top = H - margin

            # Logo (script folder, then CWD)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [os.path.join(script_dir, "cut_logo.png"), "cut_logo.png"]
            logo_file = next((p for p in candidates if os.path.exists(p)), None)
            logo_w = logo_h = 0
            if logo_file:
                try:
                    img = ImageReader(logo_file)
                    iw, ih = img.getSize()
                    target_h = 16*mm
                    scale = target_h / ih
                    logo_w = iw * scale
                    logo_h = ih * scale
                    c.drawImage(img, margin, top - logo_h, width=logo_w, height=logo_h,
                                preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass

            # Title + org + timestamp
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin + (logo_w + (4*mm if logo_w else 0)), top - 2*mm,
                         "CUT Axially Loaded Pile Report")
            c.setFont("Helvetica", 9)
            c.drawString(margin + (logo_w + (4*mm if logo_w else 0)), top - 9*mm,
                         "Cyprus University of Technology")
            c.drawRightString(W - margin, top - 2*mm, datetime.now().strftime("%Y-%m-%d %H:%M"))

            # Separator line
            y = top - (logo_h if logo_h else 10*mm) - 4*mm
            c.setStrokeColor(colors.grey)
            c.line(margin, y, W - margin, y)
            return y - 8*mm  # return baseline below header

        def section_title(c, title, y):
            W, H = A4
            margin = 20*mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, title)
            c.setStrokeColor(colors.black)
            c.line(margin, y - 2*mm, W - margin, y - 2*mm)
            return y - 8*mm

        def subhead(c, title, y):
            c.setFont("Helvetica-Bold", 10)
            c.drawString(20*mm, y, title)
            return y - 5*mm

        def kv(c, pairs, y, col_w=52*mm, gap=6*mm):
            """3-column key/value rows that fit within 170 mm width."""
            margin = 20*mm
            x = margin
            count = 0
            c.setFont("Helvetica", 9)
            for k, v in pairs:
                c.drawString(x, y, k)
                c.drawRightString(x + col_w, y, v)
                x += col_w + gap
                count += 1
                if count % 3 == 0:
                    y -= 5*mm
                    x = margin
            if count % 3 != 0:
                y -= 5*mm
            return y

        
        # -- text wrapping helpers (avoid overlap) --
        def _wrap_text(c, text, width_pt, font="Helvetica", size=9):
            """Return a list of lines that fit within width_pt (in points)."""
            if text is None:
                return [""]
            text = str(text)
            if not text:
                return [""]
            c.setFont(font, size)
            words = text.split()
            lines, cur = [], ""
            for w in words:
                test = (cur + " " + w).strip()
                if c.stringWidth(test, font, size) <= width_pt:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    # very long single word fallback: hard-split
                    if c.stringWidth(w, font, size) > width_pt:
                        chunk = ""
                        for ch in w:
                            if c.stringWidth(chunk + ch, font, size) <= width_pt:
                                chunk += ch
                            else:
                                lines.append(chunk or ch)
                                chunk = ch
                        cur = chunk
                    else:
                        cur = w
            if cur:
                lines.append(cur)
            return lines or [""]

        def kv_wrap(c, pairs, y, *, col_w_mm=52.0, gap_mm=6.0, cols=3, font="Helvetica", size=9, line_h_mm=4.6):
            """Draw key/value pairs in wrapped columns to avoid overlap."""
            margin = 20*mm
            col_w_pt = col_w_mm * mm
            gap_pt = gap_mm * mm
            line_h = line_h_mm * mm

            x = margin
            used_in_row = 0
            c.setFont(font, size)

            def draw_cell(k, v, x0, y0):
                key_lines = _wrap_text(c, k, col_w_pt, font, size)
                val_lines = _wrap_text(c, v, col_w_pt, font, size)
                rows = max(len(key_lines), len(val_lines))
                yy = y0
                for i in range(rows):
                    k_txt = key_lines[i] if i < len(key_lines) else ""
                    v_txt = val_lines[i] if i < len(val_lines) else ""
                    c.drawString(x0, yy, k_txt)
                    v_w = c.stringWidth(v_txt, font, size)
                    c.drawString(x0 + col_w_pt - v_w, yy, v_txt)
                    yy -= line_h
                return rows * line_h

            cells_in_row = 0
            for k, v in pairs:
                height_used = draw_cell(k, v, x, y)
                x += col_w_pt + gap_pt
                used_in_row = max(used_in_row, height_used)
                cells_in_row += 1
                if cells_in_row >= cols:
                    y -= used_in_row + (1.0*mm)
                    x = margin
                    cells_in_row = 0
                    used_in_row = 0
            if cells_in_row != 0:
                y -= used_in_row + (1.0*mm)
            return y
        def table_header(c, cols, y, xs, widths):
            c.setFont("Helvetica-Bold", 8)
            for x, t, w in zip(xs, cols, widths):
                c.drawString(x, y, t)
            c.setStrokeColor(colors.grey)
            c.line(20*mm, y - 2*mm, (20 + PRINTABLE_W)*mm, y - 2*mm)
            return y - 5*mm

        def ensure(c, y, need=30*mm):
            if y < need:
                c.showPage()
                return header_like_reference(c)
            return y

        

        # ---- Table helpers for perfect alignment ----
        def _build_columns(widths_mm, start_x_mm=20.0):
            xs = [start_x_mm * mm]
            for w in widths_mm[:-1]:
                xs.append(xs[-1] + w * mm)
            return xs

        def draw_table_header(c, titles, widths_mm, y, *, start_x_mm=20.0, font="Helvetica-Bold", size=8, pad_mm=1.0, draw_line=True):
            xs = _build_columns(widths_mm, start_x_mm)
            c.setFont(font, size)
            for x, w, t in zip(xs, widths_mm, titles):
                c.drawString(x + pad_mm * mm, y, t)
            if draw_line:
                c.setStrokeColor(colors.grey)
                c.line(start_x_mm * mm, y - 2 * mm, (start_x_mm + PRINTABLE_W) * mm, y - 2 * mm)
            return y - 6 * mm, xs

        def draw_table_row(c, row_vals, widths_mm, y, aligns, xs=None, *, start_x_mm=20.0, font="Helvetica", size=8, pad_mm=1.0):
            if xs is None:
                xs = _build_columns(widths_mm, start_x_mm)
            c.setFont(font, size)
            for x, w, val, al in zip(xs, widths_mm, row_vals, aligns):
                if al == 'R':
                    c.drawRightString(x + w * mm - pad_mm * mm, y, val)
                elif al == 'C':
                    c.drawCentredString(x + (w * mm) / 2.0, y, val)
                else:
                    c.drawString(x + pad_mm * mm, y, val)
            return y - 4.2 * mm

# Canvas
        c = canvas.Canvas(path, pagesize=A4)

        y = header_like_reference(c)

        # About
        y = section_title(c, "About", y)
        c.setFont("Helvetica", 9)
        for k, v in [("Program", "CUT_Axially_Loaded_Pile"),
                     ("Version", "v3"),
                     ("Author", "Dr Lysandros Pantelidis, Cyprus University of Technology")]:
            c.setFont("Helvetica-Bold", 9); c.drawString(20*mm, y, f"{k}:")
            c.setFont("Helvetica", 9);      c.drawString(55*mm, y, v)
            y -= 5*mm
        c.drawString(20*mm, y, "Educational tool — no warranty. Use at your own risk. Free of charge.")
        y -= 8*mm

        # Inputs
        y = section_title(c, "Inputs", y)

        D = float(self.var_D.get())
        kv_v = float(self.var_kv.get())
        N = int(self.var_N.get())
        gw = float(self.var_gw.get())
        pt = self.var_pile_type.get()
        disp = float(self.var_displacement.get())
        gR = float(self.var_gammaR.get())
        axial = float(self.var_axial_load.get())
        a_mode = self.var_a_mode.get()
        a_const = float(self.var_a_const.get())
        Rt_unfact = float(self.var_Rt_unfact.get())

        y = subhead(c, "General & GWT", y)
        y = kv_wrap(c, [("k_v (seismic)", f"{kv_v:.3f}"),
                   ("Slices, N", f"{N:d}"),
                   ("GWT depth (m)", f"{gw:.3f}")], y, cols=3)

        y = subhead(c, "Pile data", y)
        y = kv_wrap(c, [("Pile type", pt),
                   ("Diameter, D (m)", f"{D:.3f}"),
                   ("Displacement (m)", f"{disp:.4f}"),
                   ("a mode (OCR^a)", a_mode),
                   ("a (constant)", f"{a_const:.3f}")], y, cols=3)

        y = subhead(c, "Factors & Loads", y)
        y = kv_wrap(c, [("Resistance factor, γ_R", f"{gR:.3f}"),
                   ("Axial pile load, V_k or V_d (kN)", f"{axial:.3f}"),
                   ("Tip resistance, R_t (NON-factored) (kN)", f"{Rt_unfact:.3f}")], y, cols=2, col_w_mm=82.0, gap_mm=6.0, line_h_mm=4.8)
        y -= 2*mm

        # Layers table — column widths scaled to fit 170 mm
        
        y = ensure(c, y, 45*mm)
        y = subhead(c, "Layers (top to bottom)", y)
        col_titles = ["#", "h", "c", "φ", "γ",
                      "a_OCR", "b_OCR", "c_OCR", "α_c", "α_tanφ", "E", "ν"]
        col_units  = ["", "(m)", "(kPa)", "(deg)", "(kN/m³)",
                      "(-)", "(-)", "(-)", "(-)", "(-)", "(kPa)", "(-)"]
        base_widths = [8, 16, 16, 16, 20, 14, 14, 14, 14, 16, 22, 10]
        scale = PRINTABLE_W / sum(base_widths)
        widths_mm = [w * scale for w in base_widths]
        y, xs = draw_table_header(c, col_titles, widths_mm, y, start_x_mm=20.0, draw_line=False)
        aligns = ['L'] * len(col_titles)  # simple left alignment
        # units row under header
        y_line = y
        y = draw_table_row(c, col_units, widths_mm, y, aligns, xs=xs, start_x_mm=20.0)
        c.setStrokeColor(colors.grey)
        c.line(20*mm, y_line - 2*mm, (20 + PRINTABLE_W)*mm, y_line - 2*mm)
        for i, L in enumerate(self.layers, 1):
            if y < 20*mm:
                c.showPage()
                y = header_like_reference(c)
                y = subhead(c, "Layers (cont.)", y)
                y, xs = draw_table_header(c, col_titles, widths_mm, y, start_x_mm=20.0, draw_line=False)
                y_line = y
                y = draw_table_row(c, col_units, widths_mm, y, aligns, xs=xs, start_x_mm=20.0)
                c.setStrokeColor(colors.grey)
                c.line(20*mm, y_line - 2*mm, (20 + PRINTABLE_W)*mm, y_line - 2*mm)
            vals = [
                f"{i:d}",
                f"{L['h']:.3f}",
                f"{L['c']:.2f}",
                f"{L['φ']:.2f}",
                f"{L.get('γ', L.get('gamma', 19.0)):.2f}",
                f"{L.get('a_OCR',1.0):.3f}",
                f"{L.get('b_OCR',1.0):.3f}",
                f"{L.get('c_OCR',1.0):.3f}",
                f"{L.get('α_c',1.0):.3f}",
                f"{L.get('α_tanφ',1.0):.3f}",
                f"{L.get('E',30000.0):.1f}",
                f"{L.get('ν',0.3):.3f}",
            ]
            y = draw_table_row(c, vals, widths_mm, y, aligns, xs=xs, start_x_mm=20.0)


        # Outputs
        y = ensure(c, y, 40*mm)
        y = section_title(c, "Outputs", y)

        Rs_txt   = self.var_Rs.get()
        qs_txt   = self.var_qs.get()
        SFs_txt  = self.var_safety_shaft.get()
        Rt_txt   = self.var_Rt.get()
        Rtot_txt = self.var_Rtot.get()
        SFt_txt  = self.var_safety_total.get()

        y = subhead(c, "Summary", y)
        y = kv_wrap(c, [("Shaft resistance (factored), R_s", Rs_txt),
                   ("Average unit shaft (factored), q_s,tot", qs_txt),
                   ("Safety (shaft only)", SFs_txt),
                   ("Tip resistance (factored), R_t", Rt_txt),
                   ("Total pile resistance (factored), R_tot", Rtot_txt),
                   ("Safety (total)", SFt_txt)], y, cols=2, col_w_mm=82.0, gap_mm=6.0, line_h_mm=4.8)
        y -= 2*mm

        # Per-layer (factored) table — 5 columns that fit 170 mm
        
        y = ensure(c, y, 45*mm)
        y = subhead(c, "Per-layer (factored)", y)
        titles2  = ["Layer", "h (m)", "Shaft res. q (kPa)", "Shaft res. Q (kN)", "Q_layer / V_d"]
        widths2  = [18, 28, 50, 50, 24]  # total 170 mm
        y, xs2 = draw_table_header(c, titles2, widths2, y, start_x_mm=20.0)
        aligns2 = ['L','L','L','L','L']
        for r in getattr(self, "_last_layer_results", []):
            if y < 20*mm:
                c.showPage()
                y = header_like_reference(c)
                y = subhead(c, "Per-layer (cont.)", y)
                y, xs2 = draw_table_header(c, titles2, widths2, y, start_x_mm=20.0)
            row = [f"{int(r['idx'])}", f"{r['h']:.3f}", f"{r['q_kPa_fact']:.3f}", f"{r['Q_kN_fact']:.3f}", f"{r['ratio']:.3f}"]
            y = draw_table_row(c, row, widths2, y, aligns2, xs=xs2, start_x_mm=20.0)


        # ===== Charts (titles under header; plot box below title) =====
        def draw_k0_chart():
            W, H = A4
            c.showPage()
            title_y = header_like_reference(c)  # baseline under header
            c.setFont("Helvetica-Bold", 11)
            c.drawString(20*mm, title_y, "K vs depth")

            kbase = getattr(self, "_last_kbase", [])
            kmod  = getattr(self, "_last_kmod", [])
            if not (kbase and kmod):
                return

            x0, x1 = 30*mm, (20 + PRINTABLE_W)*mm
            y0, y1 = title_y - 12*mm, 25*mm  # start below the chart title

            z_vals = [p['z'] for p in kbase]
            k_vals = [p['K'] for p in kbase] + [p['K'] for p in kmod]
            zmin = 0.0
            zmax = max(z_vals) if z_vals else max(1.0, getattr(self, "_last_H", 1.0))
            auto_kmin, auto_kmax = (min(k_vals), max(k_vals)) if k_vals else (0.0, 1.0)
            xmin_user, xmax_user = self._parse_xlim()
            kmin = auto_kmin if xmin_user is None else xmin_user
            kmax = auto_kmax if xmax_user is None else xmax_user
            if kmin == kmax:
                kmin, kmax = kmin - 1.0, kmax + 1.0

            def xm(K): return x0 + (K - kmin) / max(1e-12, (kmax - kmin)) * (x1 - x0)
            def ym(z): return y0 - (z - zmin) / max(1e-12, (zmax - zmin)) * (y0 - y1)

            # axes
            c.line(x0, y1, x0, y0); c.line(x0, y1, x1, y1)
            c.setFont("Helvetica", 8); c.drawString((x0 + x1)/2, y1 - 10, "K")
            c.saveState(); c.translate(x0 - 24, (y0 + y1)/2); c.rotate(90); c.drawString(0, 0, "z (m)"); c.restoreState()

            # grid + ticks
            for kvv in nice_ticks(kmin, kmax, n=6):
                xx = xm(kvv); c.setStrokeColor(colors.lightgrey); c.line(xx, y1, xx, y0)
                c.setStrokeColor(colors.black); c.drawString(xx - 10, y1 - 14, f"{kvv:.2f}")
            for zv in nice_ticks(zmin, zmax, n=6):
                yy = ym(zv); c.setStrokeColor(colors.lightgrey); c.line(x0, yy, x1, yy)
                c.setStrokeColor(colors.black); c.drawRightString(x0 - 4, yy - 3, f"{zv:.1f}")

            # curves
            c.setStrokeColorRGB(0.10, 0.46, 0.82); prev = None
            for p in kbase:
                xx, yy = xm(p['K']), ym(p['z'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)
            c.setStrokeColorRGB(0.83, 0.18, 0.18); prev = None
            for p in kmod:
                xx, yy = xm(p['K']), ym(p['z'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)

            # Kp curve
            kpcap = getattr(self, "_last_kpcap", [])
            c.setStrokeColorRGB(0.42, 0.10, 0.60)
            prev = None
            for p in kpcap:
                xx, yy = xm(p['K']), ym(p['z'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)

            # legend
            c.setFillColor(colors.white); c.setStrokeColor(colors.grey)
            c.rect(x0 + 8*mm, y1 + 8*mm, 85*mm, 16*mm, fill=1, stroke=1)
            # K0
            c.setStrokeColorRGB(0.10, 0.46, 0.82); c.line(x0 + 12*mm, y1 + 16*mm, x0 + 26*mm, y1 + 16*mm)
            c.setFillColor(colors.black); c.drawString(x0 + 28*mm, y1 + 13*mm, "K0 (m=1)")
            # K modified
            c.setStrokeColorRGB(0.83, 0.18, 0.18); c.line(x0 + 12*mm, y1 + 12*mm, x0 + 26*mm, y1 + 12*mm)
            c.setFillColor(colors.black); c.drawString(x0 + 28*mm, y1 + 9*mm, "K (modified, capped)")
            # Kp
            c.setStrokeColorRGB(0.42, 0.10, 0.60); c.line(x0 + 48*mm, y1 + 16*mm, x0 + 62*mm, y1 + 16*mm)
            c.setFillColor(colors.black); c.drawString(x0 + 64*mm, y1 + 13*mm, "Kp (m→∞)")

        def draw_q_chart():
            W, H = A4
            c.showPage()
            title_y = header_like_reference(c)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(20*mm, title_y, "Shaft resistance vs depth")

            slices = getattr(self, "_last_slices", [])
            if not slices:
                return

            x0, x1 = 30*mm, (20 + PRINTABLE_W)*mm
            y0, y1 = title_y - 12*mm, 25*mm

            z_vals = [s['z_mid'] for s in slices]
            q_vals = [s['q_local'] for s in slices]
            zmin, zmax = 0.0, max(z_vals) if z_vals else 1.0
            auto_qmin, auto_qmax = (min(q_vals), max(q_vals)) if q_vals else (0.0, 1.0)
            qxmin, qxmax = self._parse_q_xlim()
            qmin = auto_qmin if qxmin is None else qxmin
            qmax = auto_qmax if qxmax is None else qxmax
            if qmin == qmax:
                qmin, qmax = qmin - 1.0, qmax + 1.0

            def xm(q): return x0 + (q - qmin) / max(1e-12, (qmax - qmin)) * (x1 - x0)
            def ym(z): return y0 - (z - zmin) / max(1e-12, (zmax - zmin)) * (y0 - y1)

            c.line(x0, y1, x0, y0); c.line(x0, y1, x1, y1)
            c.setFont("Helvetica", 8); c.drawString((x0 + x1)/2, y1 - 10, "q_s (kPa)")
            c.saveState(); c.translate(x0 - 24, (y0 + y1)/2); c.rotate(90); c.drawString(0, 0, "z (m)"); c.restoreState()

            for qv in nice_ticks(qmin, qmax, n=6):
                xx = xm(qv); c.setStrokeColor(colors.lightgrey); c.line(xx, y1, xx, y0)
                c.setStrokeColor(colors.black); c.drawString(xx - 10, y1 - 14, f"{qv:.0f}")
            for zv in nice_ticks(zmin, zmax, n=6):
                yy = ym(zv); c.setStrokeColor(colors.lightgrey); c.line(x0, yy, x1, yy)
                c.setStrokeColor(colors.black); c.drawRightString(x0 - 4, yy - 3, f"{zv:.1f}")

            c.setStrokeColorRGB(0.18, 0.49, 0.20); prev = None
            for s in slices:
                xx, yy = xm(s['q_local']), ym(s['z_mid'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)

        # Draw charts
        draw_k0_chart()
        draw_q_chart()

        c.save()
        try:
            webbrowser.open(path)
        except Exception:
            pass




        # Slices
        
        y = ensure(c, y, 45*mm)
        y = subhead(c, "Slices (point-level)", y)
        titlesS = ["z (m)", "K", "Kp", "q (kPa)", "dQ (kN)"]
        widthsS = [24, 32, 32, 42, 40]  # sum 170
        y, xsS = draw_table_header(c, titlesS, widthsS, y, start_x_mm=20.0)
        alignsS = ['L','L','L','L']
        c.setFont("Helvetica", 8)
        for s in getattr(self, "_last_slices", []):
            if y < 16*mm:
                c.showPage()
                y = header_like_reference(c)
                y = subhead(c, "Slices (cont.)", y)
                y, xsS = draw_table_header(c, titlesS, widthsS, y, start_x_mm=20.0)
            kp_here = next((p["K"] for p in getattr(self, "_last_kpcap", []) if abs(p["z"] - s["z_mid"]) < 1e-9), float("nan"))
            row = [f"{s['z_mid']:.3f}", f"{s['K']:.4f}", f"{kp_here:.4f}", f"{s['q_local']:.2f}", f"{s['dQ']:.2f}"]
            y = draw_table_row(c, row, widthsS, y, alignsS, xs=xsS, start_x_mm=20.0)

            def x_map(K): return x0 + (K - kmin) / max(1e-12, (kmax - kmin)) * (x1 - x0)
            def y_map(z): return y0 - (z - zmin) / max(1e-12, (zmax - zmin)) * (y0 - y1)  # inverted

            # axes
            c.line(x0, y1, x0, y0); c.line(x0, y1, x1, y1)
            c.setFont("Helvetica", 8); c.drawString((x0 + x1) / 2, y1 - 10, "K0")
            c.saveState(); c.translate(x0 - 28, (y0 + y1) / 2); c.rotate(90); c.drawString(0, 0, "z (m)"); c.restoreState()

            # grid
            for kv in nice_ticks(kmin, kmax, n=6):
                x = x_map(kv); c.setStrokeColorRGB(0.85, 0.85, 0.85); c.line(x, y1, x, y0)
                c.setStrokeColorRGB(0, 0, 0); c.drawString(x - 10, y1 - 14, f"{kv:.2f}")
            for zv in nice_ticks(zmin, zmax, n=6):
                ytick = y_map(zv); c.setStrokeColorRGB(0.9, 0.9, 0.9); c.line(x0, ytick, x1, ytick)
                c.setStrokeColorRGB(0, 0, 0); c.drawRightString(x0 - 4, ytick - 3, f"{zv:.1f}")

            # curves
            c.setStrokeColorRGB(0.10, 0.46, 0.82); prev = None
            for p in kbase:
                xx = x_map(p['K']); yy = y_map(p['z'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)
            c.setStrokeColorRGB(0.83, 0.18, 0.18); prev = None
            for p in kmod:
                xx = x_map(p['K']); yy = y_map(p['z'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)

            # legend — move to top-right of the plot box
            LEG_W, LEG_H = 220, 50
            x_leg = x1 - LEG_W - 10   # position near right margin
            y_leg = y1 + 10            # a bit above x-axis

            c.setFillColorRGB(1, 1, 1)
            c.rect(x_leg, y_leg, LEG_W, LEG_H, fill=1, stroke=1)

            # K0 (blue)
            c.setStrokeColorRGB(0.10, 0.46, 0.82)
            c.line(x_leg + 6, y_leg + 16, x_leg + 36, y_leg + 16)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(x_leg + 42, y_leg + 12, "Original (OCR=1; displ.=0)")

            # K modified (red)
            c.setStrokeColorRGB(0.83, 0.18, 0.18)
            c.line(x_leg + 6, y_leg + 34, x_leg + 36, y_leg + 34)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(x_leg + 42, y_leg + 30, "Modified (OCR & disp.)")


        # Charts: q(z) (PDF only — y inverted)
        c.showPage(); w, h = A4; x0 = 3*cm; x1 = w - 2*cm; y0 = h - 3*cm; y1 = 3*cm
        c.setFont("Helvetica-Bold", 10); c.drawString(2*cm, h - 2*cm, "Shaft resistance vs depth")

        slices = getattr(self, "_last_slices", [])
        if slices:
            z_vals = [s['z_mid'] for s in slices]; q_vals = [s['q_local'] for s in slices]
            zmin, zmax = 0.0, max(z_vals) if z_vals else 1.0
            auto_qmin, auto_qmax = (min(q_vals), max(q_vals)) if q_vals else (0.0, 1.0)
            qxmin, qxmax = self._parse_q_xlim()
            qmin = auto_qmin if qxmin is None else qxmin
            qmax = auto_qmax if qxmax is None else qxmax
            if qmin == qmax:
                qmin, qmax = qmin - 1.0, qmax + 1.0

            def x_map(q): return x0 + (q - qmin) / max(1e-12, (qmax - qmin)) * (x1 - x0)
            def y_map(z): return y0 - (z - zmin) / max(1e-12, (zmax - zmin)) * (y0 - y1)  # inverted

            # axes
            c.line(x0, y1, x0, y0); c.line(x0, y1, x1, y1)
            c.setFont("Helvetica", 8); c.drawString((x0 + x1) / 2, y1 - 10, "q_s (kPa)")
            c.saveState(); c.translate(x0 - 28, (y0 + y1) / 2); c.rotate(90); c.drawString(0, 0, "z (m)"); c.restoreState()

            # grid
            for qv in nice_ticks(qmin, qmax, n=6):
                x = x_map(qv); c.setStrokeColorRGB(0.85, 0.85, 0.85); c.line(x, y1, x, y0)
                c.setStrokeColorRGB(0, 0, 0); c.drawString(x - 12, y1 - 14, f"{qv:.0f}")
            for zv in nice_ticks(zmin, zmax, n=6):
                ytick = y_map(zv); c.setStrokeColorRGB(0.9, 0.9, 0.9); c.line(x0, ytick, x1, ytick)
                c.setStrokeColorRGB(0, 0, 0); c.drawRightString(x0 - 4, ytick - 3, f"{zv:.1f}")

            # curve
            c.setStrokeColorRGB(0.18, 0.49, 0.20); prev = None
            for s in slices:
                xx = x_map(s['q_local']); yy = y_map(s['z_mid'])
                if prev: c.line(prev[0], prev[1], xx, yy)
                prev = (xx, yy)

        c.save()
        try:
            webbrowser.open(path)
        except Exception:
            pass

if __name__ == "__main__":
    app = App()
    app.mainloop()