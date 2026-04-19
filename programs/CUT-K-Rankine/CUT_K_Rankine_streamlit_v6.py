from __future__ import annotations

import base64
import math
from pathlib import Path

import streamlit as st

PROGRAM_NAME = "CUT_K_Rankine"
VERSION = "v6 (Web)"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"
HOME_URL = "https://cut-apps.streamlit.app/"

BASE_DIR = Path(__file__).resolve().parent
HEADER_LOGO_FILE = BASE_DIR / "logo.png"
CUT_BUTTON_FILE = BASE_DIR / "cut_logo.png"
HOME_LOGO_FILE = BASE_DIR / "home.png"
FIGURE_FILE = BASE_DIR / "fig2.png"

ABOUT_TEXT = """CUT_K_Rankine
Version: v6 (Web)
Author: Dr Lysandros Pantelidis, Cyprus University of Technology

Computes Kₐ and Kₚ by direct application of the Rankine formulas.
Inputs: φ (soil friction angle) and β (backfill angle).

Educational tool — no warranty. Use at your own risk. Free of charge."""


class RankineError(ValueError):
    pass


def image_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "image/png" if suffix == "png" else f"image/{suffix}"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def rankine_ka_kp(phi_deg: float, beta_deg: float) -> tuple[float, float]:
    if not (0.0 < phi_deg < 90.0):
        raise RankineError("φ must be between 0 and 90 degrees.")

    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)

    cos_beta = math.cos(beta)
    radicand = cos_beta * cos_beta - math.cos(phi) * math.cos(phi)

    if radicand < -1e-12:
        raise RankineError(
            "The expression under the square root becomes negative. "
            "For these formulas, admissible inputs require cos²β ≥ cos²φ."
        )

    radicand = max(0.0, radicand)
    root = math.sqrt(radicand)

    den_ka = cos_beta + root
    den_kp = cos_beta - root

    if abs(den_ka) < 1e-14 or abs(den_kp) < 1e-14:
        raise RankineError("A denominator becomes zero for the selected inputs.")

    ka = cos_beta * (cos_beta - root) / den_ka
    kp = cos_beta * (cos_beta + root) / den_kp
    return ka, kp


