import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import qrcode
import streamlit as st
from urllib.request import Request, urlopen

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

GITHUB_OWNER = cfg.get("github_owner", "").strip()
GITHUB_REPO = cfg.get("github_repo_name", "").strip()
GITHUB_BRANCH = cfg.get("github_branch", "main").strip()
GITHUB_REPO_URL = cfg.get("github_repo_url", "").strip()
UPDATES_COUNT = int(cfg.get("updates_count", 5))
SHARE_URL = cfg.get("share_url", "").strip()

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def get_str(key: str, default: str = "") -> str:
    val = cfg.get(key, default)
    return val if isinstance(val, str) else default


def slugify(text: str) -> str:
    return (
        text.lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace(":", "")
        .replace(",", "")
    )


def make_qr_image(data: str):
    qr = qrcode.QRCode(version=None, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def format_date(date_text: str) -> str:
    if not date_text:
        return ""
    try:
        dt = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_text


def version_tuple_to_str(version_tuple):
    if not version_tuple:
        return ""
    return ".".join(str(x) for x in version_tuple)


def parse_version_tuple(text: str):
    if not text:
        return ()
    match = re.search(r"[vV](\d+(?:[._-]\d+)*)", text)
    if not match:
        return ()
    raw = match.group(1)
    parts = re.split(r"[._-]", raw)
    out = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
    return tuple(out)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "CUT-Geotechnical-Hub",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


@st.cache_data(ttl=600, show_spinner=False)
def get_releases(owner: str, repo: str):
    if not owner or not repo:
        return []
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=30"
    data = fetch_json(url)
    return data if isinstance(data, list) else []


def find_release_asset(item: dict):
    releases = get_releases(GITHUB_OWNER, GITHUB_REPO)

    tag_contains = item.get("release_tag_contains", "").strip().lower()
    asset_name_contains = item.get("asset_name_contains", "").strip().lower()
    asset_ext = item.get("asset_ext", "").strip().lower()

    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue

        tag_name = rel.get("tag_name", "")
        if tag_contains and tag_contains not in tag_name.lower():
            continue

        assets = rel.get("assets", [])
        for asset in assets:
            asset_name = asset.get("name", "")
            asset_name_l = asset_name.lower()

            if asset_name_contains and asset_name_contains not in asset_name_l:
                continue
            if asset_ext and not asset_name_l.endswith(asset_ext):
                continue

            version_tuple = parse_version_tuple(tag_name) or parse_version_tuple(asset_name)
            return {
                "version": version_tuple_to_str(version_tuple) or tag_name,
                "tag_name": tag_name,
                "published_at": rel.get("published_at", ""),
                "release_name": rel.get("name", "") or tag_name,
                "release_body": rel.get("body", "") or "",
                "release_html_url": rel.get("html_url", ""),
                "asset_name": asset_name,
                "asset_url": asset.get("browser_download_url", ""),
            }

    return None


@st.cache_data(ttl=600, show_spinner=False)
def get_repo_folder_contents(owner: str, repo: str, branch: str, folder_path: str):
    if not owner or not repo or not folder_path:
        return []

    encoded_path = quote(folder_path.strip("/"), safe="/")
    encoded_ref = quote(branch)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={encoded_ref}"
    data = fetch_json(url)
    return data if isinstance(data, list) else []


def find_manual_file(item: dict):
    folder = item.get("manual_repo_folder", "").strip()
    file_contains = item.get("manual_file_contains", "").strip().lower()

    if not folder:
        return None

    entries = get_repo_folder_contents(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, folder)
    candidates = []

    for entry in entries:
        if entry.get("type") != "file":
            continue

        name = entry.get("name", "")
        name_l = name.lower()

        if not name_l.endswith(".pdf"):
            continue
        if file_contains and file_contains not in name_l:
            continue

        version_tuple = parse_version_tuple(name)
        candidates.append(
            {
                "name": name,
                "html_url": entry.get("html_url", ""),
                "download_url": entry.get("download_url", ""),
                "version_tuple": version_tuple,
                "version": version_tuple_to_str(version_tuple),
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (x["version_tuple"], x["name"].lower()),
        reverse=True
    )
    return candidates[0]


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

    safe_key = slugify(title)
    st.markdown("### QR code")

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


def render_software_citation(title: str, version: str, key_suffix: str):
    citations = cfg.get("software_citations", [])
    match = next((c for c in citations if c.get("title") == title), None)

    if not match:
        return

    citation = match.get("software_citation", "").strip()
    bibtex = match.get("software_citation_bibtex", "").strip()

    if citation:
        if version and "(Version" not in citation:
            citation = citation.replace("[Software].", f"(Version {version}) [Software].")
        st.markdown("### Cite this software")
        st.code(citation, language=None)

        st.download_button(
            "Download citation (.txt)",
            data=citation.encode("utf-8"),
            file_name=f"{slugify(title)}_citation.txt",
            mime="text/plain",
            key=f"citation_txt_{title}_{key_suffix}",
            use_container_width=True,
        )

    if bibtex:
        if version and "version" not in bibtex.lower():
            bibtex = bibtex.rstrip("}") + f",\n  version      = {{{version}}}\n}}"

        st.markdown("### BibTeX")
        st.code(bibtex, language="bibtex")

        st.download_button(
            "Download BibTeX (.bib)",
            data=bibtex.encode("utf-8"),
            file_name=f"{slugify(title)}.bib",
            mime="text/plain",
            key=f"citation_bib_{title}_{key_suffix}",
            use_container_width=True,
        )


def render_card(item: dict, button_label: str, mode: str):
    title = item.get("title", "")
    tag = item.get("tag", "")
    desc = item.get("description", "")
    note = item.get("note", "")

    release_info = find_release_asset(item)
    version = release_info["version"] if release_info else ""

    header_text = f"📦 {title}"
    if version:
        header_text += f" — {version}"

    with st.expander(header_text, expanded=False):
        st.markdown('<div class="card">', unsafe_allow_html=True)

        meta_parts = []
        if tag:
            meta_parts.append(f'<span class="card-tag">{tag}</span>')
        if version:
            meta_parts.append(f'<span class="version-pill">Version: {version}</span>')

        if meta_parts:
            st.markdown(" ".join(meta_parts), unsafe_allow_html=True)

        if desc:
            st.markdown(f'<div class="card-text">{desc}</div>', unsafe_allow_html=True)

        if mode == "web":
            app_url = item.get("url", "").strip()
            if app_url:
                st.link_button(button_label, app_url, use_container_width=True)
                render_qr_block(title, app_url)
            else:
                st.info("Web app link not provided.")

        elif mode == "desktop":
            exe_url = release_info["asset_url"] if release_info else ""
            if exe_url:
                st.link_button(button_label, exe_url, use_container_width=True)
                render_qr_block(title, exe_url)
            else:
                st.warning("No matching .exe found in GitHub Releases.")

        if release_info:
            release_date = format_date(release_info.get("published_at", ""))
            if release_date:
                st.markdown(f"**Release date:** {release_date}")
            if release_info.get("release_html_url"):
                st.link_button("Open release page", release_info["release_html_url"], use_container_width=True)

        if note:
            st.markdown(f'<div class="mini-note">{note}</div>', unsafe_allow_html=True)

        render_software_citation(title, version, f"{mode}_{title}")

        st.markdown("</div>", unsafe_allow_html=True)


def render_doc_card(item: dict):
    title = item.get("title", "")
    tag = item.get("tag", "")
    desc = item.get("description", "")
    refs = item.get("references", [])

    release_info = find_release_asset(item)
    software_version = release_info["version"] if release_info else ""

    manual_info = find_manual_file(item)
    manual_version = manual_info["version"] if manual_info else ""

    header_text = f"📘 {title}"
    if software_version:
        header_text += f" — {software_version}"
    elif manual_version:
        header_text += f" — manual v{manual_version}"

    with st.expander(header_text, expanded=False):
        st.markdown('<div class="card">', unsafe_allow_html=True)

        meta_parts = []
        if tag:
            meta_parts.append(f'<span class="card-tag">{tag}</span>')
        if software_version:
            meta_parts.append(f'<span class="version-pill">Software version: {software_version}</span>')
        if manual_version:
            meta_parts.append(f'<span class="version-pill">Manual version: {manual_version}</span>')

        if meta_parts:
            st.markdown(" ".join(meta_parts), unsafe_allow_html=True)

        if desc:
            st.markdown(f'<div class="card-text">{desc}</div>', unsafe_allow_html=True)

        if manual_info:
            col1, col2 = st.columns(2)

            with col1:
                if manual_info.get("html_url"):
                    st.link_button("View manual online", manual_info["html_url"], use_container_width=True)

            with col2:
                if manual_info.get("download_url"):
                    st.link_button("Download manual", manual_info["download_url"], use_container_width=True)

            if manual_info.get("html_url"):
                render_qr_block(f"{title} manual", manual_info["html_url"])
        else:
            st.warning("No matching manual PDF found in the configured repository folder.")

        st.markdown("### References")
        if refs and isinstance(refs, list):
            for ref in refs:
                render_reference(ref)
        else:
            st.write("No references listed.")

        st.markdown("</div>", unsafe_allow_html=True)


def render_updates():
    releases = get_releases(GITHUB_OWNER, GITHUB_REPO)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Recent software release links</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="footer-text">'
        'The links below lead directly to the latest public release pages of the software hosted in the repository.'
        '</div>',
        unsafe_allow_html=True,
    )

    public_releases = [
        r for r in releases
        if not r.get("draft") and not r.get("prerelease")
    ][:UPDATES_COUNT]

    if public_releases:
        for rel in public_releases:
            tag = rel.get("tag_name", "")
            name = rel.get("name", "") or tag
            date = format_date(rel.get("published_at", ""))
            label = f"{date} — {name}" if date else name

            if rel.get("html_url"):
                st.link_button(label, rel["html_url"], use_container_width=True)
    else:
        st.write("No public release links found.")

    if GITHUB_REPO_URL:
        st.markdown("### Repository")
        st.link_button("Open GitHub repository", GITHUB_REPO_URL, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


def build_share_links(url: str):
    encoded_url = quote(url, safe="")
    encoded_mail_body = quote(
        "Please consider sharing this platform with colleagues, students, researchers, and practicing engineers:\n\n" + url,
        safe=""
    )
    encoded_mail_subject = quote("CUT Geotechnical Engineering Lab", safe="")

    return {
        "LinkedIn": f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}",
        "Facebook": f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}",
        "Twitter/X": f"https://twitter.com/intent/tweet?url={encoded_url}",
        "Email": f"mailto:?subject={encoded_mail_subject}&body={encoded_mail_body}",
    }


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
        margin-right: 0.4rem;
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Web Applications",
    "Desktop Programs (.exe)",
    "Manuals / Documentation",
    "Release Links",
    "About / Citation",
    "Share",
    "Contact"
])

