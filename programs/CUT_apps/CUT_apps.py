def render_tracked_link_button(
    button_text: str,
    url: str,
    event_name: str,
    key_suffix: str,
    new_tab: bool = True,
    use_container_width: bool = True,
    **params,
):
    if not url:
        return

    payload_json = json.dumps(params).replace("&", "&amp;").replace("'", "&#39;")
    safe_url = url.replace("&", "&amp;").replace('"', "&quot;")
    safe_label = button_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    target = "_blank" if new_tab else "_self"
    rel = "noopener noreferrer" if new_tab else ""

    width_style = "width: 100%;" if use_container_width else "width: auto;"

    button_html = f"""
    <a
        href="{safe_url}"
        target="{target}"
        rel="{rel}"
        onclick='(function() {{ var p = {payload_json}; if (typeof window.gtag !== "undefined") {{ window.gtag("event", "{event_name}", p); }} }})()'
        style="
            {width_style}
            background-color: #ff4b4b;
            color: #ffffff;
            text-decoration: none;
            padding: 0.55rem 0.75rem;
            border-radius: 0.5rem;
            text-align: center;
            font-weight: 600;
            line-height: 1.6;
            border: 1px solid #ff4b4b;
            box-sizing: border-box;
            display: inline-block;
            cursor: pointer;
            margin: 0.2rem 0 0.55rem 0;
        "
    >{safe_label}</a>
    """

    st.markdown(button_html, unsafe_allow_html=True)
