# -*- coding: utf-8 -*-
import base64
from pathlib import Path
import streamlit as st

from CUT_Rock_key_data import (
    APP_LINK,
    ORIGINAL_LINK,
    ROCK_INFO_EN,
    ROCK_INFO_EL,
    NODES_EN,
    NODES_EL,
    UI_STR,
)

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="Rock Identification Key", layout="wide", initial_sidebar_state="collapsed")

def img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime = "image/png"
    if path.suffix.lower() in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"

def existing_path(*names: str):
    for name in names:
        p = BASE_DIR / name
        if p.exists():
            return p
    return None

def result_image_path(rock_id: str):
    candidates = [
        f"{rock_id}.jpg", f"{rock_id}.jpeg", f"{rock_id}.png",
        f"{rock_id.lower()}.jpg", f"{rock_id.lower()}.jpeg", f"{rock_id.lower()}.png",
        f"{rock_id.capitalize()}.jpg", f"{rock_id.capitalize()}.jpeg", f"{rock_id.capitalize()}.png",
    ]
    return existing_path(*candidates)

def init_state():
    if "lang" not in st.session_state:
        st.session_state.lang = "en"
    if "current" not in st.session_state:
        st.session_state.current = "1"
    if "history" not in st.session_state:
        st.session_state.history = []
    if "show_info" not in st.session_state:
        st.session_state.show_info = False

def go_to(next_id: str):
    st.session_state.history.append(st.session_state.current)
    st.session_state.current = next_id
    st.session_state.show_info = False

def go_back():
    if st.session_state.history:
        st.session_state.current = st.session_state.history.pop()
        st.session_state.show_info = False

def go_home():
    st.session_state.history = []
    st.session_state.current = "1"
    st.session_state.show_info = False

def render_clickable_image(path, url: str, max_height: int = 60, fallback_text: str = ""):
    if path and path.exists():
        uri = img_to_data_uri(path)
        st.markdown(
            f'<a href="{url}" target="_blank"><img src="{uri}" style="max-height:{max_height}px;width:auto;display:block;"></a>',
            unsafe_allow_html=True,
        )
    elif fallback_text:
        st.markdown(f'<a href="{url}" target="_blank">{fallback_text}</a>', unsafe_allow_html=True)

def info_text(ui: dict, rock: dict, rock_id: str) -> str:
    return ui["info_text"].format(
        name=rock.get("name", rock_id),
        type=rock["type"],
        minerals=rock["minerals"],
        look=rock["look"],
        formation=rock["formation"],
        compare=rock["compare"],
    )

init_state()

st.markdown(
    '''
    <style>
    .block-container {padding-top: 2.2rem; padding-bottom: 1rem;}
    .top-title {
        font-size: 2.1rem;
        font-weight: 800;
        line-height: 1.2;
        padding-top: 0.15rem;
        margin-bottom: .35rem;
    }
    .top-desc {color: #dce9f5; font-size: 1.02rem; line-height: 1.45;}
    .panel-title {font-size: 1.2rem; font-weight: 700; margin-bottom: .6rem;}
    .rock-result {font-size: 1.45rem; font-weight: 800; margin-bottom: .8rem;}
    .small-note {color: #5b6773; font-style: italic; margin-top: .6rem;}
    div.stButton > button {width: 100%; border-radius: 10px; padding-top: .7rem; padding-bottom: .7rem; font-weight: 700;}
    </style>
    ''',
    unsafe_allow_html=True,
)

lang = st.session_state.lang
ui = UI_STR[lang]
nodes = {"el": NODES_EL, "en": NODES_EN}[lang]
rocks = {"el": ROCK_INFO_EL, "en": ROCK_INFO_EN}[lang]

logo_path = existing_path("university_logo.png", "university_logo.jpg", "university_logo.jpeg", "logo.png", "logo.jpg", "logo.jpeg")
home_path = existing_path("home.png", "home.jpg", "home.jpeg")

top_left, top_mid, top_right = st.columns([1.2, 3.5, 1.8], vertical_alignment="top")
with top_left:
    if logo_path:
        st.image(str(logo_path), use_container_width=True)
with top_mid:
    st.markdown(f'<div class="top-title">{ui["intro_title"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="top-desc">{ui["intro_body"]}</div>', unsafe_allow_html=True)
