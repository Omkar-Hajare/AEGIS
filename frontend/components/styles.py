import streamlit as st


def is_dark_mode() -> bool:
    """Return True if Dark Mode is active, False for Light (White) mode."""
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = True
    return bool(st.session_state["dark_mode"])


def get_theme_colors() -> dict:
    """Return semantic color palette based on current theme."""
    dark = is_dark_mode()
    if dark:
        return {
            "is_dark": True,
            "bg": "#050505",
            "secondary_bg": "#0A0A0B",
            "card_bg": "rgba(255, 255, 255, 0.04)",
            "card_bg_hover": "rgba(255, 255, 255, 0.07)",
            "card_surface": "rgba(255, 255, 255, 0.04)",
            "card_bg_elevated": "rgba(255, 255, 255, 0.06)",
            "card_border": "rgba(255, 255, 255, 0.10)",
            "card_border_glow": "rgba(255, 255, 255, 0.16)",
            "text": "#F5F5F5",
            "text_muted": "#A1A1AA",
            "text_subtle": "#71717A",
            "sidebar_bg": "#0A0A0B",
            "sidebar_border": "rgba(255, 255, 255, 0.10)",
            "terminal_bg": "#0A0A0B",
            "terminal_border": "rgba(255, 255, 255, 0.10)",
            # Semantic Colors (Restrained & Meaningful)
            "green": "#22C55E",
            "emerald": "#22C55E",
            "red": "#EF4444",
            "rose": "#EF4444",
            "amber": "#F59E0B",
            "purple": "#A78BFA",
            "blue": "#60A5FA",
            "cyan": "#60A5FA",
            "neutral": "#F5F5F5",
            # Charts
            "chart_paper_bg": "rgba(0, 0, 0, 0)",
            "chart_plot_bg": "rgba(0, 0, 0, 0)",
            "chart_font": "#F5F5F5",
            "chart_grid": "rgba(255, 255, 255, 0.06)",
            "chart_zeroline": "rgba(255, 255, 255, 0.12)",
            "tooltip_bg": "#0A0A0B",
            "tooltip_border": "rgba(255, 255, 255, 0.16)",
            "tooltip_font": "#F5F5F5",
        }
    else:
        return {
            "is_dark": False,
            "bg": "#F4F4F5",
            "secondary_bg": "#EDEDEF",
            "card_bg": "rgba(255, 255, 255, 0.70)",
            "card_bg_hover": "rgba(255, 255, 255, 0.85)",
            "card_surface": "#EDEDEF",
            "card_bg_elevated": "#FFFFFF",
            "card_border": "rgba(0, 0, 0, 0.08)",
            "card_border_glow": "rgba(0, 0, 0, 0.14)",
            "text": "#18181B",
            "text_muted": "#52525B",
            "text_subtle": "#71717A",
            "sidebar_bg": "#EDEDEF",
            "sidebar_border": "rgba(0, 0, 0, 0.08)",
            "terminal_bg": "#18181B",
            "terminal_border": "rgba(0, 0, 0, 0.12)",
            # Semantic Colors
            "green": "#16A34A",
            "emerald": "#16A34A",
            "red": "#DC2626",
            "rose": "#DC2626",
            "amber": "#D97706",
            "purple": "#7C3AED",
            "blue": "#2563EB",
            "cyan": "#2563EB",
            "neutral": "#18181B",
            # Charts
            "chart_paper_bg": "rgba(0, 0, 0, 0)",
            "chart_plot_bg": "rgba(0, 0, 0, 0)",
            "chart_font": "#18181B",
            "chart_grid": "rgba(0, 0, 0, 0.06)",
            "chart_zeroline": "rgba(0, 0, 0, 0.12)",
            "tooltip_bg": "#FFFFFF",
            "tooltip_border": "rgba(0, 0, 0, 0.12)",
            "tooltip_font": "#18181B",
        }


@st.cache_data(ttl=5)
def get_backend_status() -> dict:
    """Check backend health via centralized ApiClient."""
    from frontend.services.api_client import check_health

    health = check_health()
    if health.get("is_live"):
        return {
            "is_live": True,
            "status": "ONLINE",
            "label": f"BACKEND: HEALTHY (API v{health.get('version', '0.1.0')})",
            "badge_class": "badge-protected",
            "details": "FastAPI + Redis Tier-1",
        }
    return {
        "is_live": False,
        "status": "DEMO MODE",
        "label": "BACKEND: DEMO MODE (LOCAL TELEMETRY)",
        "badge_class": "badge-hot",
        "details": "High-Fidelity Synthetic Trace",
    }


