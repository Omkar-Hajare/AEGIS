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
            "bg": "#060913",
            "card_bg": "#0B1120",
            "card_surface": "#0E1726",
            "card_bg_elevated": "#0E1726",
            "card_border": "rgba(56, 189, 248, 0.12)",
            "card_border_glow": "rgba(56, 189, 248, 0.35)",
            "text": "#F8FAFC",
            "text_muted": "#94A3B8",
            "text_subtle": "#64748B",
            "sidebar_bg": "#080D1A",
            "sidebar_border": "rgba(255, 255, 255, 0.08)",
            "terminal_bg": "#050811",
            "terminal_border": "#1E293B",
            # Accents
            "cyan": "#38BDF8",
            "emerald": "#10B981",
            "amber": "#F59E0B",
            "purple": "#A855F7",
            "rose": "#F43F5E",
            # Charts
            "chart_paper_bg": "rgba(0,0,0,0)",
            "chart_plot_bg": "rgba(0,0,0,0)",
            "chart_font": "#E2E8F0",
            "chart_grid": "rgba(255, 255, 255, 0.06)",
            "chart_zeroline": "rgba(255, 255, 255, 0.15)",
            "tooltip_bg": "#0F172A",
            "tooltip_border": "#38BDF8",
            "tooltip_font": "#F8FAFC",
        }
    else:
        return {
            "is_dark": False,
            "bg": "#F4F6F9",
            "card_bg": "#FFFFFF",
            "card_surface": "#F8FAFC",
            "card_bg_elevated": "#F8FAFC",
            "card_border": "#E2E8F0",
            "card_border_glow": "rgba(2, 132, 199, 0.4)",
            "text": "#0F172A",
            "text_muted": "#334155",
            "text_subtle": "#475569",
            "sidebar_bg": "#EAEEF4",
            "sidebar_border": "#CBD5E1",
            "terminal_bg": "#0B0F19",
            "terminal_border": "#1E293B",
            # Accents
            "cyan": "#0284C7",
            "emerald": "#059669",
            "amber": "#B45309",
            "purple": "#7C3AED",
            "rose": "#DC2626",
            # Charts
            "chart_paper_bg": "rgba(0,0,0,0)",
            "chart_plot_bg": "rgba(0,0,0,0)",
            "chart_font": "#0F172A",
            "chart_grid": "rgba(15, 23, 42, 0.08)",
            "chart_zeroline": "rgba(15, 23, 42, 0.20)",
            "tooltip_bg": "#FFFFFF",
            "tooltip_border": "#0284C7",
            "tooltip_font": "#0F172A",
        }