st.set_page_config(page_title=PROGRAM_NAME, layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1.2rem;
    }
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
    .toolbar-home-btn, .toolbar-cut-box {
        display:flex;
        align-items:center;
        justify-content:center;
        width:100%;
        height:118px;
        border:1px solid #cfd8e3;
        border-radius:12px;
        background:#ffffff;
        box-shadow:0 1px 3px rgba(0,0,0,0.08);
        text-decoration:none;
        overflow:hidden;
    }
    .toolbar-home-img, .toolbar-cut-img {
        width: 92%;
        height: 92%;
        object-fit: contain;
        display:block;
    }
    .toolbar-right-tight [data-testid="stVerticalBlock"] {
        gap: 0.20rem !important;
    }
    .toolbar-right-tight div[data-testid="stButton"] {
        margin: 0 !important;
    }
    .left-pane {
        border: 1px solid #dde4ee;
        border-radius: 14px;
        padding: 0.8rem 0.9rem 0.7rem 0.9rem;
        background: #fbfcfe;
    }
    .right-pane {
        border: 1px solid #dde4ee;
        border-radius: 14px;
        padding: 0.8rem 1.0rem 0.8rem 1.0rem;
        background: #ffffff;
        max-height: 78vh;
        overflow-y: auto;
    }
    .result-card {
        border: 1px solid #dde4ee;
        border-radius: 12px;
        padding: 0.8rem 0.9rem;
        background: white;
        margin-top: 0.6rem;
    }
    .result-main {
        font-size: 1.18rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .caption-center {
        text-align:left;
        font-size:0.95rem;
        color:#444;
        margin-top:0.2rem;
        margin-bottom:0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "show_about" not in st.session_state:
    st.session_state["show_about"] = False
if "ka" not in st.session_state:
    st.session_state["ka"] = None
if "kp" not in st.session_state:
    st.session_state["kp"] = None
if "note" not in st.session_state:
    st.session_state["note"] = ""
if "last_error" not in st.session_state:
    st.session_state["last_error"] = ""

header_cols = st.columns([1, 3])
with header_cols[0]:
    if HEADER_LOGO_FILE.exists():
        st.image(str(HEADER_LOGO_FILE), width=150)
with header_cols[1]:
    st.title(PROGRAM_NAME)
    st.caption(f"{VERSION} — {AUTHOR}")

toolbar_col, _ = st.columns([1.15, 2.85], gap="small")
with toolbar_col:
    left, right = st.columns([1, 1], gap="small")

    with left:
        if HOME_LOGO_FILE.exists():
            home_uri = image_to_data_uri(HOME_LOGO_FILE)
            st.markdown(
                f'''
                <a href="{HOME_URL}" target="_blank" class="toolbar-home-btn">
                    <img src="{home_uri}" class="toolbar-home-img">
                </a>
                ''',
                unsafe_allow_html=True,
            )
        else:
            st.link_button("Home", HOME_URL, use_container_width=True)

    with right:
        if CUT_BUTTON_FILE.exists():
            cut_uri = image_to_data_uri(CUT_BUTTON_FILE)
            st.markdown(
                f'''
                <div class="toolbar-cut-box">
                    <img src="{cut_uri}" class="toolbar-cut-img">
                </div>
                ''',
                unsafe_allow_html=True,
            )
        st.markdown('<div class="toolbar-right-tight">', unsafe_allow_html=True)
        about_clicked = st.button("About", use_container_width=True)
        compute_clicked = st.button("Compute", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

if about_clicked:
    st.session_state["show_about"] = not st.session_state.get("show_about", False)

if st.session_state.get("show_about", False):
    st.info(ABOUT_TEXT)

left_pane, right_pane = st.columns([0.95, 1.85], gap="medium")

with left_pane:
    st.markdown('<div class="left-pane">', unsafe_allow_html=True)
    st.subheader("Inputs")
    phi = st.number_input("φ (deg)", min_value=0.001, max_value=89.999, value=30.0, step=1.0, format="%.1f")
    beta = st.number_input("β (deg)", value=0.0, step=1.0, format="%.1f")

    if compute_clicked or st.session_state["ka"] is None:
        try:
            ka, kp = rankine_ka_kp(float(phi), float(beta))
            st.session_state["ka"] = ka
            st.session_state["kp"] = kp
            st.session_state["last_error"] = ""
            if abs(beta) > 1e-12:
                st.session_state["note"] = (
                    "For non-zero β, the program evaluates the published expressions directly; "
                    "see the teaching corner for their limitations."
                )
            else:
                st.session_state["note"] = "β = 0° gives the horizontal-backfill case."
        except Exception as e:
            st.session_state["ka"] = None
            st.session_state["kp"] = None
            st.session_state["note"] = ""
            st.session_state["last_error"] = str(e)

    st.subheader("Results")
    if st.session_state["last_error"]:
        st.error(st.session_state["last_error"])
    else:
        ka = st.session_state["ka"]
        kp = st.session_state["kp"]
        st.markdown(
            f'''
            <div class="result-card">
                <div class="result-main">Kₐ = {ka:.4f} &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; Kₚ = {kp:.4f}</div>
                <div>{st.session_state["note"]}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with right_pane:
    st.markdown('<div class="right-pane">', unsafe_allow_html=True)
    st.subheader("Teaching Corner")

    st.markdown("**Rankine formulas used by this program**")
    st.latex(r"K_a = \frac{\cos\beta\left(\cos\beta - \sqrt{\cos^2\beta - \cos^2\phi}\right)}{\cos\beta + \sqrt{\cos^2\beta - \cos^2\phi}}")
    st.latex(r"K_p = \frac{\cos\beta\left(\cos\beta + \sqrt{\cos^2\beta - \cos^2\phi}\right)}{\cos\beta - \sqrt{\cos^2\beta - \cos^2\phi}}")

    st.markdown(
        "Rankine, W. J. M. (1857). *On the stability of loose earth*. "
        "*Philosophical Transactions of the Royal Society of London*, 147, 9–27."
    )

    st.markdown("**Assumptions behind Rankine theory**")
    st.write(
        "Rankine’s original theory is derived for a cohesionless granular mass whose stability arises from internal "
        "friction alone. The wall is smooth, so wall friction is zero, and the stress state is governed by limiting "
        "frictional equilibrium. In the original 1857 paper, Rankine treated the case of a horizontal or uniformly "
        "sloping backfill."
    )

    st.markdown("**Why Rankine theory is not valid for non-zero backfill angle**")
    st.write(
        "Perhaps few have noticed that a positive (and therefore, favourable) angle β results in an unfavourable Kₚ "
        "coefficient (and vice versa). This is obviously not acceptable."
    )
    st.write(
        "Schematically, for sloping ground inclined at an angle of β to the horizontal, the active Rankine earth pressure "
        "is defined by point B in Figure 1 (σA′). The fact that σA′ > σA, as explained below, does not mean that σA′ is "
        "the correct answer to Rankine’s problem. In this context, point E provides the answer. Point E defines the "
        "corresponding passive Rankine earth pressure (σP′′), which is smaller than σP; the latter obviously should not "
        "be the case. This discrepancy is a strong indication that the line OE in Figure 1 does not represent the ground inclination."
    )
    st.write(
        "Another indication is that the vertical stress of the sloping ground in the active state is less than that of the "
        "horizontal ground (σν < σv), which is also incorrect."
    )
    st.write(
        "A third indication is that the same point in the ground has different vertical stress depending on whether the "
        "problem is examined from the active or passive perspective (i.e., σv′ ≠ σv″; point C ≠ point D). This is also "
        "not acceptable since the vertical stress in the ground should be independent of the state of the soil."
    )

    if FIGURE_FILE.exists():
        st.image(str(FIGURE_FILE), width=430)
        st.markdown('<div class="caption-center">Figure 1. Rankine’s theory for sloping ground for the active and passive state.</div>', unsafe_allow_html=True)

    st.markdown("**The paradox**")
    st.write(
        "For φ = 30° and β = 0°, Kₐ = 0.3333 and Kₚ = 3.0000. For β either +10° or −10°, Kₐ = 0.3495 and Kₚ = 2.7748."
    )
    st.write(
        "Thus, not only +10° and −10° give identical results, but also, the passive coefficient becomes smaller than the "
        "horizontal case, which is incorrect."
    )

    st.markdown("**Further reading**")
    st.write(
        "Pantelidis, L. (2024). *From EN 1998-5: 2004 to prEN 1998-5: 2023: Has the calculation of earth pressures improved "
        "or deteriorated?* In *Proceedings of the XVIII European Conference on Soil Mechanics and Geotechnical Engineering* "
        "(ECSMGE 2024), Lisbon, Portugal, 26–30 August 2024 (pp. 733–738). CRC Press."
    )
    st.markdown("DOI: https://doi.org/10.1201/9781003431749-121")
    st.markdown(
        "Direct download: "
        "https://www.issmge.org/uploads/publications/51/126/367_A_from_en_199852004_to_pren_199852023_has_the_calcul.pdf"
    )
    st.markdown("</div>", unsafe_allow_html=True)
