import json
from io import BytesIO
from pathlib import Path

import qrcode
import streamlit as st

st.set_page_config(
    page_title="CUT Geotechnical Engineering Lab",
    page_icon="🏗️",
    layout="wide",
)

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "hub_content.json"

if not CONFIG_FILE.exists():
    st.error(f"Configuration file not found: {CONFIG_FILE.name}")
    st.stop()

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    cfg = json.load(f)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def get_str(key: str, default: str = "") -> str:
    val = cfg.get(key, default)
    return val if isinstance(val, str) else default


def make_qr_image(data: str):
    qr = qrcode.QRCode(
        version=None,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img


def render_reference(ref: dict | str):
    if isinstance(ref, str):
        st.markdown(f"- {ref}")
        return

    text = ref.get("text", "").strip()
    doi = ref.get("doi", "").strip()
    url = ref.get("url", "").strip()

    if doi:
        st.markdown(f"- {text}  \n  DOI: [{doi}]({doi})")
    elif url:
        st.markdown(f"- {text}  \n  Link: [{url}]({url})")
    else:
        st.markdown(f"- {text}")


def render_qr_block(title: str, url: str):
    if not url.strip():
        return

    safe_key = (
        title.lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
    )

    with st.expander(f"📱 QR code for {title}", expanded=False):
        img = make_qr_image(url)

        buf = BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        st.image(png_bytes, caption=f"QR code for {title}", width=170)

        st.download_button(
            "Download QR code",
            data=png_bytes,
            file_name=f"{safe_key}_qr.png",
            mime="image/png",
            key=f"download_qr_{safe_key}_{abs(hash(url))}",
            use_container_width=True,
        )

def render_card(item: dict, button_label: str, url_key: str):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    title = item.get("title", "")
    tag = item.get("tag", "")
    desc = item.get("description", "")
    note = item.get("note", "")
    url = item.get(url_key, "")
    version = item.get("version", "").strip()

    st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)

    meta_parts = []
    if tag:
        meta_parts.append(f'<span class="card-tag">{tag}</span>')
    if version:
        meta_parts.append(f'<span class="version-pill">Version: {version}</span>')

    if meta_parts:
        st.markdown(" ".join(meta_parts), unsafe_allow_html=True)

    if desc:
        st.markdown(f'<div class="card-text">{desc}</div>', unsafe_allow_html=True)

    if url.strip():
        st.link_button(button_label, url, use_container_width=True)
    else:
        st.info("Link not provided.")

    if note:
        st.markdown(f'<div class="mini-note">{note}</div>', unsafe_allow_html=True)

    render_qr_block(title, url)

    # ---- CITATION BLOCK ----
    citations = cfg.get("software_citations", [])
    match = next((c for c in citations if c.get("title") == title), None)

    if match:
        citation = match.get("software_citation", "").strip()
        bibtex = match.get("software_citation_bibtex", "").strip()

        if citation:
            with st.expander("📖 Cite this software", expanded=False):
                st.code(citation, language=None)

                st.download_button(
                    "Download citation (.txt)",
                    data=citation.encode("utf-8"),
                    file_name=f"{title.lower().replace(' ', '_')}_citation.txt",
                    mime="text/plain",
                    key=f"citation_txt_{title}_{button_label}_{abs(hash(url))}",
                    use_container_width=True,
                )

        if bibtex:
            with st.expander("BibTeX", expanded=False):
                st.code(bibtex, language="bibtex")

                st.download_button(
                    "Download BibTeX (.bib)",
                    data=bibtex.encode("utf-8"),
                    file_name=f"{title.lower().replace(' ', '_')}.bib",
                    mime="text/plain",
                    key=f"citation_bib_{title}_{button_label}_{abs(hash(url))}",
                    use_container_width=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)



