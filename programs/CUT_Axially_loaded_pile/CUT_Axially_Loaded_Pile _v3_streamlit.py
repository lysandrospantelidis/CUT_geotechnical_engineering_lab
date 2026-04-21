import math
import os
import io
import base64
from datetime import datetime

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

PROGRAM_NAME = "CUT Axially Loaded Pile (v3) — Streamlit"
ABOUT_TEXT = """CUT_Axially_Loaded_Pile
Version: v3 (Streamlit)
Author: Dr Lysandros Pantelidis, Cyprus University of Technology

Educational tool — no warranty. Use at your own risk. Free of charge."""
GAMMA_W = 9.81


def resource_path(relative_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


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


def phi_m_deg_fric(phi_deg, ah, kv):
    phi = rad(phi_deg)
    if abs(1.0 - kv) < 1e-12:
        return phi_deg
    tan_theta1 = 0.0 / (1.0 - kv)
    num = 1.0 - (1.0 - math.sin(phi)) * (1.0 + tan_theta1 * math.tan(phi))
    den = 1.0 + (1.0 - math.sin(phi)) ** 2 * (1.0 + tan_theta1 * math.tan(phi))
    x = clamp(num / den if den != 0 else 0.0, -1.0, 1.0)
    return math.degrees(math.asin(x))


def cbrt_complex(z):
    if isinstance(z, complex):
        r = abs(z)
        if r == 0:
            return 0.0
        theta = math.atan2(z.imag, z.real)
        return r ** (1.0 / 3.0) * complex(math.cos(theta / 3.0), math.sin(theta / 3.0))
    return z ** (1.0 / 3.0) if z >= 0 else -(-z) ** (1.0 / 3.0)


def _A0_B1_new(phi_deg, c, kv, sigma_v_eff, m, kh=0.0):
    phi = rad(phi_deg)
    s = math.sin(phi)
    t = math.tan(phi)
    if m is None:
        xi = 0.0
        xi2 = -1.0
    else:
        m = float(m)
        xi = (m - 1.0) / (m + 1.0) - 1.0
        xi2 = 2.0 / m - 1.0
    xi1 = 1.0 + xi
    ratio = (1.0 + s) / max(1e-12, (1.0 - s))
    A0 = (ratio ** xi1) * (1.0 + xi * s + xi2 * (kh / max(1e-12, 1.0 - kv)) * t * (2.0 + xi * (1.0 + s)))
    tan_p = math.tan(math.pi / 4.0 + phi / 2.0)
    tan_m = math.tan(math.pi / 4.0 - phi / 2.0)
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
        denom = 1.0 + sgn * math.sin(phim)
        return (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0

    tphi = math.tan(phi)
    if abs(B1) < 1e-18:
        phim_deg = phi_m_deg_fric(phi_deg, 0.0, kv)
        phim = rad(phim_deg)
        denom = 1.0 + sgn * math.sin(phim)
        return (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0

    e1 = (1.0 - A0) / B1
    e2 = (1.0 + A0) / (sgn * B1) + 2.0 * c / (max(1e-12, (1.0 - kv) * sigma_v_eff) * sgn * B1 * max(1e-12, tphi))

    a0 = 1.0 + (e2 ** 2) * (tphi ** 2)
    b0 = 1.0 - (2.0 * sgn * e1 * e2 + e2 ** 2) * (tphi ** 2)
    c0 = ((e1 ** 2) + 2.0 * sgn * e1 * e2) * (tphi ** 2)
    d0 = (-(e1 ** 2) * (tphi ** 2))

    D0 = b0 ** 2 - 3.0 * a0 * c0
    D1 = 2.0 * b0 ** 3 - 9.0 * a0 * b0 * c0 + 27.0 * a0 ** 2 * d0
    inside = D1 ** 2 - 4.0 * (D0 ** 3)
    IMSQRT = math.sqrt(inside) if inside >= 0 else complex(0.0, math.sqrt(-inside))
    D1_sqrt = (D1 - IMSQRT) / 2.0
    C0 = cbrt_complex(D1_sqrt)
    zeta = complex(-0.5, math.sqrt(3.0) / 2.0)
    zeta_lam_C0 = (zeta ** lam) * C0 if C0 != 0 else complex(0.0, 0.0)
    two_lam_1_over_3a0 = (-1.0 / (3.0 * sgn * a0)) if abs(a0) > 1e-18 else 0.0
    D0_over = (D0 / zeta_lam_C0) if zeta_lam_C0 != 0 else 0.0
    bo = b0 + zeta_lam_C0 + D0_over
    col = (bo.real * two_lam_1_over_3a0) if isinstance(bo, complex) else (bo * two_lam_1_over_3a0)
    col = clamp(col, -1.0, 1.0)
    phim = math.asin(col)

    cm_mob = c * math.tan(phim) / max(1e-12, tphi)
    denom = 1.0 + sgn * math.sin(phim)
    base = (1.0 - sgn * math.sin(phim)) / denom if abs(denom) > 1e-12 else 0.0
    corr = sgn * 2.0 * cm_mob * math.tan(math.pi / 4.0 - sgn * phim / 2.0) / (max(1e-12, sigma_v_eff) * max(1e-12, (1.0 - kv)))
    return base - corr


def koe_at_rest_pantelidis(z, c, phi_deg, gamma, kv, *, sigma_v_eff=None, m=1.0):
    if sigma_v_eff is None:
        sigma_v_eff = max(1e-8, gamma * max(z, 0.0))
    return _solve_K_general_with_A0B1(z, c, phi_deg, gamma, kv, m, sigma_v_eff)


def sigma_v_eff_at_depth(z, layers, gw_depth):
    if z <= 0:
        return 0.0
    sv = 0.0
    z_cursor = 0.0
    for L in layers:
        h = L["h"]
        dz = min(h, max(0.0, z - z_cursor))
        if dz <= 0:
            break
        top = z_cursor
        bot = z_cursor + dz
        above = max(0.0, min(bot, gw_depth) - top)
        below = dz - above
        sv += L["γ"] * above
        sv += max(0.0, L["γ"] - GAMMA_W) * below
        z_cursor += dz
        if z_cursor >= z:
            break
    return sv


def koe_displacement(z, H, L, gw_depth, kv, displacement_m, OCR, a_value, sigma_eff_z):
    K_base = max(0.0, koe_at_rest_pantelidis(z, L["c"], L["φ"], L["γ"], kv, sigma_v_eff=sigma_eff_z, m=1.0))
    z_over_H = max(1e-9, z / max(H, 1e-9))
    E = max(1e-9, L.get("E", 1e6))
    nu = clamp(L.get("ν", 0.3), -0.49, 0.49)
    bracket = (math.pi / 4.0) * ((1.0 - nu ** 2) / E) * (((1.0 + z_over_H) ** 3) * (1.0 - z_over_H) / z_over_H) * H * (1.0 - kv) * max(1e-9, sigma_eff_z)
    addon = displacement_m * (1.0 / bracket) if bracket > 0 else 0.0
    return max(0.0, K_base * (OCR ** a_value) + addon)


def split_layers_at_gwt(layers, gw_depth):
    if gw_depth is None or gw_depth <= 0:
        return layers[:]
    out = []
    z_top = 0.0
    for L in layers:
        h = float(L["h"])
        z_bot = z_top + h
        if z_top < gw_depth < z_bot:
            h_top = gw_depth - z_top
            h_bot = z_bot - gw_depth
            if h_top > 1e-6 and h_bot > 1e-6:
                L_top = dict(L)
                L_bot = dict(L)
                L_top["h"] = h_top
                L_bot["h"] = h_bot
                out.extend([L_top, L_bot])
            else:
                out.append(dict(L))
        else:
            out.append(dict(L))
        z_top = z_bot
    return out


def compute_shaft_resistance(params, layers):
    D = params["D"]
    kv = params["kv"]
    N = params["N"]
    pile_type = params["pile_type"]
    displacement_m = params["displacement_m"]
    gw_depth = params["gw_depth"]
    gammaR = params["γ_R"]
    axial_load = params["axial_load"]
    a_mode = params["a_mode"]
    a_const = params["a_const"]
    Rt_unfact = params["Rt_unfact"]

    H = sum(L["h"] for L in layers)
    perim = math.pi * D
    bounds = []
    z = 0.0
    for idx, L in enumerate(layers):
        bounds.append({"z0": z, "z1": z + L["h"], "L": L, "idx": idx})
        z += L["h"]

    def layer_at(zz):
        for b in bounds:
            if b["z0"] - 1e-9 <= zz <= b["z1"] + 1e-9:
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
        L = b["L"]
        idx = b["idx"]
        sigma_eff_z = sigma_v_eff_at_depth(z_mid, layers, gw_depth)

        K0 = max(0.0, koe_at_rest_pantelidis(z_mid, L["c"], L["φ"], L["γ"], kv, sigma_v_eff=sigma_eff_z, m=1.0))
        Kp_cap = max(0.0, koe_at_rest_pantelidis(z_mid, L["c"], L["φ"], L["γ"], kv, sigma_v_eff=sigma_eff_z, m=None))
        K0 = min(K0, Kp_cap)

        a_OCR = float(L.get("a_OCR", 1.0))
        b_OCR = float(L.get("b_OCR", 1.0))
        c_OCR = float(L.get("c_OCR", 1.0))
        z_eff = max(1e-6, z_mid)
        OCR = a_OCR * (z_eff ** (-b_OCR)) + c_OCR
        OCR = max(1.0, OCR)
        cap = params.get("OCR_cap", None)
        if cap is not None and cap > 0:
            OCR = min(OCR, cap)

        if pile_type == "Displacement" and (OCR > 1.0 + 1e-12 or displacement_m > 1e-12):
            a_val = math.sin(rad(L["φ"])) if a_mode == "sinφ" else a_const
            K_mod = koe_displacement(z_mid, H, L, gw_depth, kv, displacement_m, OCR, a_val, sigma_eff_z)
        else:
            K_mod = K0
        K_used = min(max(0.0, K_mod), Kp_cap)

        ko_curve_base.append({"z": z_mid, "K": K0})
        ko_curve_mod.append({"z": z_mid, "K": K_used})
        kp_curve.append({"z": z_mid, "K": Kp_cap})

        alpha_c = min(1.0, max(0.0, L.get("α_c", 1.0)))
        alpha_t = min(1.0, max(0.0, L.get("α_tanφ", 1.0)))
        q_local = (alpha_c * L["c"]) + K_used * (1.0 - kv) * sigma_eff_z * (alpha_t * math.tan(rad(L["φ"])))
        dQ = perim * (z_bot - z_top) * q_local

        Rs += dQ
        layer_kPa[idx] += q_local * (z_bot - z_top)
        layer_kN[idx] += dQ
        details.append({"z_mid": z_mid, "K": K_used, "Kp": Kp_cap, "q_local": q_local, "dQ": dQ, "OCR": OCR})

    Rs_fact = Rs / max(1e-12, gammaR)
    qs_fact = (Rs / max(1e-12, H)) / max(1e-12, gammaR)
    Rt_fact = Rt_unfact / max(1e-12, gammaR)
    R_total_fact = Rs_fact + Rt_fact
    safety_shaft = Rs_fact / max(1e-12, axial_load) if axial_load > 0 else float("inf")
    safety_total = R_total_fact / max(1e-12, axial_load) if axial_load > 0 else float("inf")

    per_layer_results = []
    for i, L in enumerate(layers):
        h = L["h"]
        avg_q_kPa = layer_kPa[i] / max(1e-12, h) if h > 0 else 0.0
        q_kPa_fact = avg_q_kPa / max(1e-12, gammaR)
        Q_kN_fact = layer_kN[i] / max(1e-12, gammaR)
        ratio = layer_kN[i] / max(1e-12, Rs) if Rs > 0 else 0.0
        per_layer_results.append({"idx": i + 1, "h": h, "q_kPa_fact": q_kPa_fact, "Q_kN_fact": Q_kN_fact, "ratio": ratio})

    return {
        "H": H,
        "Rs_fact": Rs_fact,
        "qs_fact": qs_fact,
        "per_layer_results": per_layer_results,
        "safety_shaft": safety_shaft,
        "Rt_fact": Rt_fact,
        "Rtot_fact": R_total_fact,
        "safety_total": safety_total,
        "details": details,
        "kbase": ko_curve_base,
        "kmod": ko_curve_mod,
        "kpcap": kp_curve,
        "layers_used": layers,
    }


def default_layers_df():
    return pd.DataFrame([{
        "Select": False,
        "#": 1,
        "h": 12.0,
        "c": 20.0,
        "φ": 30.0,
        "γ": 19.0,
        "a_OCR": 1.0,
        "b_OCR": 1.0,
        "c_OCR": 1.0,
        "α_c": 1.0,
        "α_tanφ": 1.0,
        "E": 30000.0,
        "ν": 0.3,
    }])


def dataframe_to_layers(df, apply_all=False, alpha_c_all=1.0, alpha_t_all=1.0):
    cols = ["h", "c", "φ", "γ", "a_OCR", "b_OCR", "c_OCR", "α_c", "α_tanφ", "E", "ν"]
    out = []
    for _, row in df.iterrows():
        L = {}
        for c in cols:
            try:
                val = float(row[c])
            except Exception:
                val = 0.0
            L[c] = val
        if apply_all:
            L["α_c"] = alpha_c_all
            L["α_tanφ"] = alpha_t_all
        L["α_c"] = clamp(L["α_c"], 0.0, 1.0)
        L["α_tanφ"] = clamp(L["α_tanφ"], 0.0, 1.0)
        out.append(L)
    return out


def slices_dataframe(results):
    return pd.DataFrame(results["details"])[["z_mid", "K", "Kp", "q_local", "dQ", "OCR"]]


def per_layer_dataframe(results):
    return pd.DataFrame(results["per_layer_results"])


def build_excel_bytes(df):
    try:
        import openpyxl  # noqa: F401
    except Exception:
        return None

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Slices")
    bio.seek(0)
    return bio.getvalue()


def add_home_logo():
    path = resource_path("home.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f'''<a href="https://cut-apps.streamlit.app/" target="_blank"><img src="data:image/png;base64,{b64}" width="95"></a>''',
            unsafe_allow_html=True,
        )
    else:
        st.link_button("Home", "https://cut-apps.streamlit.app/")


def plot_k_chart(results, xmin=None, xmax=None):
    kbase = results["kbase"]
    kmod = results["kmod"]
    kpcap = results["kpcap"]
    z_vals = [p["z"] for p in kbase]
    k_vals = [p["K"] for p in kbase] + [p["K"] for p in kmod] + [p["K"] for p in kpcap]
    kmin = min(k_vals) if xmin is None else xmin
    kmax = max(k_vals) if xmax is None else xmax
    if kmax <= kmin:
        kmax = kmin + 1.0
    fig, ax = plt.subplots(figsize=(6, 7))
    ax.plot([p["K"] for p in kbase], [p["z"] for p in kbase], label="K0 (m=1)")
    ax.plot([p["K"] for p in kmod], [p["z"] for p in kmod], label="K (modified, capped)")
    ax.plot([p["K"] for p in kpcap], [p["z"] for p in kpcap], label="Kp (m→∞)")
    ax.set_xlabel("K")
    ax.set_ylabel("z (m)")
    ax.set_xlim(kmin, kmax)
    ax.set_ylim(0, max(z_vals) if z_vals else 1)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_q_chart(results, xmin=None, xmax=None):
    data = results["details"]
    z_vals = [s["z_mid"] for s in data]
    q_vals = [s["q_local"] for s in data]
    qmin = min(q_vals) if xmin is None else xmin
    qmax = max(q_vals) if xmax is None else xmax
    if qmax <= qmin:
        qmax = qmin + 1.0
    fig, ax = plt.subplots(figsize=(6, 7))
    ax.plot(q_vals, z_vals, label="q_s")
    ax.set_xlabel("q_s (kPa)")
    ax.set_ylabel("z (m)")
    ax.set_xlim(qmin, qmax)
    ax.set_ylim(0, max(z_vals) if z_vals else 1)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_ocr_chart(layers, H, ocr_cap=None, xmin=None, xmax=None):
    z_vals = []
    dz = max(0.02, H / 300.0)
    z = 0.0
    while z <= H + 1e-9:
        z_vals.append(z)
        z += dz

    def layer_for(zm):
        zt = 0.0
        for L in layers:
            zb = zt + L["h"]
            if zm <= zb + 1e-9:
                return L
            zt = zb
        return layers[-1]

    o_vals = []
    for z in z_vals:
        L = layer_for(z if z > 1e-9 else 1e-6)
        val = float(L.get("a_OCR", 1.0)) * (max(1e-6, z) ** (-float(L.get("b_OCR", 1.0)))) + float(L.get("c_OCR", 1.0))
        if ocr_cap is not None and ocr_cap > 0:
            val = min(val, ocr_cap)
        o_vals.append(val)

    omin = min(o_vals) if xmin is None else xmin
    omax = max(o_vals) if xmax is None else xmax
    if omax <= omin:
        omax = omin + 1.0
    fig, ax = plt.subplots(figsize=(6, 7))
    ax.plot(o_vals, z_vals, label=r"OCR(z)=a_OCR z^{-b_OCR}+c_OCR")
    ax.set_xlabel("OCR")
    ax.set_ylabel("z (m)")
    ax.set_xlim(omin, omax)
    ax.set_ylim(0, H)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_pile_visualization(results, params):
    layers = results["layers_used"]
    H = results["H"]
    gw = params["gw_depth"]
    D = params["D"]
    pile_type = params["pile_type"]
    kv = params["kv"]
    Vk = params["axial_load"]
    Rt_nf = params["Rt_unfact"]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 10)
    ax.set_ylim(H + 1.5, -1.5)
    ax.axhspan(-1.5, 0, facecolor="#f8f8f8")
    ax.axhspan(0, H + 1.5, facecolor="#f3efe8")
    if gw < H:
        ax.axhspan(gw, H + 1.5, facecolor="#e0f2ff")
        ax.axhline(gw, linewidth=2)
        ax.text(9.7, gw - 0.15, f"GWT = {gw:.2f} m", ha="right", va="bottom")

    x0, x1 = 2.8, 3.8
    ax.add_patch(plt.Rectangle((x0, 0), x1 - x0, H, fill=True, edgecolor="#666", facecolor="#ddd"))
    ax.annotate("", xy=((x0 + x1) / 2, 0), xytext=((x0 + x1) / 2, -1.0), arrowprops=dict(arrowstyle="->", lw=2))
    ax.text((x0 + x1) / 2 - 0.2, -1.15, f"Axial load, V_k = {Vk:.1f} kN", ha="right", va="center")
    ax.annotate("", xy=((x0 + x1) / 2, H), xytext=((x0 + x1) / 2, H + 1.0), arrowprops=dict(arrowstyle="->", lw=2))
    ax.text((x0 + x1) / 2 + 0.2, H + 1.1, f"Tip resistance, R_t = {Rt_nf:.1f} kN", ha="left", va="center")

    zc = 0.0
    for i, L in enumerate(layers, 1):
        zc_next = zc + L["h"]
        ax.axhline(zc_next, color="#bbb", linestyle="--", linewidth=1)
        txt = (
            f"Layer {i}: h={L['h']:.2f} m\n"
            f"c={L['c']:.2f} kPa, φ={L['φ']:.1f} deg\n"
            f"γ={L['γ']:.2f} kN/m³, a_OCR={L['a_OCR']:.3f}, b_OCR={L['b_OCR']:.3f}, c_OCR={L['c_OCR']:.3f}\n"
            f"α_c={L['α_c']:.2f}, α_tanφ={L['α_tanφ']:.2f}, E={L['E']:.0f} kPa, ν={L['ν']:.2f}"
        )
        ax.text(4.3, (zc + zc_next) / 2, txt, va="center")
        zc = zc_next

    ax.text(5.0, -1.3, f"Pile type: {pile_type}    k_v={kv:.3f}    GWT={gw:.2f} m", ha="center", weight="bold")
    ax.text((x0 + x1) / 2, 0.25, f"D = {D:.2f} m", ha="center")
    ax.text((x0 + x1) / 2, H + 0.3, f"H = {H:.2f} m", ha="center")
    ax.set_xticks([])
    ax.set_ylabel("z (m)")
    for spine in ["top", "right", "bottom"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


def build_pdf_bytes(results, params, slices_df, per_layer_df):
    if not REPORTLAB_AVAILABLE:
        return None
    bio = io.BytesIO()
    c = rl_canvas.Canvas(bio, pagesize=A4)
    W, H = A4
    margin = 20 * mm

    def header(title):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, H - margin, "CUT Axially Loaded Pile Report")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - margin, H - margin, datetime.now().strftime("%Y-%m-%d %H:%M"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, H - margin - 10 * mm, title)

    header("Summary")
    y = H - margin - 20 * mm
    c.setFont("Helvetica", 9)
    lines = [
        f"Pile type: {params['pile_type']}",
        f"D = {params['D']:.3f} m",
        f"k_v = {params['kv']:.3f}",
        f"GWT depth = {params['gw_depth']:.3f} m",
        f"Displacement = {params['displacement_m']:.4f} m",
        f"γ_R = {params['γ_R']:.3f}",
        f"Axial load = {params['axial_load']:.3f} kN",
        f"Tip resistance, R_t (NON-factored) = {params['Rt_unfact']:.3f} kN",
        f"R_s (factored) = {results['Rs_fact']:.3f} kN",
        f"q_s,tot (factored) = {results['qs_fact']:.3f} kPa",
        f"R_t (factored) = {results['Rt_fact']:.3f} kN",
        f"R_tot (factored) = {results['Rtot_fact']:.3f} kN",
        f"Safety (shaft only) = {results['safety_shaft']:.3f}",
        f"Safety (total) = {results['safety_total']:.3f}",
    ]
    for line in lines:
        c.drawString(margin, y, line)
        y -= 5 * mm

    c.showPage()
    header("Per-layer (factored)")
    y = H - margin - 20 * mm
    c.setFont("Helvetica-Bold", 8)
    cols = ["Layer", "h (m)", "q (kPa)", "Q (kN)", "Q_layer / V_d"]
    xs = [margin, margin + 22 * mm, margin + 50 * mm, margin + 85 * mm, margin + 120 * mm]
    for x, col in zip(xs, cols):
        c.drawString(x, y, col)
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    for _, row in per_layer_df.iterrows():
        vals = [f"{int(row['idx'])}", f"{row['h']:.3f}", f"{row['q_kPa_fact']:.3f}", f"{row['Q_kN_fact']:.3f}", f"{row['ratio']:.3f}"]
        for x, val in zip(xs, vals):
            c.drawString(x, y, val)
        y -= 4.5 * mm
        if y < 20 * mm:
            c.showPage()
            header("Per-layer (factored) cont.")
            y = H - margin - 20 * mm
            c.setFont("Helvetica", 8)

    c.showPage()
    header("Slices")
    y = H - margin - 20 * mm
    c.setFont("Helvetica-Bold", 8)
    cols = ["z (m)", "K", "Kp", "q (kPa)", "dQ (kN)", "OCR"]
    xs = [margin, margin + 25 * mm, margin + 50 * mm, margin + 75 * mm, margin + 110 * mm, margin + 145 * mm]
    for x, col in zip(xs, cols):
        c.drawString(x, y, col)
    y -= 5 * mm
    c.setFont("Helvetica", 7.5)
    for _, row in slices_df.iterrows():
        vals = [f"{row['z_mid']:.3f}", f"{row['K']:.4f}", f"{row['Kp']:.4f}", f"{row['q_local']:.2f}", f"{row['dQ']:.2f}", f"{row['OCR']:.3f}"]
        for x, val in zip(xs, vals):
            c.drawString(x, y, val)
        y -= 4.0 * mm
        if y < 20 * mm:
            c.showPage()
            header("Slices cont.")
            y = H - margin - 20 * mm
            c.setFont("Helvetica", 7.5)

    c.save()
    bio.seek(0)
    return bio.getvalue()


st.set_page_config(page_title=PROGRAM_NAME, layout="wide")
st.title(PROGRAM_NAME)

top1, top2, top3, top4 = st.columns([1.0, 1.6, 1.6, 1.0])
with top1:
    add_home_logo()
with top2:
    manual_path = resource_path("CUT_Axially_Loaded_Pile_User_Manual.pdf")
    if os.path.exists(manual_path):
        with open(manual_path, "rb") as f:
            st.download_button("Theory and user manual", f.read(), file_name="CUT_Axially_Loaded_Pile_User_Manual.pdf", use_container_width=True)
    else:
        st.button("Theory and user manual", disabled=True, use_container_width=True)
with top3:
    st.empty()
with top4:
    with st.popover("About", use_container_width=True):
        st.text(ABOUT_TEXT)

if "layers_df" not in st.session_state:
    st.session_state.layers_df = default_layers_df()

left, right = st.columns([1.05, 1.2])
with left:
    st.subheader("Inputs")
    with st.expander("General", expanded=True):
        g1, g2, g3 = st.columns(3)
        kv = g1.number_input("k_v (seismic)", value=0.0, step=0.01, format="%.4f")
        N = g2.number_input("Discretization", value=400, step=1, min_value=20)
        gw = g3.number_input("Groundwater table (GWT) depth (m)", value=2.0, step=0.1, format="%.4f")

    with st.expander("Pile data", expanded=True):
        p1, p2 = st.columns([1.4, 1])
        pile_type = p1.selectbox("Pile type", ["Non-displacement", "Displacement"])
        D = p2.number_input("Diameter D (m)", value=1.0, min_value=1e-6, step=0.1, format="%.4f")
        p3, p4, p5 = st.columns([1.4, 1, 1])
        displacement_m = p3.number_input("Displacement (m) (e.g. D/2 for solid pile)", value=0.0, step=0.01, format="%.4f")
        a_mode = p4.selectbox("a mode (OCR^a)", ["constant", "sinφ"])
        a_const = p5.number_input("a (constant)", value=0.5, step=0.01, format="%.4f")
        ocr_cap_txt = st.text_input("OCR cap", value="")

    with st.expander("Factors & Loads", expanded=True):
        f1, f2, f3 = st.columns(3)
        gammaR = f1.number_input("Resistance factor γ_R", value=1.0, min_value=1e-9, step=0.05, format="%.4f")
        axial_load = f2.number_input("Axial pile load, V_k or V_d (kN)", value=1000.0, step=1.0, format="%.4f")
        Rt_unfact = f3.number_input("Tip resistance Rt (kN) NON-factored", value=0.0, step=1.0, format="%.4f")
        st.caption("Note: If a resistance factor is used, the axial load should also be the factored value (V_d).")

    st.subheader("Layers (top to bottom) — H is auto = sum(h)")
    c1, c2, c3, c4 = st.columns([1.7, 0.8, 0.8, 1])
    apply_src_all = c1.checkbox("Apply the same interface reduction factor to all layers", value=False)
    alpha_c_all = c2.number_input("α_c", value=1.0, min_value=0.0, max_value=1.0, step=0.05, format="%.4f")
    alpha_tanphi_all = c3.number_input("α_tanφ", value=1.0, min_value=0.0, max_value=1.0, step=0.05, format="%.4f")
    add_row = c4.button("Add layer", use_container_width=True)
    d1, d2 = st.columns([1, 1])
    delete_selected = d2.button("Delete selected layer(s)", use_container_width=True)

    if add_row:
        df = st.session_state.layers_df.copy()
        next_idx = len(df) + 1
        new_row = pd.DataFrame([{
            "Select": False,
            "#": next_idx,
            "h": 1.0,
            "c": 0.0,
            "φ": 30.0,
            "γ": 19.0,
            "a_OCR": 1.0,
            "b_OCR": 1.0,
            "c_OCR": 1.0,
            "α_c": 1.0,
            "α_tanφ": 1.0,
            "E": 30000.0,
            "ν": 0.3
        }])
        st.session_state.layers_df = pd.concat([df, new_row], ignore_index=True)

    if delete_selected:
        df = st.session_state.layers_df

        # Keep only rows NOT selected
        df = df[df["Select"] == False].copy()

        # Ensure at least one layer remains
        if df.empty:
            df = default_layers_df()

        # 🔹 RESET all checkboxes
        df["Select"] = False

        df["#"] = range(1, len(df) + 1)
        st.session_state.layers_df = df

    edited_df = st.data_editor(
        st.session_state.layers_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Select": st.column_config.CheckboxColumn("Select"),
            "#": st.column_config.NumberColumn("#", disabled=True),
            "h": st.column_config.NumberColumn("h", format="%.4f"),
            "c": st.column_config.NumberColumn("c", format="%.4f"),
            "φ": st.column_config.NumberColumn("φ", format="%.4f"),
            "γ": st.column_config.NumberColumn("γ or γsat", format="%.4f"),
            "a_OCR": st.column_config.NumberColumn("a_OCR", format="%.4f"),
            "b_OCR": st.column_config.NumberColumn("b_OCR", format="%.4f"),
            "c_OCR": st.column_config.NumberColumn("c_OCR", format="%.4f"),
            "α_c": st.column_config.NumberColumn("α_c", format="%.4f"),
            "α_tanφ": st.column_config.NumberColumn("α_tanφ", format="%.4f"),
            "E": st.column_config.NumberColumn("E", format="%.4f"),
            "ν": st.column_config.NumberColumn("ν", format="%.4f"),
        },
    )

    edited_df["#"] = range(1, len(edited_df) + 1)
    st.session_state.layers_df = edited_df
    st.button("Run", type="primary", use_container_width=True)

layers = dataframe_to_layers(st.session_state.layers_df, apply_src_all, alpha_c_all, alpha_tanphi_all)
layers = split_layers_at_gwt(layers, gw)
if a_mode == "constant" and a_const > 1.0:
    st.error("The exponent a must be <= 1. Please enter a value <= 1.")
    st.stop()
try:
    ocr_cap = float(ocr_cap_txt.strip()) if ocr_cap_txt.strip() else None
except Exception:
    st.error("OCR cap must be numeric or blank.")
    st.stop()

params = {"D": D, "kv": float(kv), "N": int(N), "pile_type": pile_type, "displacement_m": float(displacement_m), "gw_depth": float(gw), "γ_R": float(gammaR), "axial_load": float(axial_load), "a_mode": a_mode, "a_const": float(a_const), "Rt_unfact": float(Rt_unfact), "OCR_cap": ocr_cap}
results = compute_shaft_resistance(params, layers)
slices_df = slices_dataframe(results)
per_layer_df = per_layer_dataframe(results)

with right:
    st.subheader("Outputs")
    m1, m2, m3 = st.columns(3)
    m1.metric("Shaft resistance (factored), Rs", f"{results['Rs_fact']:,.2f} kN")
    m2.metric("Average unit shaft (factored), qs_tot", f"{results['qs_fact']:,.2f} kPa")
    m3.metric("Safety (shaft only)", f"{results['safety_shaft']:,.3f}")
    m4, m5, m6 = st.columns(3)
    m4.metric("Tip resistance (factored), Rt", f"{results['Rt_fact']:,.2f} kN")
    m5.metric("Total pile resistance (factored), Rtot", f"{results['Rtot_fact']:,.2f} kN")
    m6.metric("Safety (total)", f"{results['safety_total']:,.3f}")

    t1, t2, t3, t4, t5 = st.tabs(["Visualization - Pile", "Visualization - OCR vs depth", "K vs depth", "Shaft resistance vs depth", "Tables"])
    with t1:
        st.pyplot(plot_pile_visualization(results, params), use_container_width=True)
    with t2:
        o1, o2 = st.columns(2)
        ocr_xmin_raw = o1.text_input("OCR x-min", value="")
        ocr_xmax_raw = o2.text_input("OCR x-max", value="10")
        try:
            ocr_xmin = float(ocr_xmin_raw) if ocr_xmin_raw.strip() else None
            ocr_xmax = float(ocr_xmax_raw) if ocr_xmax_raw.strip() else None
        except Exception:
            ocr_xmin, ocr_xmax = None, None
        st.pyplot(plot_ocr_chart(results["layers_used"], results["H"], ocr_cap=ocr_cap, xmin=ocr_xmin, xmax=ocr_xmax), use_container_width=True)
    with t3:
        k1, k2 = st.columns(2)
        kxmin_raw = k1.text_input("K0 x-axis min (blank=auto)", value="")
        kxmax_raw = k2.text_input("K0 x-axis max (blank=auto)", value="")
        try:
            kxmin = float(kxmin_raw) if kxmin_raw.strip() else None
            kxmax = float(kxmax_raw) if kxmax_raw.strip() else None
        except Exception:
            kxmin, kxmax = None, None
        st.pyplot(plot_k_chart(results, xmin=kxmin, xmax=kxmax), use_container_width=True)
    with t4:
        q1, q2 = st.columns(2)
        qxmin_raw = q1.text_input("q_s x-axis min (blank=auto)", value="")
        qxmax_raw = q2.text_input("q_s x-axis max (blank=auto)", value="")
        try:
            qxmin = float(qxmin_raw) if qxmin_raw.strip() else None
            qxmax = float(qxmax_raw) if qxmax_raw.strip() else None
        except Exception:
            qxmin, qxmax = None, None
        st.pyplot(plot_q_chart(results, xmin=qxmin, xmax=qxmax), use_container_width=True)
    with t5:
        st.markdown("**Slices (point-level)**")
        st.dataframe(slices_df, use_container_width=True)
        st.markdown("**Per-layer (factored)**")
        st.dataframe(per_layer_df, use_container_width=True)
        excel_bytes = build_excel_bytes(slices_df)
        if excel_bytes is not None:
            st.download_button(
                "Export Slices (Excel)",
                data=excel_bytes,
                file_name=f"CUT_Axially_Loaded_Pile_Slices_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Install openpyxl to enable Excel export.")
        if pdf_bytes is not None:
            st.download_button("Export Report (PDF)", data=pdf_bytes, file_name=f"CUT_Axially_Loaded_Pile_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf", mime="application/pdf")
        else:
            st.info("Install reportlab to enable PDF export in the Streamlit version.")

st.caption("Streamlit version generated from the uploaded Tkinter application logic.")