with top_right:
    choice = st.selectbox(
        ui["lang_label"],
        ["English", "Ελληνικά"],
        index=0 if st.session_state.lang == "en" else 1,
    )
    new_lang = "el" if choice.startswith("Ε") else "en"
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    render_clickable_image(home_path, APP_LINK, max_height=70, fallback_text=ui["portal"])

btn1, btn2 = st.columns([1.4, 4.6])
with btn1:
    st.link_button(ui["orig_btn"], ORIGINAL_LINK, use_container_width=True)
with btn2:
    with st.expander(ui["about"]):
        if lang == "el":
            st.write(
                "Dr Lysandros Pantelidis  \n"
                "Cyprus University of Technology  \n"
                "Department of Civil Engineering and Geomatics  \n\n"
                "Rock Identification Key GUI  \n"
                "Version 1.0  \n"
                "Educational tool  \n\n"
                "Το πρόγραμμα προσφέρει μόνο web app και exe έκδοση του "
                "The Rock Identification Key - by Don Peck. "
                "Δεν αλλάζει τον αλγόριθμο ταυτοποίησης."
            )
        else:
            st.write(
                "Dr Lysandros Pantelidis  \n"
                "Cyprus University of Technology  \n"
                "Department of Civil Engineering and Geomatics  \n\n"
                "Rock Identification Key GUI  \n"
                "Version 1.0  \n"
                "Educational tool  \n\n"
                "This program only offers a web app and an exe version of "
                "The Rock Identification Key - by Don Peck. "
                "It does not change the identification algorithm."
            )

lang = st.session_state.lang
ui = UI_STR[lang]
nodes = {"el": NODES_EL, "en": NODES_EN}[lang]
rocks = {"el": ROCK_INFO_EL, "en": ROCK_INFO_EN}[lang]
current = st.session_state.current

left, right = st.columns(2, gap="large")

with left:
    st.markdown(f'<div class="panel-title">{ui["questions_header"]}</div>', unsafe_allow_html=True)

    if current in rocks:
        st.success(rocks[current].get("name", current))
        nav1, nav2, nav3, nav4 = st.columns(4)
        with nav1:
            st.button(ui["back"], on_click=go_back, use_container_width=True)
        with nav2:
            st.button(ui["home"], on_click=go_home, use_container_width=True)
        with nav3:
            if st.button(ui["info"], use_container_width=True):
                st.session_state.show_info = not st.session_state.show_info
        with nav4:
            st.link_button(ui["wiki"], rocks[current].get("link", ORIGINAL_LINK), use_container_width=True)

        if st.session_state.show_info:
            st.text_area(
                ui["info"],
                value=info_text(ui, rocks[current], current),
                height=320,
                key=f"info_box_{current}_{lang}",
            )
    else:
        node = nodes[current]
        st.subheader(node.get("text", ""))
        if node.get("explanation"):
            st.caption(node["explanation"])

        yes_col, no_col = st.columns(2)
        with yes_col:
            if st.button(f'{ui["yes"]} — {node.get("yes_text","")}', use_container_width=True):
                go_to(node["yes"])
                st.rerun()
        with no_col:
            if st.button(f'{ui["no"]} — {node.get("no_text","")}', use_container_width=True):
                go_to(node["no"])
                st.rerun()

        nav1, nav2 = st.columns(2)
        with nav1:
            st.button(ui["back"], on_click=go_back, use_container_width=True)
        with nav2:
            st.button(ui["home"], on_click=go_home, use_container_width=True)

        st.markdown(f'<div class="small-note">{ui["note"]}</div>', unsafe_allow_html=True)
        with st.expander(ui["help_defs"]):
            st.write(ui["gloss"])

with right:
    st.markdown(f'<div class="panel-title">{ui["result_header"]}</div>', unsafe_allow_html=True)

    if current in rocks:
        rock = rocks[current]
        st.markdown(f'<div class="rock-result">{rock.get("name", current)} — {rock["type"]}</div>', unsafe_allow_html=True)
        img_path = result_image_path(current)
        if img_path:
            st.image(str(img_path), use_container_width=True)
        else:
            st.info(ui["img_missing"])
    else:
        st.info(ui["note"])