with tab1:
    st.markdown(
        '<div class="section-intro">Interactive browser-based tools for immediate use on desktop, tablet, and phone, without local installation.</div>',
        unsafe_allow_html=True,
    )
    st.caption("Compatible with Windows, macOS, iOS, Android, and all modern web browsers.")

    for item in cfg.get("web_applications", []):
        render_card(item, "Open Web App", "web")

with tab2:
    st.markdown(
        '<div class="section-intro">Standalone Windows executables for offline and local desktop use.</div>',
        unsafe_allow_html=True,
    )

    for item in cfg.get("desktop_programs", []):
        render_card(item, "Download .exe", "desktop")

with tab3:
    st.markdown(
        '<div class="section-intro">Supporting manuals, explanatory material, and references for the software suite.</div>',
        unsafe_allow_html=True,
    )

    for item in cfg.get("documentation", []):
        render_doc_card(item)

with tab4:
    st.markdown(
        '<div class="section-intro">Direct links to recent public software releases.</div>',
        unsafe_allow_html=True,
    )
    render_updates()

with tab5:
    st.markdown(
        '<div class="section-intro">Institutional information, software citation guidance, and disclaimer.</div>',
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

with tab6:
    st.markdown(
        '<div class="section-intro">Please consider sharing this platform with colleagues, students, researchers, and practicing engineers who may benefit from these tools. Wider sharing helps the software reach the academic and professional communities it was developed to support.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Share this platform</div>', unsafe_allow_html=True)

    if SHARE_URL:
        share_text = """CUT Apps – Geotechnical engineering tools (bearing capacity, earth pressures & more):
https://cut-apps.streamlit.app/"""

        encoded = quote(share_text, safe="")

        wa_url = f"https://wa.me/?text={encoded}"
        email_url = f"mailto:?subject=CUT Apps&body={encoded}"

        share_links = build_share_links(SHARE_URL)

        st.markdown("### 📲 Share CUT Apps")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.link_button("WhatsApp", wa_url, use_container_width=True)

        with col2:
            st.link_button("Email", email_url, use_container_width=True)

        with col3:
            st.link_button("LinkedIn", share_links["LinkedIn"], use_container_width=True)

        with col4:
            st.link_button("Facebook", share_links["Facebook"], use_container_width=True)

        with col5:
            st.link_button("Twitter/X", share_links["Twitter/X"], use_container_width=True)

        st.markdown("#### or")

        st.text_area("Copy message", share_text, height=80)

        render_qr_block("CUT Apps Hub", SHARE_URL)

    else:
        st.info("Share URL not configured.")

    st.markdown("</div>", unsafe_allow_html=True)

with tab7:
    st.markdown(
        '<div class="section-intro">Contact information and academic profiles.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 1], gap="large")

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Contact Information</div>', unsafe_allow_html=True)

        contact_text = get_str("contact_text")
        if contact_text:
            st.markdown(
                f'<div class="footer-text">{contact_text}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Contact information not configured.")

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Academic Profiles</div>', unsafe_allow_html=True)

        for item in cfg.get("contact_links", []):
            label = item.get("label", "").strip()
            url = item.get("url", "").strip()
            if label and url:
                st.link_button(label, url, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)