def render_doc_card(item: dict):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    title = item.get("title", "")
    tag = item.get("tag", "")
    desc = item.get("description", "")
    manual_url = item.get("manual_url", "")
    refs = item.get("references", [])
    version = item.get("version", "").strip()

    st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)

    meta_parts = []
    if tag:
        meta_parts.append(f'<span class="card-tag">{tag}</span>')
    if version:
        meta_parts.append(f'<span class="version-pill">Version: {version}</span>')

    if meta_parts:
        st.markdown(" ".join(meta_parts), unsafe_allow_html=True)

    if desc:
        st.markdown(f'<div class="card-text">{desc}</div>', unsafe_allow_html=True)

    if manual_url.strip():
        st.link_button("Open Manual", manual_url, use_container_width=True)
        render_qr_block(f"{title} manual", manual_url)
    else:
        st.info("Add manual link here.")

    with st.expander("References", expanded=False):
        if refs and isinstance(refs, list):
            for ref in refs:
                render_reference(ref)
        else:
            st.write("Add references here.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_citation_block(item: dict):
    title = item.get("title", "")
    version = item.get("version", "")
    citation = item.get("software_citation", "").strip()
    bibtex = item.get("software_citation_bibtex", "").strip()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)

    if version:
        st.markdown(f'<span class="version-pill">Version: {version}</span>', unsafe_allow_html=True)

    if citation:
        st.markdown('<div class="ref-title">Recommended software citation</div>', unsafe_allow_html=True)
        st.code(citation, language=None)

        st.download_button(
            "Download citation (.txt)",
            data=citation.encode("utf-8"),
            file_name=f"{title.lower().replace(' ', '_')}_citation.txt",
            mime="text/plain",
            key=f"citation_txt_{title}_{version}",
            use_container_width=True,
        )
    else:
        st.info("Add software citation text in the JSON file.")

    if bibtex:
        with st.expander("BibTeX", expanded=False):
            st.code(bibtex, language="bibtex")
            st.download_button(
                "Download BibTeX (.bib)",
                data=bibtex.encode("utf-8"),
                file_name=f"{title.lower().replace(' ', '_')}.bib",
                mime="text/plain",
                key=f"citation_bib_{title}_{version}",
                use_container_width=True,
            )
    else:
        st.info("Add BibTeX entry in the JSON file.")

    st.markdown("</div>", unsafe_allow_html=True)

def render_updates():
    updates = cfg.get("updates", [])
    repo = cfg.get("github_repo", "")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Latest updates</div>', unsafe_allow_html=True)

    if updates:
        for u in updates:
            date = u.get("date", "")
            text = u.get("text", "")
            st.markdown(f"**{date}** — {text}")
    else:
        st.write("No updates listed.")

    st.markdown("<br>", unsafe_allow_html=True)

    if repo:
        st.link_button("Follow updates on GitHub", repo, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)
