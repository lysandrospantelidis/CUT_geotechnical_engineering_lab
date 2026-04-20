
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import streamlit as st

from core.domain import Domain, ResultsType
from core.node import Node
from core.sections import SectionRectangle, SectionTrapezoidal, SectionUser
from io_utils.xml_parser import XMLParser

st.set_page_config(page_title="jWinkler Web", page_icon="📐", layout="wide")

st.markdown("""
<style>
    div[data-testid="stSidebar"] button, div[data-testid="stSidebar"] a[data-testid="stLinkButton"] {
        width: 100% !important;
        min-width: 0 !important;
        white-space: nowrap !important;
    }
</style>
""", unsafe_allow_html=True)

ASSETS = Path(__file__).resolve().parent / "assets"
SECTION_IMAGES = {
    "Trapezoidal": ASSETS / "SectionTrapezoidal.png",
    "Rectangular": ASSETS / "SectionRectangular.png",
    "User": ASSETS / "SectionUser.png",
}

ABOUT_HTML = """
<h3>jWinkler – Beam on Elastic Foundation (Winkler Model)</h3>
<p>
This software is an <b>educational and research-oriented tool</b> for the analysis of beams on elastic foundation based on the Winkler model.
It allows the user to define geometry, material properties, cross-sections, and loading conditions, and compute displacements,
bending moments, shear forces, and soil pressures.
</p>
<p>
This version is a <b>translation of an existing Java program into Python</b>, aiming at the development of:
</p>
<ul>
    <li>a Web-based application</li>
    <li>a standalone executable (EXE) application</li>
</ul>
<p>
The purpose of this translation is to overcome usability limitations associated with Java-based applications, while enabling:
</p>
<ul>
    <li>operation without installation (Web &amp; EXE versions)</li>
    <li>compatibility with all operating systems</li>
    <li>use on desktop and mobile devices, including iOS (PC and smartphone/tablet)</li>
</ul>
<p>
The initial functions of the original program have not been modified.
</p>
<p><b>Original software:</b><br>
Department of Civil Engineering,<br>
Aristotle University of Thessaloniki, Greece
</p>
<p>
Available at:<br>
<a href="https://edusoft.civil.auth.gr/">https://edusoft.civil.auth.gr/</a>
</p>
<p>
Installation instructions for the Java version:<br>
<a href="https://www.youtube.com/watch?v=CJ8P1-xuP64">https://www.youtube.com/watch?v=CJ8P1-xuP64</a>
</p>
<p><b>The Web and EXE versions do not require installation.</b></p>
<hr>
<p><b>Disclaimer</b><br>
This software is intended for educational and research use only and is provided without warranty.
</p>
<hr>
<p>
<b>Development and adaptation of the Web &amp; EXE versions:</b><br>
Dr. Lysandros Pantelidis<br>
Department of Civil Engineering and Geomatics<br>
Cyprus University of Technology<br>
<a href="mailto:lysandros.pantelidis@cut.ac.cy">lysandros.pantelidis@cut.ac.cy</a>
</p>
"""