@st.cache_data(ttl=20)
def get_backend_status() -> dict:
    """Check if real FastAPI backend is reachable on localhost:8000; gracefully report demo mode otherwise."""
    try:
        import requests

        resp = requests.get("http://localhost:8000/health", timeout=0.25)
        if resp.status_code == 200:
            return {
                "is_live": True,
                "status": "ONLINE",
                "label": "BACKEND: HEALTHY (API v1.0)",
                "badge_class": "badge-protected",
                "details": "FastAPI + Redis Tier-1",
            }
    except Exception:
        pass
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
        body_bg_color = "#060913"
        body_gradient = (
            "radial-gradient(circle at 15% 20%, rgba(56, 189, 248, 0.08) 0%, transparent 45%), "
            "radial-gradient(circle at 85% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 45%), "
            "radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.03) 0%, transparent 50%)"
        )
        card_bg = "rgba(11, 17, 32, 0.78)"
        card_border = "rgba(148, 163, 184, 0.12)"
        card_shadow = "0 4px 20px rgba(0, 0, 0, 0.35)"
        card_shadow_hover = "0 10px 30px rgba(0, 0, 0, 0.55), 0 0 16px rgba(56, 189, 248, 0.14)"
        sidebar_bg = "#080D1A"
        sidebar_border = "rgba(255, 255, 255, 0.08)"
        hr_color = "#1E293B"
        dock_bg = "rgba(11, 17, 32, 0.85)"
        navbar_bg = "rgba(8, 13, 26, 0.88)"
        navbar_border = "rgba(56, 189, 248, 0.16)"
        seg_bg = "rgba(12, 19, 34, 0.85)"
        seg_border = "rgba(56, 189, 248, 0.16)"
        seg_hover_bg = "rgba(255, 255, 255, 0.07)"
        seg_active_bg = "rgba(56, 189, 248, 0.18)"
        seg_active_border = "rgba(56, 189, 248, 0.50)"
        seg_active_shadow = "0 0 12px rgba(56, 189, 248, 0.25)"
        seg_active_color = "#38BDF8"
        seg_inactive_color = "#94A3B8"
    else:
        body_bg_color = "#F4F6F9"
        body_gradient = (
            "radial-gradient(circle at 15% 20%, rgba(2, 132, 199, 0.04) 0%, transparent 40%), "
            "radial-gradient(circle at 85% 80%, rgba(124, 58, 237, 0.03) 0%, transparent 40%)"
        )
        card_bg = "rgba(255, 255, 255, 0.92)"
        card_border = "#E2E8F0"
        card_shadow = "0 4px 16px rgba(15, 23, 42, 0.05)"
        card_shadow_hover = "0 8px 24px rgba(15, 23, 42, 0.1), 0 0 12px rgba(2, 132, 199, 0.12)"
        sidebar_bg = "#EAEEF4"
        sidebar_border = "#CBD5E1"
        hr_color = "#E2E8F0"
        dock_bg = "rgba(255, 255, 255, 0.94)"
        navbar_bg = "rgba(255, 255, 255, 0.94)"
        navbar_border = "#E2E8F0"
        seg_bg = "#E8EDF4"
        seg_border = "#CBD5E1"
        seg_hover_bg = "rgba(255, 255, 255, 0.6)"
        seg_active_bg = "#FFFFFF"
        seg_active_border = "rgba(2, 132, 199, 0.45)"
        seg_active_shadow = "0 2px 8px rgba(15, 23, 42, 0.08), 0 0 10px rgba(2, 132, 199, 0.12)"
        seg_active_color = "#0284C7"
        seg_inactive_color = "#475569"

    sidebar_link_color = "#CBD5E1" if dark else "#1E293B"
    sidebar_hover_bg = (
        "rgba(56, 189, 248, 0.1)" if dark else "rgba(2, 132, 199, 0.08)"
    )
    sidebar_active_bg = (
        "rgba(56, 189, 248, 0.18)" if dark else "rgba(2, 132, 199, 0.14)"
    )

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

        /* Single Consistent Full-Width Control-Center Container (1440px wide, centered) */
        .stMainBlockContainer,
        .block-container,
        [data-testid="stMainBlockContainer"],
        div[data-testid="stAppViewBlockContainer"] {{
            width: 100% !important;
            max-width: 1440px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 8px !important;
            padding-bottom: 32px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
        }}

        /* Consistent Column Row Gap (16px) */
        div[data-testid="stHorizontalBlock"] {{
            gap: 16px !important;
        }}

        /* Seamless Top Navbar: Edge-to-edge container alignment with crisp border-bottom */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]),
        div[data-testid="stHorizontalBlock"]:has(button[data-variant="segmented_control"]) {{
            background: transparent !important;
            border-bottom: 1px solid {navbar_border} !important;
            border-top: none !important;
            border-left: none !important;
            border-right: none !important;
            border-radius: 0px !important;
            padding-top: 2px !important;
            padding-bottom: 12px !important;
            padding-left: 0px !important;
            padding-right: 0px !important;
            margin-top: 0 !important;
            margin-bottom: 10px !important;
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
        button[data-variant="segmented_control"] *,
        [data-testid="stButtonGroup"] button *,
        button[data-variant="segmented_control"] p,
        button[data-variant="segmented_control"] span,
        button[data-variant="segmented_control"] div {{
            color: {seg_inactive_color} !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }}
        button[data-variant="segmented_control"]:hover,
        [data-testid="stButtonGroup"] button:hover {{
            background-color: {seg_hover_bg} !important;
            background: {seg_hover_bg} !important;
        }}
        button[data-variant="segmented_control"]:hover *,
        [data-testid="stButtonGroup"] button:hover * {{
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
        button[data-variant="segmented_control"][data-selected="true"] *,
        button[data-variant="segmented_control"][data-selected] *,
        button[data-variant="segmented_control"][aria-checked="true"] *,
        [data-testid="stButtonGroup"] button[data-selected="true"] *,
        [data-testid="stButtonGroup"] button[data-selected] *,
        [data-testid="stButtonGroup"] button[aria-checked="true"] * {{
            color: {seg_active_color} !important;
            font-weight: 700 !important;
        }}

        /* Action buttons inside Navbar */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button {{
            border-radius: 8px !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            min-height: 34px !important;
            padding: 4px 10px !important;
            background: {c["card_bg_elevated"]} !important;
            background-color: {c["card_bg_elevated"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            box-shadow: none !important;
        }}
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button:hover,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button:hover {{
            border-color: {c["cyan"]} !important;
            color: {c["cyan"]} !important;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.25) !important;
        }}

        /* Force theme text colors across standard markdown and Streamlit elements */
        .stApp, .stApp p, .stApp label, .stApp div[data-testid="stMarkdownContainer"] p {{
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
            background-color: {c["card_bg"]} !important;
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        li[role="option"], [role="option"] {{
            background-color: {c["card_bg"]} !important;
            background: {c["card_bg"]} !important;
            color: {c["text"]} !important;
        }}
        li[role="option"]:hover, [role="option"]:hover {{
            background-color: {"rgba(56, 189, 248, 0.15)" if dark else "rgba(2, 132, 199, 0.1)"} !important;
            color: {c["cyan"]} !important;
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
            background-color: {c["cyan"]} !important;
            border-color: {c["cyan"]} !important;
        }}
        [data-testid="stSlider"] div[data-baseweb="slider"] div div:first-child {{
            background-color: {c["cyan"]} !important;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            color: {c["text_muted"]} !important;
            font-weight: 600 !important;
            padding: 8px 18px !important;
            font-size: 13.5px !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {c["cyan"]} !important;
            border-bottom-color: {c["cyan"]} !important;
            font-weight: 700 !important;
        }}

        /* Pulse Dot Keyframe */
        @keyframes pulseGlow {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }}
            70% {{ box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        .pulse-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: #10B981;
            border-radius: 50%;
            margin-right: 7px;
            animation: pulseGlow 2.5s infinite;
        }}

        /* Top Control Ribbon / Glass Dock */
        .control-ribbon {{
            background: {dock_bg};
            border: 1px solid {c["card_border"]};
            border-radius: 12px;
            padding: 9px 18px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: {card_shadow};
        }}

        /* Modern Elevated Cards (GPU-Friendly Transitions) */
        .hero-card, .status-card, .decision-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: {card_shadow};
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease;
        }}

        .metric-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 12px !important;
            padding: 16px 18px !important;
            min-height: 130px !important;
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            box-shadow: {card_shadow} !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease !important;
        }}

        .hero-card:hover, .status-card:hover, .decision-card:hover, .metric-card:hover {{
            border-color: {c["card_border_glow"]} !important;
            transform: translateY(-2px);
            box-shadow: {card_shadow_hover};
        }}

        /* Streamlit Native Metric cards */
        [data-testid="stMetric"] {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 12px !important;
            padding: 16px 18px !important;
            box-shadow: {card_shadow};
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
            background-color: #060913 !important;
            border: 1px solid rgba(56, 189, 248, 0.22) !important;
            border-radius: 10px;
            padding: 16px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 12px;
            color: #38BDF8 !important;
            line-height: 1.7;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        }}
        .terminal-box span, .terminal-box div {{
            color: #94A3B8;
        }}
        .terminal-box code {{
            background: rgba(56, 189, 248, 0.12) !important;
            color: #38BDF8 !important;
            border: 1px solid rgba(56, 189, 248, 0.25) !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
        }}

        /* Buttons */
        .stButton button,
        button[data-testid="stBaseButton-secondary"],
        span[data-testid="stTooltipHoverTarget"] button {{
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 12.5px !important;
            min-height: 34px !important;
            background-color: {c["card_bg_elevated"]} !important;
            background: {c["card_bg_elevated"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            box-shadow: none !important;
            transition: all 0.2s ease !important;
        }}
        .stButton button:hover,
        button[data-testid="stBaseButton-secondary"]:hover,
        span[data-testid="stTooltipHoverTarget"] button:hover {{
            border-color: {c["cyan"]} !important;
            color: {c["cyan"]} !important;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.2) !important;
        }}
        .stButton button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {{
            background-color: {c["cyan"]} !important;
            background: {c["cyan"]} !important;
            color: #FFFFFF !important;
            font-weight: 700 !important;
            border-color: {c["cyan"]} !important;
        }}

        /* Dividers */
        hr {{
            border-color: {hr_color} !important;
            margin: 1.2rem 0 !important;
        }}

        /* Dataframe table styling */
        [data-testid="stDataFrame"] {{
            border: 1px solid {c["card_border"]} !important;
            border-radius: 10px !important;
            overflow: hidden;
            background-color: {c["card_bg"]} !important;
        }}

        /* Clean Technical Badges (No Emoji Clutter) */
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
            background: rgba(16, 185, 129, 0.15);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }}
        .badge-hot {{
            background: rgba(245, 158, 11, 0.15);
            color: {"#F59E0B" if dark else "#B45309"};
            border: 1px solid rgba(245, 158, 11, 0.35);
        }}
        .badge-risk {{
            background: rgba(244, 63, 94, 0.15);
            color: {"#F43F5E" if dark else "#DC2626"};
            border: 1px solid rgba(244, 63, 94, 0.35);
        }}
        .badge-active {{
            background: rgba(56, 189, 248, 0.15);
            color: {"#38BDF8" if dark else "#0284C7"};
            border: 1px solid rgba(56, 189, 248, 0.35);
        }}
        .badge-purple {{
            background: rgba(168, 85, 247, 0.15);
            color: {"#A855F7" if dark else "#7C3AED"};
            border: 1px solid rgba(168, 85, 247, 0.35);
        }}

        /* Responsive Pipeline Flow Grid */
        .pipeline-node {{
            background: {c["card_surface"]};
            border: 1px solid {c["card_border"]};
            border-radius: 10px;
            padding: 14px 16px;
            text-align: center;
            position: relative;
            transition: all 0.2s ease;
        }}
        .pipeline-node:hover {{
            border-color: {c["card_border_glow"]};
            transform: translateY(-2px);
        }}

    </style>
    """
    if hasattr(st, "html"):
        st.html(css)
    else:
        st.markdown(css, unsafe_allow_html=True)


def render_top_control_bar(active_page: str = "Overview"):
    """Render unified top observability ribbon with dynamic live/demo system connectivity badges."""
    c = get_theme_colors()
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    status_color = "#10B981" if is_live else c["amber"]
    status_text = "SYSTEM OPERATIONAL" if is_live else "DEMO MODE (LOCAL TELEMETRY)"
    pulse_dot_html = (
        '<span class="pulse-dot"></span>'
        if is_live
        else f'<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {c["amber"]}; margin-right: 6px;"></span>'
    )
    tier_label = "REDIS TIER-1" if is_live else "IN-MEMORY TELEMETRY"
    stream_badge = "● LIVE STREAMING" if is_live else "● SYNTHETIC TRACE"
    stream_color = c["cyan"] if is_live else c["amber"]
    stream_bg = (
        "rgba(56, 189, 248, 0.12)" if is_live else "rgba(245, 158, 11, 0.12)"
    )
    stream_border = (
        "rgba(56, 189, 248, 0.25)" if is_live else "rgba(245, 158, 11, 0.25)"
    )

    st.markdown(
        f"""
        <div class="control-ribbon">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 6px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3);">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{c["cyan"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                        </svg>
                    </div>
                    <span style="font-weight: 800; font-size: 13.5px; letter-spacing: -0.2px; color: {c["text"]};">
                        AdaptiveCache
                    </span>
                    <span style="color: {c["text_subtle"]}; font-size: 12px;">/</span>
                    <span style="color: {c["cyan"]}; font-size: 12.5px; font-weight: 600;">{active_page}</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="display: flex; align-items: center; font-size: 11.5px; font-weight: 700; color: {status_color};">
                    {pulse_dot_html}{status_text}
                </div>
                <div style="display: none; @media (min-width: 768px) {{ display: block; }}">
                    <span style="font-size: 11px; font-weight: 600; color: {c["text_muted"]}; background: rgba(255, 255, 255, 0.05); border: 1px solid {c["card_border"]}; padding: 3px 8px; border-radius: 5px;">
                        {tier_label}
                    </span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: {stream_color}; background: {stream_bg}; border: 1px solid {stream_border}; padding: 3px 9px; border-radius: 5px; letter-spacing: 0.5px;">
                        {stream_badge}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_branding(active_page: str = ""):
    """Render unified branding, engine tier status, and the Dark/White theme toggler."""
    c = get_theme_colors()
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    tier_status_color = "#10B981" if is_live else c["amber"]
    tier_status_text = "● ONLINE" if is_live else "○ DEMO MODE"
    tier_subtitle = "Redis + Telemetry Loop" if is_live else "Local High-Fidelity Trace"

    with st.sidebar:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 6px 0 14px 0;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 10px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); margin-bottom: 8px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{c["cyan"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <h2 style="margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -0.2px; color: {c["text"]} !important;">ADAPTIVE CACHE</h2>
                <p class="muted" style="font-size: 11px; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.8px; color: {c["text_muted"]} !important;">Control Center &bull; v2.6</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Engine Tier Status Badge
        st.markdown(
            f"""
            <div class="hero-card" style="padding: 10px 14px; margin-bottom: 16px; background: {c["card_bg"]} !important; border: 1px solid {c["card_border"]} !important;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: {c["text_muted"]};">
                        TIER 1 ARBITER
                    </span>
                    <span style="color: {tier_status_color}; font-size: 11px; font-weight: 700;">
                        {tier_status_text}
                    </span>
                </div>
                <div style="font-size: 13px; font-weight: 600; margin-top: 4px; color: {c["text"]};">
                    {tier_subtitle}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Theme Toggler (Dark vs White mode)
        is_dark = is_dark_mode()
        toggle_label = "Dark Mode" if is_dark else "Light Mode"

        new_val = st.toggle(
            toggle_label,
            value=is_dark,
            key=f"theme_toggle_{active_page or 'main'}",
            help="Toggle between Cyber Obsidian Dark Mode and Clean Light Mode",
        )

        if new_val != is_dark:
            st.session_state["dark_mode"] = new_val
            st.rerun()

        st.divider()