def apply_global_styles():
    """Inject responsive, polished CSS for Cyber Obsidian Dark and Clean Off-White Light modes."""
    c = get_theme_colors()
    dark = c["is_dark"]

    if dark:
        body_bg_color = "#050505"
        body_gradient = (
            "radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.015) 0%, transparent 45%), "
            "radial-gradient(circle at 82% 82%, rgba(167, 139, 250, 0.02) 0%, transparent 50%), "
            "radial-gradient(circle at 50% 50%, rgba(34, 197, 94, 0.01) 0%, transparent 60%)"
        )
        card_bg_hover = "rgba(255, 255, 255, 0.07)"
        card_border_hover = "rgba(255, 255, 255, 0.16)"
        card_shadow = "0 8px 32px rgba(0, 0, 0, 0.25)"
        card_shadow_hover = "0 12px 40px rgba(0, 0, 0, 0.35)"
        hr_color = "rgba(255, 255, 255, 0.08)"
        dock_bg = "rgba(10, 10, 10, 0.72)"
        navbar_bg = "rgba(10, 10, 10, 0.72)"
        navbar_border = "rgba(255, 255, 255, 0.10)"
        seg_bg = "rgba(255, 255, 255, 0.03)"
        seg_border = "rgba(255, 255, 255, 0.08)"
        seg_hover_bg = "rgba(255, 255, 255, 0.05)"
        seg_active_bg = "rgba(255, 255, 255, 0.08)"
        seg_active_border = "rgba(255, 255, 255, 0.14)"
        seg_active_shadow = "0 2px 8px rgba(0, 0, 0, 0.2)"
        seg_active_color = "#F5F5F5"
        seg_inactive_color = "#A1A1AA"
        blob_purple = "rgba(124, 58, 237, 0.13)"   # #7C3AED with 0.13 opacity
        blob_magenta = "rgba(219, 39, 119, 0.10)"  # #DB2777 with 0.10 opacity
        blob_blue = "rgba(37, 99, 235, 0.11)"      # #2563EB with 0.11 opacity
        blob_orange = "rgba(249, 115, 22, 0.08)"   # #F97316 with 0.08 opacity
    else:
        body_bg_color = "#F4F4F5"
        body_gradient = (
            "radial-gradient(circle at 20% 20%, rgba(0, 0, 0, 0.015) 0%, transparent 40%), "
            "radial-gradient(circle at 80% 80%, rgba(0, 0, 0, 0.01) 0%, transparent 40%)"
        )
        card_bg_hover = "rgba(255, 255, 255, 0.85)"
        card_border_hover = "rgba(0, 0, 0, 0.14)"
        card_shadow = "0 4px 20px rgba(0, 0, 0, 0.04)"
        card_shadow_hover = "0 8px 28px rgba(0, 0, 0, 0.08)"
        hr_color = "rgba(0, 0, 0, 0.08)"
        dock_bg = "rgba(244, 244, 245, 0.85)"
        navbar_bg = "rgba(244, 244, 245, 0.85)"
        navbar_border = "rgba(0, 0, 0, 0.08)"
        seg_bg = "rgba(0, 0, 0, 0.03)"
        seg_border = "rgba(0, 0, 0, 0.06)"
        seg_hover_bg = "rgba(0, 0, 0, 0.04)"
        seg_active_bg = "#FFFFFF"
        seg_active_border = "rgba(0, 0, 0, 0.12)"
        seg_active_shadow = "0 2px 6px rgba(0, 0, 0, 0.06)"
        seg_active_color = "#18181B"
        seg_inactive_color = "#52525B"
        blob_purple = "rgba(124, 58, 237, 0.04)"   # Ultra-subtle frosted light mode
        blob_magenta = "rgba(219, 39, 119, 0.03)"  # Ultra-subtle frosted light mode
        blob_blue = "rgba(37, 99, 235, 0.035)"     # Ultra-subtle frosted light mode
        blob_orange = "rgba(249, 115, 22, 0.025)"  # Ultra-subtle frosted light mode

    css = f"""
    <style>
        /* Ambient subtle shift */
        @keyframes ambientShift {{
            0%, 100% {{ background-position: 0% 50%, 100% 0%, 50% 50%; }}
            50% {{ background-position: 100% 50%, 0% 100%, 50% 50%; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            .stApp {{ animation: none !important; }}
        }}

        /* Base App Canvas */
        .stApp {{
            background-color: {body_bg_color} !important;
            background-image: {body_gradient} !important;
            background-size: 140% 140%, 140% 140%, 140% 140% !important;
            animation: ambientShift 35s ease-in-out infinite alternate !important;
            color: {c["text"]} !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* Ambient Abstract Liquid Gradient Blob Layer */
        .ambient-gradient-backdrop {{
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            overflow: hidden !important;
            pointer-events: none !important;
            z-index: 0 !important;
        }}

        div[data-testid="element-container"]:has(.ambient-gradient-backdrop),
        div[data-testid="stMarkdown"]:has(.ambient-gradient-backdrop),
        div[data-testid="stMarkdownContainer"]:has(.ambient-gradient-backdrop) {{
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: visible !important;
            pointer-events: none !important;
            line-height: 0 !important;
        }}

        .gradient-blob {{
            position: absolute !important;
            border-radius: 50% !important;
            pointer-events: none !important;
            will-change: transform !important;
            transform: translate3d(0, 0, 0) !important;
        }}

        /* Blob 1: Upper-left Purple (#7C3AED) */
        .blob-purple {{
            top: -140px !important;
            left: -100px !important;
            width: 680px !important;
            height: 620px !important;
            background: radial-gradient(circle, {blob_purple} 0%, rgba(124, 58, 237, 0) 70%) !important;
            border-radius: 52% 48% 64% 36% / 44% 56% 44% 56% !important;
            filter: blur(95px) !important;
            -webkit-filter: blur(95px) !important;
            animation: blobDrift1 26s ease-in-out infinite alternate !important;
        }}

        /* Blob 2: Upper-right Magenta (#DB2777) */
        .blob-magenta {{
            top: -80px !important;
            right: -120px !important;
            width: 640px !important;
            height: 590px !important;
            background: radial-gradient(circle, {blob_magenta} 0%, rgba(219, 39, 119, 0) 70%) !important;
            border-radius: 44% 56% 40% 60% / 58% 42% 58% 42% !important;
            filter: blur(105px) !important;
            -webkit-filter: blur(105px) !important;
            animation: blobDrift2 30s ease-in-out infinite alternate !important;
        }}

        /* Blob 3: Middle-lower Blue (#2563EB) */
        .blob-blue {{
            bottom: 12% !important;
            left: -80px !important;
            width: 660px !important;
            height: 620px !important;
            background: radial-gradient(circle, {blob_blue} 0%, rgba(37, 99, 235, 0) 70%) !important;
            border-radius: 58% 42% 46% 54% / 48% 52% 48% 52% !important;
            filter: blur(110px) !important;
            -webkit-filter: blur(110px) !important;
            animation: blobDrift3 28s ease-in-out infinite alternate !important;
        }}

        /* Blob 4: Lower-right Orange (#F97316) */
        .blob-orange {{
            bottom: -100px !important;
            right: -80px !important;
            width: 600px !important;
            height: 560px !important;
            background: radial-gradient(circle, {blob_orange} 0%, rgba(249, 115, 22, 0) 70%) !important;
            border-radius: 46% 54% 56% 44% / 52% 48% 52% 48% !important;
            filter: blur(95px) !important;
            -webkit-filter: blur(95px) !important;
            animation: blobDrift4 24s ease-in-out infinite alternate !important;
        }}

        /* Extremely subtle, slow liquid drift animations (24s-30s cycle) */
        @keyframes blobDrift1 {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            50% {{ transform: translate(25px, -18px) scale(1.04); }}
        }}
        @keyframes blobDrift2 {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            50% {{ transform: translate(-22px, 20px) scale(0.96); }}
        }}
        @keyframes blobDrift3 {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            50% {{ transform: translate(18px, 22px) scale(1.03); }}
        }}
        @keyframes blobDrift4 {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            50% {{ transform: translate(-20px, -18px) scale(0.97); }}
        }}

        /* Accessibility & Reduced Motion */
        @media (prefers-reduced-motion: reduce) {{
            .blob-purple, .blob-magenta, .blob-blue, .blob-orange {{
                animation: none !important;
            }}
        }}

        /* Responsive Scaling for Laptops & Tablets */
        @media (max-width: 1280px) {{
            .blob-purple, .blob-magenta, .blob-blue, .blob-orange {{
                filter: blur(75px) !important;
                -webkit-filter: blur(75px) !important;
                opacity: 0.85 !important;
            }}
            .blob-purple {{ width: 500px !important; height: 460px !important; }}
            .blob-magenta {{ width: 480px !important; height: 440px !important; }}
            .blob-blue {{ width: 490px !important; height: 460px !important; }}
            .blob-orange {{ width: 450px !important; height: 420px !important; }}
        }}

        @media (max-width: 768px) {{
            .blob-purple, .blob-magenta, .blob-blue, .blob-orange {{
                filter: blur(60px) !important;
                -webkit-filter: blur(60px) !important;
                opacity: 0.7 !important;
            }}
            .blob-purple {{ width: 340px !important; height: 320px !important; }}
            .blob-magenta {{ width: 320px !important; height: 300px !important; }}
            .blob-blue {{ width: 330px !important; height: 310px !important; }}
            .blob-orange {{ width: 300px !important; height: 280px !important; }}
        }}

        /* Completely Hide Streamlit Header, Top Decoration, Sidebar & Collapse Triggers */
        header[data-testid="stHeader"],
        .stAppHeader,
        [data-testid="stHeader"],
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stDecoration"],
        div[data-testid="stToolbar"],
        button[kind="headerNoPadding"] {{
            display: none !important;
            height: 0px !important;
            min-height: 0px !important;
            max-height: 0px !important;
            padding: 0 !important;
            margin: 0 !important;
            opacity: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}

        /* Section wrapper zeroing */
        section[data-testid="stMain"],
        .stMain {{
            padding: 0 !important;
            margin: 0 !important;
        }}

        /* Single Consistent Full-Width Control-Center Container (1480px wide, centered, 40px breathing room) */
        .stMainBlockContainer,
        .block-container,
        [data-testid="stMainBlockContainer"],
        div[data-testid="stAppViewBlockContainer"] {{
            position: relative !important;
            z-index: 1 !important;
            width: 100% !important;
            max-width: 1480px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 10px !important;
            padding-bottom: 36px !important;
            padding-left: 40px !important;
            padding-right: 40px !important;
        }}

        @media (max-width: 1024px) {{
            .stMainBlockContainer,
            .block-container,
            [data-testid="stMainBlockContainer"],
            div[data-testid="stAppViewBlockContainer"] {{
                padding-left: 24px !important;
                padding-right: 24px !important;
            }}
        }}

        @media (max-width: 768px) {{
            .stMainBlockContainer,
            .block-container,
            [data-testid="stMainBlockContainer"],
            div[data-testid="stAppViewBlockContainer"] {{
                padding-left: 16px !important;
                padding-right: 16px !important;
            }}
        }}

        /* Consistent Column Row Gap (18px) and Column Equal Stretch */
        div[data-testid="stHorizontalBlock"] {{
            gap: 18px !important;
            margin-bottom: 18px !important;
        }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
            display: flex !important;
            flex-direction: column !important;
        }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div {{
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
        }}

        /* Seamless Top Navbar: Edge-to-edge container alignment with crisp border-bottom */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]),
        div[data-testid="stHorizontalBlock"]:has(button[data-variant="segmented_control"]) {{
            background: {navbar_bg} !important;
            border-bottom: 1px solid {navbar_border} !important;
            border-top: none !important;
            border-left: none !important;
            border-right: none !important;
            border-radius: 0px !important;
            backdrop-filter: blur(18px) !important;
            -webkit-backdrop-filter: blur(18px) !important;
            padding-top: 4px !important;
            padding-bottom: 12px !important;
            padding-left: 0px !important;
            padding-right: 0px !important;
            margin-top: 0 !important;
            margin-bottom: 16px !important;
            box-shadow: none !important;
            align-items: center !important;
            width: 100% !important;
        }}

        /* Top Navbar Segmented Control Customization */
        [data-testid="stButtonGroup"] {{
            display: flex !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
        }}
        [data-testid="stButtonGroup"] div[role="radiogroup"] {{
            background-color: {seg_bg} !important;
            background: {seg_bg} !important;
            border: 1px solid {seg_border} !important;
            border-radius: 10px !important;
            padding: 3px !important;
            gap: 4px !important;
            display: flex !important;
            width: 100% !important;
            justify-content: space-between !important;
        }}
        button[data-variant="segmented_control"],
        [data-testid="stButtonGroup"] button {{
            background-color: transparent !important;
            background: transparent !important;
            border-radius: 7px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            padding: 6px 14px !important;
            color: {seg_inactive_color} !important;
            border: 1px solid transparent !important;
            flex: 1 !important;
            text-align: center !important;
            transition: all 0.15s ease-in-out !important;
        }}
        .stApp button[data-variant="segmented_control"] *,
        .stApp [data-testid="stButtonGroup"] button *,
        .stApp button[data-variant="segmented_control"] p,
        .stApp button[data-variant="segmented_control"] span,
        .stApp button[data-variant="segmented_control"] div,
        .stApp [data-testid="stButtonGroup"] button p,
        .stApp [data-testid="stButtonGroup"] button span,
        .stApp [data-testid="stButtonGroup"] button div {{
            color: {seg_inactive_color} !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }}
        button[data-variant="segmented_control"]:hover,
        [data-testid="stButtonGroup"] button:hover {{
            background-color: {seg_hover_bg} !important;
            background: {seg_hover_bg} !important;
        }}
        .stApp button[data-variant="segmented_control"]:hover *,
        .stApp [data-testid="stButtonGroup"] button:hover *,
        .stApp button[data-variant="segmented_control"]:hover p,
        .stApp [data-testid="stButtonGroup"] button:hover p {{
            color: {c["text"]} !important;
        }}
        button[data-variant="segmented_control"][data-selected="true"],
        button[data-variant="segmented_control"][data-selected],
        button[data-variant="segmented_control"][aria-checked="true"],
        [data-testid="stButtonGroup"] button[data-selected="true"],
        [data-testid="stButtonGroup"] button[data-selected],
        [data-testid="stButtonGroup"] button[aria-checked="true"] {{
            background-color: {seg_active_bg} !important;
            background: {seg_active_bg} !important;
            border: 1px solid {seg_active_border} !important;
            box-shadow: {seg_active_shadow} !important;
            color: {seg_active_color} !important;
        }}
        .stApp button[data-variant="segmented_control"][data-selected="true"] *,
        .stApp button[data-variant="segmented_control"][data-selected] *,
        .stApp button[data-variant="segmented_control"][aria-checked="true"] *,
        .stApp [data-testid="stButtonGroup"] button[data-selected="true"] *,
        .stApp [data-testid="stButtonGroup"] button[data-selected] *,
        .stApp [data-testid="stButtonGroup"] button[aria-checked="true"] *,
        .stApp button[data-variant="segmented_control"][data-selected="true"] p,
        .stApp [data-testid="stButtonGroup"] button[data-selected="true"] p,
        .stApp [data-testid="stButtonGroup"] button[aria-checked="true"] p {{
            color: {seg_active_color} !important;
            font-weight: 700 !important;
        }}

        /* Action buttons inside Navbar */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button {{
            border-radius: 8px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            min-height: 34px !important;
            padding: 4px 10px !important;
            background: {"rgba(255, 255, 255, 0.05)" if dark else "#FFFFFF"} !important;
            background-color: {"rgba(255, 255, 255, 0.05)" if dark else "#FFFFFF"} !important;
            color: {c["text"]} !important;
            border: 1px solid {"rgba(255, 255, 255, 0.10)" if dark else "rgba(0, 0, 0, 0.12)"} !important;
            box-shadow: {"none" if dark else "0 1px 3px rgba(0, 0, 0, 0.04)"} !important;
            transition: all 0.18s ease !important;
        }}
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button *,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button *,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button p,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button p {{
            color: {c["text"]} !important;
        }}
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button:hover,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button:hover {{
            background: {"rgba(255, 255, 255, 0.09)" if dark else "#F4F4F5"} !important;
            border-color: {card_border_hover} !important;
            color: {"#FFFFFF" if dark else "#000000"} !important;
            box-shadow: none !important;
        }}
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button:hover *,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button:hover *,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button:hover p,
        .stApp div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button:hover p {{
            color: {"#FFFFFF" if dark else "#000000"} !important;
        }}

        /* Force theme text colors across standard markdown and Streamlit elements (excluding button interiors) */
        .stApp,
        .stApp p:not(button p):not(button *),
        .stApp label:not(button label):not(button *),
        .stApp div[data-testid="stMarkdownContainer"]:not(button *):not(button) p {{
            color: {c["text"]} !important;
        }}

        /* Toggle switch labels */
        [data-testid="stToggle"] label p,
        [data-testid="stToggle"] p,
        [data-testid="stToggle"] span {{
            color: {c["text"]} !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }}

        /* Typography & Hierarchy */
        h1, h2, h3, h4, h5, h6 {{
            color: {c["text"]} !important;
            font-weight: 700 !important;
            letter-spacing: -0.3px;
        }}

        p, span, label, div {{
            color: inherit;
        }}

        .text-muted, .muted {{
            color: {c["text_muted"]} !important;
        }}

        /* Form elements and controls */
        [data-testid="stWidgetLabel"] label,
        [data-testid="stWidgetLabel"] p {{
            color: {c["text"]} !important;
            font-weight: 600 !important;
        }}
        [data-testid="stSelectbox"] div[role="group"],
        [data-testid="stSelectbox"] .react-aria-ComboBox div[role="group"],
        [data-testid="stSelectbox"] div[data-rac=""][role="group"],
        div[data-baseweb="select"] > div {{
            background-color: {c["card_bg"]} !important;
            background: {c["card_bg"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        [data-testid="stSelectbox"] input,
        [data-testid="stSelectbox"] input[role="combobox"],
        div[data-baseweb="select"] span {{
            background-color: transparent !important;
            background: transparent !important;
            color: {c["text"]} !important;
            font-weight: 500 !important;
        }}
        [data-testid="stSelectbox"] button,
        [data-testid="stSelectbox"] button[data-rac=""] {{
            background-color: transparent !important;
            background: transparent !important;
            color: {c["text_muted"]} !important;
            border: none !important;
        }}
        [data-testid="stSelectbox"] svg {{
            fill: {c["text_muted"]} !important;
        }}
        div[data-baseweb="popover"], div[data-baseweb="menu"], [role="listbox"] {{
            background-color: {"#0A0A0B" if dark else "#FFFFFF"} !important;
            background: {"#0A0A0B" if dark else "#FFFFFF"} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        li[role="option"], [role="option"] {{
            background-color: {"#0A0A0B" if dark else "#FFFFFF"} !important;
            background: {"#0A0A0B" if dark else "#FFFFFF"} !important;
            color: {c["text"]} !important;
        }}
        li[role="option"]:hover, [role="option"]:hover {{
            background-color: {"rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.05)"} !important;
            color: {"#FFFFFF" if dark else "#000000"} !important;
        }}

        [data-testid="stTextInput"] input {{
            background-color: {c["card_bg"]} !important;
            background: {c["card_bg"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        [data-testid="stTextInput"] input::placeholder {{
            color: {c["text_subtle"]} !important;
        }}

        /* Sliders */
        [data-testid="stSlider"] div[data-testid="stThumbValue"] {{
            color: {c["text"]} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stSlider"] div[data-testid="stTickBar"] div {{
            color: {c["text_muted"]} !important;
        }}
        [data-testid="stSlider"] [role="slider"] {{
            background-color: {c["text"]} !important;
            border-color: {c["text"]} !important;
            box-shadow: 0 0 6px rgba(255, 255, 255, 0.2) !important;
        }}
        [data-testid="stSlider"] div[data-baseweb="slider"] div div:first-child {{
            background-color: {c["emerald"]} !important;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            color: {c["text_muted"]} !important;
            font-weight: 600 !important;
            padding: 8px 18px !important;
            font-size: 13.5px !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {c["text"]} !important;
            border-bottom-color: {c["text"]} !important;
            font-weight: 700 !important;
        }}

        /* Pulse Dot Keyframe */
        @keyframes pulseGlow {{
            0% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6); }}
            70% {{ box-shadow: 0 0 0 7px rgba(34, 197, 94, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
        }}

        .pulse-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: #22C55E;
            border-radius: 50%;
            margin-right: 7px;
            animation: pulseGlow 2.5s infinite;
        }}

        /* Top Control Ribbon / Glass Dock */
        .control-ribbon {{
            background: {dock_bg};
            border: 1px solid {c["card_border"]};
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border-radius: 12px;
            padding: 9px 18px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: {card_shadow};
        }}

        /* Modern Elevated Cards (Glassmorphism + GPU-Friendly Transitions) */
        /* Modern Elevated Cards (Glassmorphism + GPU-Friendly Transitions) */
        .hero-card, .status-card, .decision-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 22px 24px !important;
            margin-bottom: 20px !important;
            box-shadow: {card_shadow} !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease !important;
        }}

        .metric-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 20px 22px !important;
            min-height: 148px !important;
            height: 100% !important;
            box-sizing: border-box !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            box-shadow: {card_shadow} !important;
            margin-bottom: 0 !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease !important;
        }}

        .hero-card:hover, .status-card:hover, .decision-card:hover, .metric-card:hover {{
            background: {card_bg_hover} !important;
            border-color: {card_border_hover} !important;
            transform: translateY(-2px);
            box-shadow: {card_shadow_hover} !important;
        }}

        /* Streamlit Plotly Chart Glassmorphic Wrapper */
        div[data-testid="stPlotlyChart"] {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 18px 20px 10px 20px !important;
            box-shadow: {card_shadow} !important;
            margin-bottom: 20px !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease !important;
        }}
        div[data-testid="stPlotlyChart"]:hover {{
            border-color: {card_border_hover} !important;
        }}

        /* Streamlit Native Alert / Info Box High Contrast Glass */
        div[data-testid="stAlert"] {{
            background: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 10px !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            padding: 14px 18px !important;
            margin-bottom: 18px !important;
        }}
        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] span,
        div[data-testid="stAlert"] div {{
            color: {c["text"]} !important;
            font-size: 13px !important;
            line-height: 1.5 !important;
        }}
        div[data-testid="stAlert"] a {{
            color: {c["purple"]} !important;
            font-weight: 600 !important;
        }}

        /* Streamlit Native Expander Glass */
        [data-testid="stExpander"] {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 10px !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            margin-bottom: 18px !important;
        }}
        [data-testid="stExpander"] summary {{
            padding: 12px 16px !important;
        }}
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span {{
            color: {c["text"]} !important;
            font-weight: 600 !important;
            font-size: 13.5px !important;
        }}
        [data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{
            padding: 14px 18px 18px 18px !important;
            border-top: 1px solid {c["card_border"]} !important;
        }}

        @media (max-width: 768px) {{
            .hero-card, .status-card, .decision-card, .metric-card {{
                padding: 16px 18px !important;
            }}
            div[data-testid="stPlotlyChart"] {{
                padding: 12px 14px 8px 14px !important;
            }}
        }}

        /* Streamlit Native Metric cards */
        [data-testid="stMetric"] {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 20px 22px !important;
            min-height: 148px !important;
            box-shadow: {card_shadow} !important;
        }}

        [data-testid="stMetricLabel"] {{
            color: {c["text_muted"]} !important;
            font-size: 0.8rem !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }}

        [data-testid="stMetricValue"] {{
            color: {c["text"]} !important;
            font-size: 1.8rem !important;
            font-weight: 800 !important;
        }}

        /* Terminal Console Box */
        .terminal-box {{
            background-color: {"#0A0A0B" if dark else "#18181B"} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 10px;
            padding: 16px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 12px;
            color: #F5F5F5 !important;
            line-height: 1.7;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        }}
        .terminal-box span, .terminal-box div {{
            color: #A1A1AA;
        }}
        .terminal-box code {{
            background: rgba(255, 255, 255, 0.08) !important;
            color: #F5F5F5 !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
        }}

        /* Buttons (Monochrome Glass System) */
        .stButton button,
        button[data-testid="stBaseButton-secondary"],
        span[data-testid="stTooltipHoverTarget"] button {{
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            min-height: 38px !important;
            background-color: {"rgba(255, 255, 255, 0.05)" if dark else "#FFFFFF"} !important;
            background: {"rgba(255, 255, 255, 0.05)" if dark else "#FFFFFF"} !important;
            color: {c["text"]} !important;
            border: 1px solid {"rgba(255, 255, 255, 0.10)" if dark else "rgba(0, 0, 0, 0.12)"} !important;
            box-shadow: {"none" if dark else "0 1px 4px rgba(0, 0, 0, 0.05)"} !important;
            transition: all 0.18s ease !important;
        }}
        .stApp .stButton button *,
        .stApp button[data-testid="stBaseButton-secondary"] *,
        .stApp span[data-testid="stTooltipHoverTarget"] button *,
        .stApp .stButton button:not([kind="primary"]) p,
        .stApp button[data-testid="stBaseButton-secondary"] p {{
            color: {c["text"]} !important;
        }}
        .stButton button:hover,
        button[data-testid="stBaseButton-secondary"]:hover,
        span[data-testid="stTooltipHoverTarget"] button:hover {{
            background-color: {"rgba(255, 255, 255, 0.09)" if dark else "#F4F4F5"} !important;
            background: {"rgba(255, 255, 255, 0.09)" if dark else "#F4F4F5"} !important;
            border-color: {"rgba(255, 255, 255, 0.20)" if dark else "rgba(0, 0, 0, 0.24)"} !important;
            color: {"#FFFFFF" if dark else "#000000"} !important;
            box-shadow: {"0 4px 14px rgba(0, 0, 0, 0.2)" if dark else "0 3px 10px rgba(0, 0, 0, 0.08)"} !important;
        }}
        .stApp .stButton button:hover *,
        .stApp button[data-testid="stBaseButton-secondary"]:hover *,
        .stApp span[data-testid="stTooltipHoverTarget"] button:hover *,
        .stApp .stButton button:not([kind="primary"]):hover p,
        .stApp button[data-testid="stBaseButton-secondary"]:hover p {{
            color: {"#FFFFFF" if dark else "#000000"} !important;
        }}

        /* Primary Buttons - High Contrast Monochrome Accent in Both Modes */
        .stButton button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {{
            background-color: {"rgba(255, 255, 255, 0.14)" if dark else "#18181B"} !important;
            background: {"rgba(255, 255, 255, 0.14)" if dark else "#18181B"} !important;
            color: #FFFFFF !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            min-height: 38px !important;
            border-radius: 8px !important;
            border: 1px solid {"rgba(255, 255, 255, 0.22)" if dark else "#18181B"} !important;
            box-shadow: {"0 2px 10px rgba(0, 0, 0, 0.35)" if dark else "0 2px 8px rgba(0, 0, 0, 0.15)"} !important;
            transition: all 0.18s ease !important;
        }}
        .stApp .stButton button[kind="primary"] *,
        .stApp button[data-testid="stBaseButton-primary"] *,
        .stApp .stButton button[kind="primary"] p,
        .stApp button[data-testid="stBaseButton-primary"] p,
        .stApp .stButton button[kind="primary"] div[data-testid="stMarkdownContainer"] p,
        .stApp button[data-testid="stBaseButton-primary"] div[data-testid="stMarkdownContainer"] p {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }}
        .stButton button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {{
            background-color: {"rgba(255, 255, 255, 0.22)" if dark else "#27272A"} !important;
            background: {"rgba(255, 255, 255, 0.22)" if dark else "#27272A"} !important;
            border-color: {"rgba(255, 255, 255, 0.35)" if dark else "#27272A"} !important;
            color: #FFFFFF !important;
            box-shadow: {"0 4px 16px rgba(255, 255, 255, 0.12)" if dark else "0 4px 14px rgba(0, 0, 0, 0.25)"} !important;
        }}
        .stApp .stButton button[kind="primary"]:hover *,
        .stApp button[data-testid="stBaseButton-primary"]:hover *,
        .stApp .stButton button[kind="primary"]:hover p,
        .stApp button[data-testid="stBaseButton-primary"]:hover p,
        .stApp .stButton button[kind="primary"]:hover div[data-testid="stMarkdownContainer"] p,
        .stApp button[data-testid="stBaseButton-primary"]:hover div[data-testid="stMarkdownContainer"] p {{
            color: #FFFFFF !important;
        }}

        /* Dividers */
        hr {{
            border-color: {hr_color} !important;
            margin: 1.2rem 0 !important;
        }}

        /* Dataframe table styling */
        [data-testid="stDataFrame"] {{
            border: 1px solid {c["card_border"]} !important;
            border-radius: 12px !important;
            overflow: hidden !important;
            background-color: {c["card_bg"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            box-shadow: {card_shadow} !important;
            margin-bottom: 20px !important;
        }}
        [data-testid="stDataFrame"] div,
        [data-testid="stDataFrame"] span {{
            color: {c["text"]} !important;
        }}

        /* Clean Technical Glass Badges */
        .badge-pill {{
            display: inline-flex;
            align-items: center;
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }}
        .badge-protected {{
            background: rgba(34, 197, 94, 0.10);
            color: #22C55E;
            border: 1px solid rgba(34, 197, 94, 0.22);
        }}
        .badge-hot {{
            background: rgba(245, 158, 11, 0.10);
            color: {"#F59E0B" if dark else "#D97706"};
            border: 1px solid rgba(245, 158, 11, 0.22);
        }}
        .badge-risk {{
            background: rgba(239, 68, 68, 0.10);
            color: {"#EF4444" if dark else "#DC2626"};
            border: 1px solid rgba(239, 68, 68, 0.22);
        }}
        .badge-active {{
            background: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"};
            color: {c["text_muted"]};
            border: 1px solid {c["card_border"]};
        }}
        .badge-purple {{
            background: rgba(167, 139, 250, 0.10);
            color: {"#A78BFA" if dark else "#7C3AED"};
            border: 1px solid rgba(167, 139, 250, 0.22);
        }}

        /* Responsive Pipeline Flow Grid */
        .pipeline-node {{
            background: {c["card_surface"]};
            border: 1px solid {c["card_border"]};
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border-radius: 10px;
            padding: 14px 16px;
            text-align: center;
            position: relative;
            transition: all 0.2s ease;
        }}
        .pipeline-node:hover {{
            border-color: {card_border_hover};
            transform: translateY(-2px);
        }}

    </style>
    """
    blob_html = """
    <div class="ambient-gradient-backdrop" aria-hidden="true">
        <div class="gradient-blob blob-purple"></div>
        <div class="gradient-blob blob-magenta"></div>
        <div class="gradient-blob blob-blue"></div>
        <div class="gradient-blob blob-orange"></div>
    </div>
    """
    full_output = f"{blob_html}\n{css}"
    st.markdown(full_output, unsafe_allow_html=True)

