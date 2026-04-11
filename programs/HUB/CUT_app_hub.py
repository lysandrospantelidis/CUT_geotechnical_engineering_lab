from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="CUT Geotechnical Engineering Lab",
    page_icon="🏗️",
    layout="wide",
)

# -----------------------------
# SETTINGS
# -----------------------------
HUB_TITLE = "CUT Geotechnical Engineering Lab"
HUB_SUBTITLE = "Web applications, desktop tools, and documentation"

BEARING_WEB_URL = "https://cut-bearing-capacity.streamlit.app/"
COULOMB_WEB_URL = "https://cut-k-coulomb.streamlit.app/"

BEARING_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/v7.1/CUT_Bearing_capacity_updated_v7_2.exe"
COULOMB_EXE_URL = "https://github.com/lysandrospantelidis/CUT_geotechnical_engineering_lab/releases/download/v1.0.0-k-coulomb/CUT_K_Coulomb.exe"

MANUAL_BEARING_URL = ""
MANUAL_COULOMB_URL = ""

LOGO_PATH = Path(__file__).resolve().parent / "cut_logo.png"
BRAND_PATH = Path(__file__).resolve().parent / "Cut bearing capacity.png"

# -----------------------------
# STYLE
# -----------------------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #666666;
        margin-bottom: 1.5rem;
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 1.2rem;
        margin-bottom: 0.6rem;
    }
    .card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 16px;
        padding: 1.1rem 1rem 1rem 1rem;
        margin-bottom: 1rem;
        background: rgba(255,255,255,0.02);
    }
    .card-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .card-text {
        font-size: 0.96rem;
        color: #555555;
        margin-bottom: 0.8rem;
    }
    .footer-note {
        font-size: 0.9rem;
        color: #666666;
        margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# HEADER
# -----------------------------
top1, top2 = st.columns([1, 4])

with top1:
    if BRAND_PATH.exists():
        st.image(str(BRAND_PATH), width=170)
    elif LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=130)

with top2:
    st.markdown(f'<div class="main-title">{HUB_TITLE}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-title">{HUB_SUBTITLE}</div>', unsafe_allow_html=True)
    st.write(
        "Central access point for the CUT geotechnical software suite, including "
        "bearing-capacity tools, Coulomb earth-pressure tools, executable downloads, "
        "and supporting documentation."
    )

st.markdown("---")

# -----------------------------
# WEB APPLICATIONS
# -----------------------------
st.markdown('<div class="section-title">Web Applications</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">CUT Bearing Capacity</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'Web application for the bearing-capacity assessment of shallow foundations, '
        'including soil compressibility, groundwater effects, seismic effects, '
        'reinforcement, and one-layer / two-layer soil cases.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.link_button("Open Web App", BEARING_WEB_URL, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">CUT K Coulomb</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'Web application for Coulomb earth-pressure calculations with user-defined '
        'ground-surface geometry and graphical visualization of the mechanism.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.link_button("Open Web App", COULOMB_WEB_URL, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# DESKTOP TOOLS
# -----------------------------
st.markdown('<div class="section-title">Desktop Programs (.exe)</div>', unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">CUT Bearing Capacity (.exe)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'Standalone Windows executable for desktop use.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.link_button("Download .exe", BEARING_EXE_URL, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">CUT K Coulomb (.exe)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'Standalone Windows executable for the Coulomb earth-pressure tool.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.link_button("Download .exe", COULOMB_EXE_URL, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# DOCUMENTATION
# -----------------------------
st.markdown('<div class="section-title">Documentation</div>', unsafe_allow_html=True)

col5, col6 = st.columns(2)

with col5:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Bearing Capacity Manual</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'User manual and documentation for the CUT Bearing Capacity program.'
        '</div>',
        unsafe_allow_html=True,
    )
    if MANUAL_BEARING_URL.strip():
        st.link_button("Open Manual", MANUAL_BEARING_URL, use_container_width=True)
    else:
        st.info("Add manual URL here when ready.")
    st.markdown("</div>", unsafe_allow_html=True)

with col6:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Coulomb Tool Manual</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-text">'
        'User manual and supporting documentation for the CUT K Coulomb tool.'
        '</div>',
        unsafe_allow_html=True,
    )
    if MANUAL_COULOMB_URL.strip():
        st.link_button("Open Manual", MANUAL_COULOMB_URL, use_container_width=True)
    else:
        st.info("Add manual URL here when ready.")
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# ABOUT / CITATION
# -----------------------------
st.markdown('<div class="section-title">About</div>', unsafe_allow_html=True)

st.markdown(
    """
    This hub provides access to the CUT geotechnical tools developed for academic,
    educational, and research use.

    Please cite the relevant publications and software source when using the tools
    in research outputs, teaching material, or professional reports.
    """
)

st.markdown(
    '<div class="footer-note">Developed by Dr Lysandros Pantelidis, Cyprus University of Technology.</div>',
    unsafe_allow_html=True,
)