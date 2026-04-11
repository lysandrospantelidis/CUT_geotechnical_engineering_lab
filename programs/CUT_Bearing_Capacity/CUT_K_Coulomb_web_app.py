from __future__ import annotations

import math
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

PROGRAM_NAME = "CUT_K_Coulomb"
VERSION = "v1.0.0 (Web)"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"

Point = Tuple[float, float]


class GeometryError(ValueError):
    pass


def _line_intersection_from_base(y0: float, m: float, p1: Point, p2: Point) -> Optional[Point]:
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    denom = dy - m * dx
    if abs(denom) < 1e-14:
        return None
    t = (m * x1 + y0 - y1) / denom
    if 0.0 <= t <= 1.0:
        xi, yi = x1 + t * dx, y1 + t * dy
        if xi > 1e-9:
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


def _build_wedge(H: float, surface: List[Point], theta: float) -> Tuple[Optional[List[Point]], float]:
    m = math.tan(theta)
    poly = [(0.0, 0.0), (0.0, -H)]
    hit = None
    for i in range(len(surface) - 1):
        p1, p2 = surface[i], surface[i + 1]
        inter = _line_intersection_from_base(-H, m, p1, p2)
        if inter is not None:
            hit = inter
            poly.append(hit)
            poly.extend(reversed(surface[: i + 1]))
            break
    if hit is None:
        return None, 0.0
    if poly[-1] != (0.0, 0.0):
        poly.append((0.0, 0.0))
    if _polygon_area(poly) <= 1e-12:
        return None, 0.0
    return poly, hit[0]


def _K_from_geom(H: float, area: float, angle_term: float) -> float:
    return (2.0 / (H * H)) * area * math.tan(angle_term)


def _sweep_theta(phi: float, H: float, surface: List[Point], mode: str, n_steps: int):
    eps = math.radians(0.1)
    if mode == "active":
        theta_min = max(eps, phi + eps)
        theta_max = math.radians(89.5)
        sign = -1
    else:
        theta_min = eps
        theta_max = max(theta_min + eps, math.radians(89.5) - phi)
        sign = +1

    best_theta = None
    best_K = None
    best_obj = float("inf")
    for i in range(1, n_steps):
        theta = theta_min + (theta_max - theta_min) * i / n_steps
        poly, _ = _build_wedge(H, surface, theta)
        if poly is None:
            continue
        area = _polygon_area(poly)
        angle_term = (theta - phi) if mode == "active" else (theta + phi)
        if not (0.0 < angle_term < math.radians(89.0)):
            continue
        K = _K_from_geom(H, area, angle_term)
        obj = sign * K
        if obj < best_obj:
            best_obj = obj
            best_theta = theta
            best_K = K
    if best_K is None:
        raise GeometryError("No feasible wedge found for these inputs.")
    return best_theta, best_K


def coulomb_top_origin(phi_deg: float, H: float, surface_pts: List[Point], n_steps: int, mode: str):
    if not (0.0 < phi_deg < 90.0):
        raise ValueError("φ must be between 0 and 90 degrees.")
    if H <= 0:
        raise ValueError("H must be positive.")
    if len(surface_pts) < 2:
        raise ValueError("Provide at least 2 surface points starting at (0, 0).")
    for (x1, _), (x2, _) in zip(surface_pts, surface_pts[1:]):
        if x2 < x1 - 1e-12:
            raise ValueError("x must be non-decreasing from Point 0 outward.")
    phi = math.radians(phi_deg)
    th, K = _sweep_theta(phi, H, surface_pts, mode, n_steps)
    return dict(theta_deg=math.degrees(th), K=K)


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


def make_plot(surface: List[Point], H: float, theta_deg: float):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    xs_plot = [p[0] for p in surface]
    ys_plot = [p[1] for p in surface]

    ax.plot([0, 0], [0, -H], lw=2)
    ax.plot(xs_plot, ys_plot, marker="o")

    th_rad = math.radians(theta_deg)
    xa = np.linspace(0, max(xs_plot) if xs_plot else 1.0, 200)
    ya = -H + np.tan(th_rad) * xa
    ax.plot(xa, ya, ls="--")

    poly, _ = _build_wedge(H, surface, th_rad)
    if poly:
        ax.fill([p[0] for p in poly], [p[1] for p in poly], alpha=0.18)

    xmax = max(1.0, max(xs_plot) * 1.2 if xs_plot else 1.0)
    ymax = max(1.0, max([0.0] + ys_plot) * 1.4 if ys_plot else 1.0)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.5, xmax)
    ax.set_ylim(-H * 1.15, ymax)
    ax.set_xlabel("x (m) →")
    ax.set_ylabel("y (m) ↑   (top at 0)")
    ax.grid(True, alpha=0.3)
    return fig


st.set_page_config(page_title=PROGRAM_NAME, layout="wide")

st.title(PROGRAM_NAME)
st.caption(f"{VERSION} — {AUTHOR}")
st.write(
    "Smooth vertical wall (δ = 0). The wall top is the origin (0, 0); "
    "the failure plane leaves the base (0, -H) and intersects the user-defined broken surface."
)

with st.sidebar:
    st.header("Inputs")
    mode = st.selectbox("Mode", ["active", "passive"], index=0)
    phi = st.number_input("φ (deg)", min_value=0.001, max_value=89.999, value=30.0, step=1.0, format="%.3f")
    H = st.number_input("H (m)", min_value=0.001, value=6.0, step=0.5, format="%.3f")
    n_steps = st.number_input("Angle sweep steps", min_value=100, value=10000, step=100, format="%d")
    compute = st.button("Compute", width="stretch")
    with st.expander("About"):
        st.write(
            f"{PROGRAM_NAME}\n\n"
            f"{VERSION}\n\n"
            f"{AUTHOR}\n\n"
            "Smooth vertical wall (δ = 0). Any soil surface geometry can be modeled via points. "
            "Educational tool — no warranty. Use at your own risk. Free of charge."
        )

default_df = pd.DataFrame(
    {
        "Point": ["Point 0", "Point 1", "Point 2"],
        "x": [0.0, 5.0, 10.0],
        "y": [0.0, 0.5, 0.8],
    }
)

st.subheader("Points (TOP origin: Point 0 fixed at (0, 0))")
edited = st.data_editor(
    default_df,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        "Point": st.column_config.TextColumn("Point", disabled=True),
        "x": st.column_config.NumberColumn("x", format="%.3f"),
        "y": st.column_config.NumberColumn("y", format="%.3f"),
    },
)

edited = edited.copy()
edited["Point"] = [f"Point {i}" for i in range(len(edited))]
if len(edited) > 0:
    edited.loc[0, "x"] = 0.0
    edited.loc[0, "y"] = 0.0

if compute:
    try:
        surface = collect_points(edited[["x", "y"]])
        res = coulomb_top_origin(phi, H, surface, int(n_steps), mode)

        c1, c2 = st.columns([1, 2])
        with c1:
            if mode == "active":
                st.metric("Kₐ", f"{res['K']:.4f}")
            else:
                st.metric("Kₚ", f"{res['K']:.4f}")
            st.metric("θ (deg)", f"{res['theta_deg']:.2f}")

        with c2:
            fig = make_plot(surface, H, res["theta_deg"])
            st.pyplot(fig, clear_figure=True)

    except Exception as e:
        st.error(str(e))
else:
    st.info("Set the inputs and press Compute.")