# -------------------------------------------------
# STYLE
# -------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --cut-blue: #003b71;
        --cut-light-blue: #0d5c9f;
        --soft-border: rgba(0, 59, 113, 0.12);
        --card-bg: #ffffff;
        --text-main: #15324b;
        --text-muted: #5d6d7e;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    .uni-line {
        font-size: 0.98rem;
        font-weight: 700;
        color: var(--cut-blue);
        margin-bottom: 0.15rem;
    }

    .dept-line {
        font-size: 0.96rem;
        color: var(--text-muted);
        margin-bottom: 0.85rem;
    }

    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--text-main);
        line-height: 1.15;
        margin-bottom: 0.35rem;
    }

    .sub-title {
        font-size: 1.02rem;
        color: var(--text-muted);
        line-height: 1.5;
        margin-bottom: 0.25rem;
        max-width: 900px;
    }

    .divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(0,59,113,0.25), rgba(0,59,113,0.05));
        margin: 1.2rem 0 1.4rem 0;
    }

    .section-intro {
        font-size: 0.95rem;
        color: var(--text-muted);
        margin-bottom: 1rem;
    }

    .card {
        background: var(--card-bg);
        border: 1px solid var(--soft-border);
        border-radius: 18px;
        padding: 1.1rem 1.1rem 1rem 1.1rem;
        box-shadow: 0 8px 22px rgba(17, 36, 56, 0.05);
        height: 100%;
        margin-bottom: 1rem;
    }

    .card-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--cut-blue);
        margin-bottom: 0.2rem;
    }

    .card-tag {
        display: inline-block;
        font-size: 0.78rem;
        color: var(--cut-light-blue);
        background: rgba(13, 92, 159, 0.08);
        border: 1px solid rgba(13, 92, 159, 0.12);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        margin-bottom: 0.65rem;
        margin-right: 0.4rem;
    }

    .version-pill {
        display: inline-block;
        font-size: 0.78rem;
        color: #7a5b20;
        background: rgba(199, 168, 109, 0.14);
        border: 1px solid rgba(199, 168, 109, 0.24);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        margin-bottom: 0.65rem;
    }

    .card-text {
        font-size: 0.96rem;
        color: var(--text-muted);
        line-height: 1.55;
        margin-bottom: 0.95rem;
    }

    .mini-note {
        font-size: 0.88rem;
        color: var(--text-muted);
        margin-top: 0.35rem;
    }

    .soft-panel {
        background: linear-gradient(180deg, rgba(0,59,113,0.03), rgba(0,59,113,0.015));
        border: 1px solid var(--soft-border);
        border-radius: 18px;
        padding: 1rem 1rem 0.9rem 1rem;
        margin-top: 1rem;
    }

    .soft-panel-title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--cut-blue);
        margin-bottom: 0.35rem;
    }

    .ref-title {
        font-size: 0.92rem;
        font-weight: 700;
        color: var(--cut-blue);
        margin-top: 0.8rem;
        margin-bottom: 0.35rem;
    }

    .footer-text {
        font-size: 0.92rem;
        color: var(--text-muted);
        line-height: 1.6;
    }

    div[data-baseweb="tab-list"] {
        gap: 0.65rem;
        background: #eaf0f6;
        border: 1px solid rgba(0,59,113,0.10);
        padding: 0.38rem;
        border-radius: 16px;
        margin-bottom: 1.25rem;
    }

    button[data-baseweb="tab"] {
        height: 48px;
        padding: 0 1.1rem;
        border-radius: 12px !important;
        background: transparent !important;
        color: #4a6278 !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        border: 1px solid transparent !important;
    }

    button[data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.75) !important;
        color: var(--cut-blue) !important;
        border: 1px solid rgba(0,59,113,0.08) !important;
    }

    button[aria-selected="true"][data-baseweb="tab"] {
        background: #ffffff !important;
        color: var(--cut-blue) !important;
        border: 1px solid rgba(0,59,113,0.14) !important;
        box-shadow: 0 4px 12px rgba(0,59,113,0.08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# HEADER
# -------------------------------------------------
logo_col, text_col = st.columns([1.15, 3.85], vertical_alignment="center")

with logo_col:
    logo_url = get_str("logo_url")
    if logo_url:
        st.image(logo_url, width=280)

with text_col:
    st.markdown(f'<div class="uni-line">{get_str("university_name")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dept-line">{get_str("department_name")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="main-title">{get_str("hub_title")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-title">{get_str("hub_subtitle")}</div>', unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# TABS
# -------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Web Applications",
    "Desktop Programs (.exe)",
    "Manuals / Documentation",
    "Updates",
    "About / Citation / Contact"
])

with tab1:
    st.markdown(
        '<div class="section-intro">Interactive browser-based tools for immediate use on desktop, tablet, and phone, without local installation.</div>',
        unsafe_allow_html=True,
    )
    st.caption("Compatible with Windows, macOS, iOS, Android, and all modern web browsers.")
    
    web_apps = cfg.get("web_applications", [])
    cols = st.columns(2, gap="large")
    for i, item in enumerate(web_apps):
        with cols[i % 2]:
            render_card(item, "Open Web App", "url")

with tab2:
    st.markdown(
        '<div class="section-intro">Standalone Windows executables for offline and local desktop use.</div>',
        unsafe_allow_html=True,
    )

    desktop_programs = cfg.get("desktop_programs", [])
    cols = st.columns(2, gap="large")
    for i, item in enumerate(desktop_programs):
        with cols[i % 2]:
            render_card(item, "Download .exe", "url")

with tab3:
    st.markdown(
        '<div class="section-intro">Supporting manuals, explanatory material, and references for the software suite.</div>',
        unsafe_allow_html=True,
    )

    docs = cfg.get("documentation", [])
    cols = st.columns(2, gap="large")
    for i, item in enumerate(docs):
        with cols[i % 2]:
            render_doc_card(item)

with tab4:
    st.markdown(
        '<div class="section-intro">Latest releases, updates, and new tools.</div>',
        unsafe_allow_html=True,
    )
    render_updates()
    
with tab5:
    st.markdown(
        '<div class="section-intro">Institutional information, software citation guidance, disclaimer, and contact details.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.4, 1], gap="large")

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">About</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="footer-text">'
            'This platform provides centralized access to the CUT geotechnical software suite developed within the academic environment '
            'of the Cyprus University of Technology. The tools are intended to support research, teaching, and technical study in geotechnical engineering.'
            '<br><br>'
            '<b>Disclaimer</b><br>'
            'The software is provided for research and educational purposes. While every effort has been made to ensure correctness and consistency, '
            'no warranty is provided, and the author assumes no liability for the use of results in engineering practice.'
            '<br><br>'
            '<b>Contact</b><br>'
            f'{get_str("contact_text")}'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Citation guidance</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="footer-text">'
            'If these tools are used in research, teaching material, theses, or reports, the relevant publications and the software version should be cited.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