def init_state() -> None:
    defaults = {
        "project": "",
        "user": "",
        "comments": "",
        "soil_gamma": 18.0,
        "soil_ks": 28000.0,
        "beam_gamma": 20.0,
        "beam_E": 21_000_000.0,
        "beam_nu": 0.15,
        "section_type": "Trapezoidal",
        "sec_b": 2.0,
        "sec_h": 2.0,
        "sec_b0": 0.5,
        "sec_h0": 0.5,
        "sec_h1": 0.5,
        "sec_h2": 0.5,
        "sec_A": 1.0,
        "sec_I": 1.0,
        "nodes_df": pd.DataFrame({"x [m]": [0.0, 5.0, 10.0]}),
        "nodal_loads_df": pd.DataFrame(columns=["node", "V [kN]", "M [kNm]"]),
        "beam_loads_df": pd.DataFrame(columns=["beam", "pA [kN/m]", "pB [kN/m]"]),
        "solved_domain": None,
        "last_error": None,
        "show_about": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def clean_nodes_df(df):
    import pandas as pd

    if isinstance(df, dict):
        try:
            df = pd.DataFrame(df)
        except Exception:
            return pd.DataFrame(columns=["x [m]"])

    if df is None:
        return pd.DataFrame(columns=["x [m]"])

    df = pd.DataFrame(df).copy()

    if len(df) == 0:
        return pd.DataFrame(columns=["x [m]"])

    # κράτα μόνο την αναμενόμενη στήλη
    if "x [m]" not in df.columns:
        return pd.DataFrame(columns=["x [m]"])

    df = df[["x [m]"]]
    df["x [m]"] = pd.to_numeric(df["x [m]"], errors="coerce")
    df = df.dropna(subset=["x [m]"])

    return df.reset_index(drop=True)


def round_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    num_cols = out.select_dtypes(include=[np.number]).columns
    out[num_cols] = out[num_cols].round(2)
    return out



def clean_table_df(df: pd.DataFrame, columns: list[str], int_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(df).copy()
    # keep only expected columns; this removes stray index/editor columns from older Streamlit versions
    out = out[[c for c in out.columns if c in columns]]
    for c in columns:
        if c not in out.columns:
            out[c] = np.nan
    out = out[columns]
    # remove fully empty rows
    out = out.dropna(how="all").reset_index(drop=True)
    for c in columns:
        out[c] = pd.to_numeric(out[c], errors="coerce")
        if c in int_cols:
            out[c] = out[c].round().astype("Int64")
    return out


def clean_nodal_loads_df(df: pd.DataFrame) -> pd.DataFrame:
    return clean_table_df(df, ["node", "V [kN]", "M [kNm]"], int_cols=("node",))


def clean_beam_loads_df(df: pd.DataFrame) -> pd.DataFrame:
    return clean_table_df(df, ["beam", "pA [kN/m]", "pB [kN/m]"], int_cols=("beam",))


def apply_generated_nodes(x1: float, x2: float, segments: int) -> None:
    segments = max(int(segments), 1)
    xs = np.linspace(float(x1), float(x2), segments + 1)
    st.session_state.nodes_df = pd.DataFrame({"x [m]": xs})
    st.session_state.solved_domain = None


def build_domain() -> Domain:
    domain = Domain()
    domain.project = st.session_state.project
    domain.user = st.session_state.user
    domain.comments = st.session_state.comments
    domain.set_soil_mat(float(st.session_state.soil_gamma), float(st.session_state.soil_ks))
    domain.set_beam_mat(float(st.session_state.beam_gamma), float(st.session_state.beam_E), float(st.session_state.beam_nu))

    sec_type = st.session_state.section_type
    if sec_type == "Trapezoidal":
        sec = SectionTrapezoidal(float(st.session_state.sec_b), float(st.session_state.sec_h), float(st.session_state.sec_b0),
                                 float(st.session_state.sec_h0), float(st.session_state.sec_h1), float(st.session_state.sec_h2))
    elif sec_type == "Rectangular":
        sec = SectionRectangle(float(st.session_state.sec_b), float(st.session_state.sec_h), float(st.session_state.sec_b0),
                               float(st.session_state.sec_h0), float(st.session_state.sec_h1))
    else:
        sec = SectionUser(float(st.session_state.sec_b), float(st.session_state.sec_h), float(st.session_state.sec_A), float(st.session_state.sec_I))
    domain.set_beam_sec(sec)

    nodes_df = clean_nodes_df(st.session_state.nodes_df)
    if len(nodes_df) < 2:
        raise ValueError("At least two nodes are required.")
    domain.set_nodes([Node(i + 1, float(x)) for i, x in enumerate(nodes_df["x [m]"].tolist())])

    nodal_df = clean_nodal_loads_df(st.session_state.nodal_loads_df)
    if not nodal_df.empty:
        for _, row in nodal_df.iterrows():
            if pd.isna(row.get("node")):
                continue
            idx = int(row["node"]) - 1
            if 0 <= idx < len(domain.nodes):
                v = pd.to_numeric(row.get("V [kN]"), errors="coerce")
                m = pd.to_numeric(row.get("M [kNm]"), errors="coerce")
                domain.nodes[idx].set_load(float(0.0 if pd.isna(v) else v), float(0.0 if pd.isna(m) else m))

    beam_df = clean_beam_loads_df(st.session_state.beam_loads_df)
    if not beam_df.empty:
        for _, row in beam_df.iterrows():
            if pd.isna(row.get("beam")):
                continue
            idx = int(row["beam"]) - 1
            if 0 <= idx < len(domain.beams):
                pa = pd.to_numeric(row.get("pA [kN/m]"), errors="coerce")
                pb = pd.to_numeric(row.get("pB [kN/m]"), errors="coerce")
                domain.beams[idx].set_load(float(0.0 if pd.isna(pa) else pa), float(0.0 if pd.isna(pb) else pb))

    return domain


def load_state_from_domain(domain: Domain) -> None:
    st.session_state.project = domain.project
    st.session_state.user = domain.user
    st.session_state.comments = domain.comments
    st.session_state.soil_gamma = domain.soil_mat.gamma
    st.session_state.soil_ks = domain.soil_mat.Ks
    st.session_state.beam_gamma = domain.beam_mat.gamma
    st.session_state.beam_E = domain.beam_mat.E
    st.session_state.beam_nu = domain.beam_mat.nu
    sec = domain.beam_sec
    if sec.tag == "TRPZ":
        st.session_state.section_type = "Trapezoidal"
        st.session_state.sec_b, st.session_state.sec_h = sec.b, sec.h
        st.session_state.sec_b0, st.session_state.sec_h0 = sec.b0, sec.h0
        st.session_state.sec_h1, st.session_state.sec_h2 = sec.h1, sec.h2
    elif sec.tag == "RECT":
        st.session_state.section_type = "Rectangular"
        st.session_state.sec_b, st.session_state.sec_h = sec.b, sec.h
        st.session_state.sec_b0, st.session_state.sec_h0 = sec.b0, sec.h0
        st.session_state.sec_h1 = sec.h1
    else:
        st.session_state.section_type = "User"
        st.session_state.sec_b, st.session_state.sec_h = sec.b, sec.h
        st.session_state.sec_A, st.session_state.sec_I = sec.A, sec.I

    st.session_state.nodes_df = pd.DataFrame({"x [m]": [n.x for n in domain.nodes]})
    nodal_rows = [{"node": n.id, "V [kN]": n.F[0], "M [kNm]": n.F[1]} for n in domain.nodes if abs(n.F[0]) > 1e-15 or abs(n.F[1]) > 1e-15]
    st.session_state.nodal_loads_df = pd.DataFrame(nodal_rows, columns=["node", "V [kN]", "M [kNm]"])
    beam_rows = [{"beam": b.id, "pA [kN/m]": b.Fext[0], "pB [kN/m]": b.Fext[1]} for b in domain.beams if abs(b.Fext[0]) > 1e-15 or abs(b.Fext[1]) > 1e-15]
    st.session_state.beam_loads_df = pd.DataFrame(beam_rows, columns=["beam", "pA [kN/m]", "pB [kN/m]"])
    st.session_state.solved_domain = None
    st.session_state.last_error = None


def solve_current_model() -> None:
    try:
        domain = build_domain()
        domain.solve()
        st.session_state.solved_domain = domain
        st.session_state.last_error = None
    except Exception as exc:
        st.session_state.solved_domain = None
        st.session_state.last_error = str(exc)


def get_current_domain_for_export() -> Domain | None:
    try:
        return build_domain()
    except Exception:
        return None


def parse_uploaded_xml(uploaded) -> None:
    parser = XMLParser()
    domain = Domain()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name
    parser.parse(domain, tmp_path)
    load_state_from_domain(domain)


def collect_result_arrays(domain: Domain, result_type: ResultsType) -> tuple[np.ndarray, np.ndarray]:
    xs: List[float] = []
    ys: List[float] = []
    domain.results_type = result_type
    for i, beam in enumerate(domain.beams):
        x = np.asarray(domain.get_x(i), dtype=float)
        y = np.asarray(domain.get_y(i), dtype=float)
        if i > 0:
            x = x[1:]
            y = y[1:]
        xs.extend(x.tolist())
        ys.extend(y.tolist())
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)



def _draw_moment(ax, x: float, y: float, value: float, side_index: int = 0):
    if abs(value) < 1e-12:
        return
    r = 0.18
    cy = y + 0.58 + 0.18 * side_index
    color = "#9c27b0"
    ccw = value > 0

    if ccw:
        # open gap near the right-hand side and place a clear tangential arrow pointing CCW
        arc = patches.Arc((x, cy), 2*r, 2*r, angle=0, theta1=35, theta2=335, lw=2.2, color=color)
        ax.add_patch(arc)
        ang = np.deg2rad(300)
        tx, ty = x + r*np.cos(ang), cy + r*np.sin(ang)
        dx, dy = -np.sin(ang), np.cos(ang)  # tangent in CCW direction
        ax.annotate("", xy=(tx, ty), xytext=(tx - 0.16*dx, ty - 0.16*dy),
                    arrowprops=dict(arrowstyle="-|>", lw=2.2, color=color, mutation_scale=18))
        ax.text(x + 0.26, cy + 0.06, f"M = {abs(value):.2f} kNm (CCW)", color=color, fontsize=9, ha="left")
    else:
        arc = patches.Arc((x, cy), 2*r, 2*r, angle=0, theta1=205, theta2=505, lw=2.2, color=color)
        ax.add_patch(arc)
        ang = np.deg2rad(240)
        tx, ty = x + r*np.cos(ang), cy + r*np.sin(ang)
        dx, dy = np.sin(ang), -np.cos(ang)  # tangent in CW direction
        ax.annotate("", xy=(tx, ty), xytext=(tx - 0.16*dx, ty - 0.16*dy),
                    arrowprops=dict(arrowstyle="-|>", lw=2.2, color=color, mutation_scale=18))
        ax.text(x + 0.26, cy + 0.06, f"M = {abs(value):.2f} kNm (CW)", color=color, fontsize=9, ha="left")


def plot_geometry(domain: Domain):
    fig, ax = plt.subplots(figsize=(16, 4.0))
    xs = [n.x for n in domain.nodes]
    L = max(domain.L, 1.0)
    ax.plot([xs[0], xs[-1]], [0, 0], lw=3.2, color="#2952cc")

    for node in domain.nodes:
        x = node.x
        ax.plot(x, 0, marker="o", ms=7, color="#2952cc")
        ax.text(x, 0.10, f"{node.id}", ha="center", va="bottom", fontsize=9, color="#334")
        ax.plot([x, x], [0, -0.12], lw=1.1, color="#8a8a8a")
        zigx = [x, x-0.05, x+0.05, x-0.05, x+0.05, x]
        zigy = [-0.12, -0.18, -0.24, -0.30, -0.36, -0.40]
        ax.plot(zigx, zigy, lw=1.1, color="#8a8a8a")
        ax.plot([x-0.08, x+0.08], [-0.42, -0.42], lw=1.0, color="#8a8a8a")

    active_nodes = [n for n in domain.nodes if abs(n.F[0]) > 1e-12 or abs(n.F[1]) > 1e-12]
    for idx, node in enumerate(active_nodes):
        x = node.x
        v, m = node.F
        level = idx % 2
        arrow_top = 0.78 + 0.14*level
        beam_y = 0.04
        if abs(v) > 1e-12:
            # Positive V is drawn downward, consistent with the desktop app.
            if v > 0:
                ax.annotate("", xy=(x, beam_y), xytext=(x, arrow_top), arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#d62828"))
                ax.text(x, arrow_top + 0.03, f"{abs(v):.2f}", color="#d62828", fontsize=9, ha="center")
            else:
                ax.annotate("", xy=(x, arrow_top), xytext=(x, beam_y), arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#d62828"))
                ax.text(x, arrow_top + 0.03, f"{abs(v):.2f}", color="#d62828", fontsize=9, ha="center")
        if abs(m) > 1e-12:
            _draw_moment(ax, x + (0.08 if abs(v) > 1e-12 else 0.0), 0.0, m, side_index=level)

    active_beams = [b for b in domain.beams if abs(b.Fext[0]) > 1e-12 or abs(b.Fext[1]) > 1e-12]
    for j, beam in enumerate(active_beams):
        xa, xb = beam.n1.x, beam.n2.x
        base_y = 0.96 + 0.18*(j % 2)
        pmax = max(abs(beam.Fext[0]), abs(beam.Fext[1]), 1.0)
        hA = 0.16 + 0.18 * abs(beam.Fext[0]) / pmax
        hB = 0.16 + 0.18 * abs(beam.Fext[1]) / pmax
        crest_a = base_y + hA
        crest_b = base_y + hB
        xx = np.linspace(xa, xb, 5)
        yy = np.linspace(crest_a, crest_b, 5)
        ax.plot([xa, xb], [crest_a, crest_b], color="#2b9348", lw=1.6)
        for x, ytop, p in zip(xx, yy, np.linspace(beam.Fext[0], beam.Fext[1], 5)):
            if p >= 0:
                ax.annotate("", xy=(x, 0.05), xytext=(x, ytop), arrowprops=dict(arrowstyle="-|>", lw=1.5, color="#2b9348"))
            else:
                ax.annotate("", xy=(x, ytop), xytext=(x, 0.05), arrowprops=dict(arrowstyle="-|>", lw=1.5, color="#2b9348"))
        ax.text((xa+xb)/2, max(crest_a, crest_b)+0.06,
                f"pA = {beam.Fext[0]:.2f}, pB = {beam.Fext[1]:.2f} kN/m",
                ha="center", va="bottom", fontsize=9, color="#2b9348")

    ax.set_title("Geometry")
    ax.set_xlim(xs[0] - 0.05 * L, xs[-1] + 0.05 * L)
    ax.set_ylim(-0.55, 1.75)
    ax.set_xlabel("x [m]")
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.25)
    return fig


def plot_result(domain: Domain, result_type: ResultsType, title: str, ylabel: str):
    xs, ys_real = collect_result_arrays(domain, result_type)
    fig, ax = plt.subplots(figsize=(16, 3.2))
    if len(xs) == 0:
        ax.set_title(title)
        return fig

    # Display convention: settlement positive downward, positive bending moment below the beam,
    # positive shear above the beam, and positive soil pressure downward.
    ys_plot = ys_real.copy()
    if result_type in (ResultsType.U, ResultsType.M, ResultsType.P):
        ys_plot = -ys_plot

    ax.axhline(0.0, lw=1.0, alpha=0.55, color="#9f9f9f")
    ax.plot(xs, ys_plot, lw=2.0, color="#1f4cff")
    ax.fill_between(xs, 0, ys_plot, alpha=0.18, color="#1f4cff")
    for n in domain.nodes:
        ax.axvline(n.x, lw=0.7, alpha=0.18, color="#657b9a", ls="--")

    ymax_idx = int(np.argmax(ys_real))
    ymin_idx = int(np.argmin(ys_real))
    ax.plot(xs[ymax_idx], ys_plot[ymax_idx], marker="o", ms=6, color="#243b63")
    ax.plot(xs[ymin_idx], ys_plot[ymin_idx], marker="o", ms=6, color="#243b63")
    ax.annotate(f"max = {ys_real[ymax_idx]:.2f}", (xs[ymax_idx], ys_plot[ymax_idx]), xytext=(8, 8), textcoords="offset points", fontsize=9)
    ax.annotate(f"min = {ys_real[ymin_idx]:.2f}", (xs[ymin_idx], ys_plot[ymin_idx]), xytext=(8, -16), textcoords="offset points", fontsize=9)
    ax.set_title(title)
    ax.set_xlabel("x [m]")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    return fig


def results_dataframe(domain: Domain) -> pd.DataFrame:
    headers = ["beam", "node", "displacements [m]", "rotations [rad]", "moments [kNm]", "shear forces [kN]", "soil pressures [kN]"]
    df = pd.DataFrame(domain.get_table(), columns=headers)
    for c in headers:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(2)
    return df


init_state()

st.title("jWinkler Web")
st.caption("Beam on elastic foundation (Winkler model) — Streamlit web application")

with st.sidebar:
    st.markdown("### Quick links")
    if st.button("About", use_container_width=True):
        st.session_state.show_about = not st.session_state.show_about
    st.link_button("CUT-APPS", "https://cut-apps.streamlit.app/", use_container_width=True)
    st.markdown("---")
    st.header("Model input")
    uploaded = st.file_uploader("Open XML file", type=["xml"])
    if uploaded is not None and st.button("Load XML into model", use_container_width=True):
        parse_uploaded_xml(uploaded)
        st.success("XML file loaded.")

    st.subheader("General")
    st.text_input("Project", key="project")
    st.text_input("User", key="user")
    st.text_area("Comments", key="comments", height=100)

    st.subheader("Materials")
    st.number_input("Soil γ", key="soil_gamma", step=0.1, format="%.2f")
    st.number_input("Soil Ks", key="soil_ks", step=100.0, format="%.2f")
    st.number_input("Beam γ", key="beam_gamma", step=0.1, format="%.2f")
    st.number_input("Beam E", key="beam_E", step=1000.0, format="%.2f")
    st.number_input("Beam ν", key="beam_nu", step=0.01, min_value=0.0, max_value=1.0, format="%.2f")

    st.subheader("Section")
    st.selectbox("Section type", ["Trapezoidal", "Rectangular", "User"], key="section_type")
    img_path = SECTION_IMAGES.get(st.session_state.section_type)
    if img_path and img_path.exists():
        st.image(str(img_path), use_container_width=True)
    st.number_input("b", key="sec_b", step=0.1, format="%.2f")
    st.number_input("h", key="sec_h", step=0.1, format="%.2f")
    if st.session_state.section_type == "Trapezoidal":
        st.number_input("b0", key="sec_b0", step=0.1, format="%.2f")
        st.number_input("h0", key="sec_h0", step=0.1, format="%.2f")
        st.number_input("h1", key="sec_h1", step=0.1, format="%.2f")
        st.number_input("h2", key="sec_h2", step=0.1, format="%.2f")
    elif st.session_state.section_type == "Rectangular":
        st.number_input("b0", key="sec_b0", step=0.1, format="%.2f")
        st.number_input("h0", key="sec_h0", step=0.1, format="%.2f")
        st.number_input("h1", key="sec_h1", step=0.1, format="%.2f")
    else:
        st.number_input("A", key="sec_A", step=0.1, format="%.2f")
        st.number_input("I", key="sec_I", step=0.1, format="%.2f")

    if st.button("Solve model", type="primary", use_container_width=True):
        solve_current_model()

    export_domain = get_current_domain_for_export()
    if export_domain is not None:
        st.download_button("Download XML", data=export_domain.to_xml().encode("utf-8"), file_name="jwinkler_model.xml", mime="application/xml", use_container_width=True)

if st.session_state.show_about:
    st.markdown(ABOUT_HTML, unsafe_allow_html=True)
    st.markdown("---")

st.subheader("Nodes")
g1, g2, g3, g4 = st.columns([1,1,1,1])
x1 = g1.number_input("From", value=0.0, step=1.0, key="gen_x1", format="%.2f")
x2 = g2.number_input("To", value=10.0, step=1.0, key="gen_x2", format="%.2f")
segments = g3.number_input("Segments", value=10, min_value=1, step=1, key="gen_segments")
if g4.button("Generate equally spaced nodes", use_container_width=True):
    apply_generated_nodes(x1, x2, int(segments))

edited_nodes_df = st.data_editor(
    round_df(clean_nodes_df(st.session_state.nodes_df)),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="nodes_editor",
    column_config={"x [m]": st.column_config.NumberColumn("x [m]", step=0.01, format="%.2f")},
)

st.session_state.nodes_df = clean_nodes_df(edited_nodes_df)

try:
    node_count = len(clean_nodes_df(st.session_state.nodes_df))
    beam_count = max(node_count - 1, 0)
except Exception:
    node_count = 0
    beam_count = 0


st.subheader("Loads")
l1, l2 = st.columns(2)

# sanitize any legacy editor/index columns saved in session state
st.session_state.nodal_loads_df = clean_nodal_loads_df(st.session_state.nodal_loads_df)
st.session_state.beam_loads_df = clean_beam_loads_df(st.session_state.beam_loads_df)

with l1:
    st.markdown("**Nodal loads**")
    with st.form("nodal_load_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        node_val = c1.number_input("node", min_value=1, max_value=max(node_count, 1), value=1, step=1, format="%d")
        v_val = c2.number_input("V [kN]", value=0.00, step=0.01, format="%.2f")
        m_val = c3.number_input("M [kNm]", value=0.00, step=0.01, format="%.2f")
        add_nodal = st.form_submit_button("Add / update nodal load", use_container_width=True)
    if add_nodal:
        df = clean_nodal_loads_df(st.session_state.nodal_loads_df)
        mask = df["node"].astype("Int64") == int(node_val)
        new_row = pd.DataFrame([{"node": int(node_val), "V [kN]": float(v_val), "M [kNm]": float(m_val)}])
        if mask.any():
            df.loc[mask, ["V [kN]", "M [kNm]"]] = [float(v_val), float(m_val)]
        else:
            df = pd.concat([df, new_row], ignore_index=True)
        st.session_state.nodal_loads_df = clean_nodal_loads_df(df).sort_values(by="node", kind="stable").reset_index(drop=True)
        st.session_state.solved_domain = None

    if not st.session_state.nodal_loads_df.empty:
        nodal_display = round_df(st.session_state.nodal_loads_df.copy())
        st.dataframe(nodal_display, use_container_width=True, hide_index=True)
        rem_node = st.selectbox("Remove nodal load at node", ["—"] + [int(x) for x in nodal_display["node"].dropna().tolist()], key="remove_nodal_node")
        if st.button("Remove selected nodal load", use_container_width=True):
            if rem_node != "—":
                df = clean_nodal_loads_df(st.session_state.nodal_loads_df)
                df = df[df["node"].astype("Int64") != int(rem_node)].reset_index(drop=True)
                st.session_state.nodal_loads_df = df
                st.session_state.solved_domain = None
                st.rerun()
    else:
        st.dataframe(pd.DataFrame(columns=["node", "V [kN]", "M [kNm]"]), use_container_width=True, hide_index=True)

with l2:
    st.markdown("**Beam loads**")
    with st.form("beam_load_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        beam_val = c1.number_input("beam", min_value=1, max_value=max(beam_count, 1), value=1, step=1, format="%d")
        pa_val = c2.number_input("pA [kN/m]", value=0.00, step=0.01, format="%.2f")
        pb_val = c3.number_input("pB [kN/m]", value=0.00, step=0.01, format="%.2f")
        add_beam = st.form_submit_button("Add / update beam load", use_container_width=True)
    if add_beam:
        df = clean_beam_loads_df(st.session_state.beam_loads_df)
        mask = df["beam"].astype("Int64") == int(beam_val)
        new_row = pd.DataFrame([{"beam": int(beam_val), "pA [kN/m]": float(pa_val), "pB [kN/m]": float(pb_val)}])
        if mask.any():
            df.loc[mask, ["pA [kN/m]", "pB [kN/m]"]] = [float(pa_val), float(pb_val)]
        else:
            df = pd.concat([df, new_row], ignore_index=True)
        st.session_state.beam_loads_df = clean_beam_loads_df(df).sort_values(by="beam", kind="stable").reset_index(drop=True)
        st.session_state.solved_domain = None

    if not st.session_state.beam_loads_df.empty:
        beam_display = round_df(st.session_state.beam_loads_df.copy())
        st.dataframe(beam_display, use_container_width=True, hide_index=True)
        rem_beam = st.selectbox("Remove beam load at beam", ["—"] + [int(x) for x in beam_display["beam"].dropna().tolist()], key="remove_beam_id")
        if st.button("Remove selected beam load", use_container_width=True):
            if rem_beam != "—":
                df = clean_beam_loads_df(st.session_state.beam_loads_df)
                df = df[df["beam"].astype("Int64") != int(rem_beam)].reset_index(drop=True)
                st.session_state.beam_loads_df = df
                st.session_state.solved_domain = None
                st.rerun()
    else:
        st.dataframe(pd.DataFrame(columns=["beam", "pA [kN/m]", "pB [kN/m]"]), use_container_width=True, hide_index=True)

domain_for_view = st.session_state.solved_domain
if domain_for_view is None:
    try:
        domain_for_view = build_domain()
    except Exception:
        domain_for_view = None

if st.session_state.last_error:
    st.error(st.session_state.last_error)

if domain_for_view is not None:
    st.subheader("Geometry")
    st.pyplot(plot_geometry(domain_for_view), use_container_width=True)

if st.session_state.solved_domain is not None:
    solved = st.session_state.solved_domain
    st.subheader("Displacement")
    st.pyplot(plot_result(solved, ResultsType.U, "Displacement", "u [m]"), use_container_width=True)
    st.subheader("Moment")
    st.pyplot(plot_result(solved, ResultsType.M, "Moment", "M [kNm]"), use_container_width=True)
    st.subheader("Shear")
    st.pyplot(plot_result(solved, ResultsType.V, "Shear", "V [kN]"), use_container_width=True)
    st.subheader("Soil pressure")
    st.pyplot(plot_result(solved, ResultsType.P, "Soil pressure", "p [kPa]"), use_container_width=True)
    st.subheader("Results table")
    st.dataframe(results_dataframe(solved), use_container_width=True, hide_index=True)
else:
    st.info("Set up the model and click Solve model to see displacement, moment, shear, soil pressure, and the results table.")
