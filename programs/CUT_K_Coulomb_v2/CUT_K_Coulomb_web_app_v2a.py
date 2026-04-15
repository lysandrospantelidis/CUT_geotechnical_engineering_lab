from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

PROGRAM_NAME = "CUT_K_Coulomb"
VERSION = "v2.1.0 (Web)"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"

BASE_DIR = Path(__file__).resolve().parent
HOME_LOGO_FILE = BASE_DIR / "home.png"
LOGO_FILE = BASE_DIR / "cut_logo.png"
HOME_URL = "https://cut-apps.streamlit.app/"

ABOUT_TEXT = """CUT_K_Coulomb
Version: v1.1.0 (Web)
Author: Dr Lysandros Pantelidis, Cyprus University of Technology

Educational tool — no warranty. Use at your own risk. Free of charge."""

Point = Tuple[float, float]


class GeometryError(ValueError):
    pass


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
            <a href="{url}" target="_blank" style="display:inline-block; width:100%; max-width:110px; padding:6px; border:1px solid #cfd8e3; border-radius:12px; background:#ffffff; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <img src="{data_uri}" alt="CUT Apps Home" style="width:100%; height:auto; border-radius:8px; display:block;">
            </a>
        </div>
        """
        st.markdown(html_block, unsafe_allow_html=True)
    else:
        st.link_button("🏠 CUT Apps Home", url, use_container_width=True)


def wall_base_point(H: float, alpha_deg: float) -> Point:
    alpha = math.radians(alpha_deg)
    return (H * math.tan(alpha), -H)


def _line_intersection_from_base(base: Point, beta: float, p1: Point, p2: Point) -> Optional[Point]:
    xb, yb = base
    m = math.tan(beta)

    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    denom = dy - m * dx
    if abs(denom) < 1e-14:
        return None

    t = (yb - m * xb + m * x1 - y1) / denom
    if 0.0 <= t <= 1.0:
        xi, yi = x1 + t * dx, y1 + t * dy
        if xi > xb + 1e-9:
            return (xi, yi)
    return None


def _polygon_area(points: List[Point]) -> float:
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(0.5 * a)


def _build_wedge(H: float, alpha_deg: float, surface: List[Point], beta: float):
    base = wall_base_point(H, alpha_deg)
    poly = [(0.0, 0.0), base]
    hit = None

    for i in range(len(surface) - 1):
        inter = _line_intersection_from_base(base, beta, surface[i], surface[i + 1])
        if inter is not None:
            hit = inter
            poly.append(hit)
            poly.extend(reversed(surface[: i + 1]))
            break

    if hit is None:
        return None, 0.0

    if poly[-1] != (0.0, 0.0):
        poly.append((0.0, 0.0))

    area = _polygon_area(poly)
    if area <= 1e-12:
        return None, 0.0

    return poly, hit[0]


def _Ka_trial(H: float, area: float, beta: float, phi_deg: float,
              alpha_deg: float, delta_deg: float):
    phi = math.radians(phi_deg)
    alpha = math.radians(alpha_deg)
    delta = math.radians(delta_deg)

    num = math.sin(beta - phi)
    den = math.cos(alpha + delta - beta + phi)

    if not math.isfinite(num) or not math.isfinite(den):
        return None
    if num <= 0.0 or den <= 0.0 or abs(den) < 1e-12:
        return None

    return (2.0 * area / (H * H)) * (num / den)


def _Kp_trial(H: float, area: float, beta: float, phi_deg: float,
              alpha_deg: float, delta_deg: float):
    phi = math.radians(phi_deg)
    alpha = math.radians(alpha_deg)
    delta = math.radians(delta_deg)

    num = math.sin(beta + phi)
    den = math.cos(alpha - delta - beta - phi)

    if not math.isfinite(num) or not math.isfinite(den):
        return None
    if num <= 0.0 or den <= 0.0 or abs(den) < 1e-12:
        return None

    return (2.0 * area / (H * H)) * (num / den)


def _sweep_beta(phi_deg: float, H: float, alpha_deg: float, delta_deg: float,
                surface: List[Point], mode: str, n_steps: int):
    beta_min = math.radians(0.1)
    beta_max = math.radians(89.5)

    best_beta = None
    best_K = None

    for i in range(1, n_steps):
        beta = beta_min + (beta_max - beta_min) * i / n_steps

        poly, _ = _build_wedge(H, alpha_deg, surface, beta)
        if poly is None:
            continue

        area = _polygon_area(poly)
        if area <= 0.0:
            continue

        if mode == "active":
            K = _Ka_trial(H, area, beta, phi_deg, alpha_deg, delta_deg)
            if K is None:
                continue
            if best_K is None or K > best_K:
                best_beta, best_K = beta, K
        else:
            K = _Kp_trial(H, area, beta, phi_deg, alpha_deg, delta_deg)
            if K is None:
                continue
            if best_K is None or K < best_K:
                best_beta, best_K = beta, K

    if best_K is None:
        raise GeometryError("No feasible wedge found for these inputs.")

    return best_beta, best_K


def coulomb_top_origin(phi_deg: float, H: float, alpha_deg: float, delta_deg: float,
                       surface_pts: List[Point], n_steps: int, mode: str):
    if not (0.0 < phi_deg < 90.0):
        raise ValueError("φ must be between 0 and 90 degrees.")
    if H <= 0.0:
        raise ValueError("H must be positive.")
    if len(surface_pts) < 2:
        raise ValueError("Provide at least two surface points.")
    if abs(surface_pts[0][0]) > 1e-12 or abs(surface_pts[0][1]) > 1e-12:
        raise ValueError("Point 0 must be exactly at (0, 0).")

    for (x1, _), (x2, _) in zip(surface_pts, surface_pts[1:]):
        if x2 < x1 - 1e-12:
            raise ValueError("x must be non-decreasing from Point 0 outward.")

    beta_opt, K_opt = _sweep_beta(phi_deg, H, alpha_deg, delta_deg, surface_pts, mode, n_steps)
    return dict(beta_deg=math.degrees(beta_opt), K=K_opt)


def collect_points(df: pd.DataFrame) -> List[Point]:
    pts: List[Point] = []
    for _, row in df.iterrows():
        pts.append((float(row["x"]), float(row["y"])))
    if len(pts) == 0 or abs(pts[0][0]) > 1e-12 or abs(pts[0][1]) > 1e-12:
        raise ValueError("Point 0 must be exactly at (0, 0).")
    for (x1, _), (x2, _) in zip(pts, pts[1:]):
        if x2 < x1 - 1e-12:
            raise ValueError("x must be non-decreasing from Point 0 outward.")
    return pts


def make_plot(surface: List[Point], H: float, alpha_deg: float, beta_deg: float):
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    xb, yb = wall_base_point(H, alpha_deg)
    xs_plot = [p[0] for p in surface]
    ys_plot = [p[1] for p in surface]

    ax.plot([0.0, xb], [0.0, yb], lw=2.0)
    ax.plot(xs_plot, ys_plot, marker="o")

    beta_rad = math.radians(beta_deg)
    xa = np.linspace(xb, max(xs_plot) if xs_plot else max(1.0, xb + 1.0), 200)
    ya = yb + np.tan(beta_rad) * (xa - xb)
    ax.plot(xa, ya, ls="--")

    poly, _ = _build_wedge(H, alpha_deg, surface, beta_rad)
    if poly:
        ax.fill([p[0] for p in poly], [p[1] for p in poly], alpha=0.18)

    xmax = max(1.0, max(xs_plot) * 1.2 if xs_plot else 1.0, xb * 1.2 if xb > 0 else 1.0)
    xmin = min(-0.5, xb - 0.5)
    ymax = max(1.0, max([0.0] + ys_plot) * 1.4 if ys_plot else 1.0)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-H * 1.15, ymax)
    ax.set_xlabel("x (m) →")
    ax.set_ylabel("y (m) ↑   (top at 0)")
    ax.grid(True, alpha=0.3)
    return fig


def init_points_df() -> None:
    if "points_df" not in st.session_state:
        st.session_state.points_df = pd.DataFrame(
            {
                "Select": [False, False, False],
                "Point": ["Point 0", "Point 1", "Point 2"],
                "x": [0.0, 5.0, 10.0],
                "y": [0.0, 0.5, 0.8],
            }
        )


def normalize_points_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Select" not in df.columns:
        df.insert(0, "Select", False)
    if "Point" not in df.columns:
        df.insert(1, "Point", [f"Point {i}" for i in range(len(df))])

    df = df[["Select", "Point", "x", "y"]]

    if len(df) == 0:
        df.loc[0] = [False, "Point 0", 0.0, 0.0]

    df.iloc[0, df.columns.get_loc("Select")] = False
    df.iloc[0, df.columns.get_loc("x")] = 0.0
    df.iloc[0, df.columns.get_loc("y")] = 0.0

    for i in range(len(df)):
        df.iloc[i, df.columns.get_loc("Point")] = f"Point {i}"

    return df.reset_index(drop=True)


def sync_points_from_widgets() -> None:
    df = normalize_points_df(st.session_state.points_df)
    rows = []
    for i in range(len(df)):
        sel = bool(st.session_state.get(f"pt_sel_{i}", False))
        x = float(st.session_state.get(f"pt_x_{i}", df.loc[i, "x"]))
        y = float(st.session_state.get(f"pt_y_{i}", df.loc[i, "y"]))
        if i == 0:
            sel = False
            x = 0.0
            y = 0.0
        rows.append({"Select": sel, "Point": f"Point {i}", "x": x, "y": y})
    st.session_state.points_df = normalize_points_df(pd.DataFrame(rows))


def init_point_widgets() -> None:
    df = normalize_points_df(st.session_state.points_df)
    for i in range(len(df)):
        if f"pt_sel_{i}" not in st.session_state:
            st.session_state[f"pt_sel_{i}"] = bool(df.loc[i, "Select"])
        if f"pt_x_{i}" not in st.session_state:
            st.session_state[f"pt_x_{i}"] = float(df.loc[i, "x"])
        if f"pt_y_{i}" not in st.session_state:
            st.session_state[f"pt_y_{i}"] = float(df.loc[i, "y"])


def cleanup_point_widgets() -> None:
    df = normalize_points_df(st.session_state.points_df)
    keep = {f"pt_sel_{i}" for i in range(len(df))} | {f"pt_x_{i}" for i in range(len(df))} | {f"pt_y_{i}" for i in range(len(df))}
    for key in list(st.session_state.keys()):
        if key.startswith("pt_sel_") or key.startswith("pt_x_") or key.startswith("pt_y_"):
            if key not in keep:
                del st.session_state[key]


def add_point() -> None:
    sync_points_from_widgets()
    df = normalize_points_df(st.session_state.points_df)
    idx = len(df)
    new_x = float(df["x"].iloc[-1] + 1.0)
    new_y = float(df["y"].iloc[-1])
    df.loc[len(df)] = [False, f"Point {idx}", new_x, new_y]
    st.session_state.points_df = normalize_points_df(df)
    cleanup_point_widgets()


def remove_selected_points() -> None:
    sync_points_from_widgets()
    df = normalize_points_df(st.session_state.points_df)
    if len(df) <= 1:
        return

    keep_rows = [0]
    for i in range(1, len(df)):
        if not bool(df.loc[i, "Select"]):
            keep_rows.append(i)

    df = df.loc[keep_rows].reset_index(drop=True)
    st.session_state.points_df = normalize_points_df(df)
    cleanup_point_widgets()


def compute_and_store(mode: str, phi: float, H: float, alpha: float, delta_w: float, n_steps: int) -> None:
    df = normalize_points_df(st.session_state.points_df)
    surface = collect_points(df[["x", "y"]])
    result = coulomb_top_origin(
        phi_deg=float(phi),
        H=float(H),
        alpha_deg=float(alpha),
        delta_deg=float(delta_w),
        surface_pts=surface,
        n_steps=int(n_steps),
        mode=mode,
    )
    st.session_state["last_result"] = {
        "mode": mode,
        "phi": float(phi),
        "H": float(H),
        "alpha": float(alpha),
        "delta_w": float(delta_w),
        "n_steps": int(n_steps),
        "surface": surface,
        "result": result,
    }
    st.session_state.pop("last_error", None)


st.set_page_config(page_title=PROGRAM_NAME, layout="wide")

st.markdown(
    """
    <style>
    div.stButton > button {
        min-height: 52px !important;
        height: 52px !important;
        border-radius: 12px !important;
        white-space: nowrap !important;
        font-weight: 600 !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #c62828 !important;
        border-color: #c62828 !important;
        color: white !important;
        font-weight: 700 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #b71c1c !important;
        border-color: #b71c1c !important;
        color: white !important;
    }
    div[data-testid="stNumberInput"] button {display:none !important;}
    div[data-testid="stNumberInput"] input {text-align:left;}
    div[data-testid="stCheckbox"] {max-width: 100%;}
    .toolbar-home-wrap {
        padding-top: 0px;
    }
    .toolbar-home-btn {
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        height:52px;
        border:1px solid #cfd8e3;
        border-radius:12px;
        background:#ffffff;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
        text-decoration:none;
    }
    .toolbar-home-img {
        width: 90%;
        height: 90%;
        object-fit: contain;
        display:block;
    }
    .point-card {
        border: 1px solid #d9dce3;
        border-radius: 10px;
        padding: 8px 10px 2px 10px;
        margin-bottom: 10px;
        background: #fafbfc;
    }
    .point-card-title {
        font-weight: 700;
        margin-bottom: 0.15rem;
    }
    .toolbar-title-space { margin-bottom: 0.35rem; }
    @media (max-width: 900px) {
        div[data-testid="stNumberInput"], div[data-testid="stSelectbox"] {max-width: 100% !important;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
    div.stButton > button {
        min-height: 52px !important;
        height: 52px !important;
        border-radius: 12px !important;
        white-space: nowrap !important;
        font-weight: 600 !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #c62828 !important;
        border-color: #c62828 !important;
        color: white !important;
        font-weight: 700 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #b71c1c !important;
        border-color: #b71c1c !important;
        color: white !important;
    }
    div[data-testid="stNumberInput"] button {display:none !important;}
    div[data-testid="stNumberInput"] input {text-align:left;}
    div[data-testid="stCheckbox"] {max-width: 100%;}
    .toolbar-home-wrap {
        padding-top: 0px;
    }
    .toolbar-home-btn {
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        height:52px;
        border:1px solid #cfd8e3;
        border-radius:12px;
        background:#ffffff;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
        text-decoration:none;
    }
    .toolbar-home-img {
        width: 90%;
        height: 90%;
        object-fit: contain;
        display:block;
    }
    .point-card {
        border: 1px solid #d9dce3;
        border-radius: 10px;
        padding: 8px 10px 2px 10px;
        margin-bottom: 10px;
        background: #fafbfc;
    }
    .point-card-title {
        font-weight: 700;
        margin-bottom: 0.15rem;
    }
    .toolbar-title-space { margin-bottom: 0.35rem; }
    @media (max-width: 900px) {
        div[data-testid="stNumberInput"], div[data-testid="stSelectbox"] {max-width: 100% !important;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_points_df()
init_point_widgets()
if "show_about" not in st.session_state:
    st.session_state["show_about"] = False

header_cols = st.columns([1, 3])
with header_cols[0]:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=160)
with header_cols[1]:
    st.title(PROGRAM_NAME)
    st.caption(f"{VERSION} — {AUTHOR}")

toolbar_col, _ = st.columns([1.15, 2.85], gap="small")
with toolbar_col:
    tb1, tb2 = st.columns(2, gap="small")
    with tb1:
        if HOME_LOGO_FILE.exists():
            data_uri = image_to_data_uri(HOME_LOGO_FILE)
            st.markdown(
                f"""
                <div class="toolbar-home-wrap">
                    <a href="{HOME_URL}" target="_blank" class="toolbar-home-btn">
                        <img src="{data_uri}" alt="CUT Apps Home" class="toolbar-home-img">
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.link_button("Home", HOME_URL, use_container_width=True)
    with tb2:
        if st.button("About", use_container_width=True):
            st.session_state["show_about"] = not st.session_state.get("show_about", False)
    run = st.button("Compute", type="primary", use_container_width=True)

if st.session_state.get("show_about", False):
    st.info(ABOUT_TEXT)

use_for_bearing = st.checkbox("Use for CUT_Bearing_capacity (force α = 0 and δw = 0)", value=True)

col_inputs1, col_inputs2, col_plot = st.columns([0.50, 1.22, 1.8], gap="medium")

with col_inputs1:
    st.subheader("Inputs")

    i1, i2 = st.columns(2, gap="small")
    with i1:
        mode = st.selectbox("Mode", ["active", "passive"], index=0)
        phi = st.number_input("φ (deg)", min_value=0.001, max_value=89.999, value=30.0, step=1.0, format="%.1f")
        if use_for_bearing:
            alpha = 0.0
            st.number_input("α (deg)", value=alpha, disabled=True, format="%.1f")
        else:
            alpha = st.number_input("α (deg)", value=0.0, step=1.0, format="%.1f")
    with i2:
        H = st.number_input("H (m)", min_value=0.001, value=6.0, step=0.5, format="%.1f")
        if use_for_bearing:
            delta_w = 0.0
            st.number_input("δw (deg)", value=delta_w, disabled=True, format="%.1f")
        else:
            delta_w = st.number_input("δw (deg)", value=0.0, step=1.0, format="%.1f")
        n_steps = st.number_input("Sweep", min_value=100, value=12000, step=100, format="%d")

with col_inputs2:
    st.subheader("Points")

    act1, act2 = st.columns(2, gap="small")
    with act1:
        st.button("Add Point", on_click=add_point, use_container_width=True)
    with act2:
        st.button("Remove Selected", on_click=remove_selected_points, use_container_width=True)

    sync_points_from_widgets()
    current_df = normalize_points_df(st.session_state.points_df)

    for i in range(len(current_df)):
        st.markdown('<div class="point-card">', unsafe_allow_html=True)
        r1c1, r1c2 = st.columns([0.28, 0.72], gap="small")
        with r1c1:
            st.checkbox(
                f"Select Point {i}",
                key=f"pt_sel_{i}",
                disabled=(i == 0),
            )
        with r1c2:
            st.markdown(f'<div class="point-card-title">Point {i}</div>', unsafe_allow_html=True)

        r2c1, r2c2 = st.columns(2, gap="small")
        with r2c1:
            st.number_input(
                f"x ({i})",
                key=f"pt_x_{i}",
                value=float(current_df.loc[i, "x"]),
                step=0.1,
                format="%.1f",
                disabled=(i == 0),
            )
        with r2c2:
            st.number_input(
                f"y ({i})",
                key=f"pt_y_{i}",
                value=float(current_df.loc[i, "y"]),
                step=0.1,
                format="%.1f",
                disabled=(i == 0),
            )
        st.markdown('</div>', unsafe_allow_html=True)

    sync_points_from_widgets()

with col_plot:
    st.subheader("Geometry & Wedge")

    try:
        # Always compute live so the drawing is visible before pressing Compute
        compute_and_store(mode, phi, H, alpha, delta_w, int(n_steps))
    except Exception as e:
        st.session_state["last_error"] = str(e)
        st.session_state.pop("last_result", None)

    # Keep the compute button for explicit user action / visual consistency
    if run:
        try:
            compute_and_store(mode, phi, H, alpha, delta_w, int(n_steps))
        except Exception as e:
            st.session_state["last_error"] = str(e)
            st.session_state.pop("last_result", None)

    if "last_error" in st.session_state and "last_result" not in st.session_state:
        st.error(st.session_state["last_error"])

    if "last_result" in st.session_state:
        payload = st.session_state["last_result"]
        res = payload["result"]
        surface = payload["surface"]

        m1, m2 = st.columns([1,1])
        with m1:
            if payload["mode"] == "active":
                st.metric("Kₐ", f"{res['K']:.4f}")
            else:
                st.metric("Kₚ", f"{res['K']:.4f}")
        with m2:
            st.metric("β (deg)", f"{res['beta_deg']:.2f}")

        extra = "α = 0 and δw = 0 forced" if use_for_bearing else f"α = {payload['alpha']:.1f}°, δw = {payload['delta_w']:.1f}°"
        st.caption(extra)

        fig = make_plot(surface, payload["H"], payload["alpha"], res["beta_deg"])
        st.pyplot(fig, clear_figure=True, use_container_width=True)
    else:
        st.info("Set the inputs.")
