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
        body_bg_color = "#050505"
        body_gradient = (
            "radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.015) 0%, transparent 45%), "
            "radial-gradient(circle at 82% 82%, rgba(167, 139, 250, 0.02) 0%, transparent 50%), "
            "radial-gradient(circle at 50% 50%, rgba(34, 197, 94, 0.01) 0%, transparent 60%)"
        )
        card_bg = "rgba(255, 255, 255, 0.04)"
        card_bg_hover = "rgba(255, 255, 255, 0.07)"
        card_border = "rgba(255, 255, 255, 0.10)"
        card_border_hover = "rgba(255, 255, 255, 0.16)"
        card_shadow = "0 8px 32px rgba(0, 0, 0, 0.25)"
        card_shadow_hover = "0 12px 40px rgba(0, 0, 0, 0.35)"
        sidebar_bg = "#0A0A0B"
        sidebar_border = "rgba(255, 255, 255, 0.10)"
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
    else:
        body_bg_color = "#F4F4F5"
        body_gradient = (
            "radial-gradient(circle at 20% 20%, rgba(0, 0, 0, 0.015) 0%, transparent 40%), "
            "radial-gradient(circle at 80% 80%, rgba(0, 0, 0, 0.01) 0%, transparent 40%)"
        )
        card_bg = "rgba(255, 255, 255, 0.70)"
        card_bg_hover = "rgba(255, 255, 255, 0.85)"
        card_border = "rgba(0, 0, 0, 0.08)"
        card_border_hover = "rgba(0, 0, 0, 0.14)"
        card_shadow = "0 4px 20px rgba(0, 0, 0, 0.04)"
        card_shadow_hover = "0 8px 28px rgba(0, 0, 0, 0.08)"
        sidebar_bg = "#EDEDEF"
        sidebar_border = "rgba(0, 0, 0, 0.08)"
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

    sidebar_link_color = "#A1A1AA" if dark else "#52525B"
    sidebar_hover_bg = (
        "rgba(255, 255, 255, 0.06)" if dark else "rgba(0, 0, 0, 0.04)"
    )
    sidebar_active_bg = (
        "rgba(255, 255, 255, 0.10)" if dark else "rgba(0, 0, 0, 0.08)"
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
            margin-bottom: 12px !important;
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
            font-weight: 600 !important;
            min-height: 34px !important;
            padding: 4px 10px !important;
            background: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"} !important;
            background-color: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            box-shadow: none !important;
            transition: all 0.18s ease !important;
        }}
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) .stButton button:hover,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stButtonGroup"]) span[data-testid="stTooltipHoverTarget"] button:hover {{
            background: {"rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.07)"} !important;
            border-color: {card_border_hover} !important;
            color: {"#FFFFFF" if dark else "#000000"} !important;
            box-shadow: none !important;
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
        .hero-card, .status-card, .decision-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: {card_shadow} !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
        }}

        .metric-card {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 16px 18px !important;
            min-height: 130px !important;
            height: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            box-shadow: {card_shadow} !important;
            transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease !important;
        }}

        .hero-card:hover, .status-card:hover, .decision-card:hover, .metric-card:hover {{
            background: {card_bg_hover} !important;
            border-color: {card_border_hover} !important;
            transform: translateY(-2px);
            box-shadow: {card_shadow_hover} !important;
        }}

        /* Streamlit Native Metric cards */
        [data-testid="stMetric"] {{
            background: {c["card_bg"]} !important;
            border: 1px solid {c["card_border"]} !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border-radius: 12px !important;
            padding: 16px 18px !important;
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
            font-size: 12.5px !important;
            min-height: 34px !important;
            background-color: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"} !important;
            background: {"rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            box-shadow: none !important;
            transition: all 0.18s ease !important;
        }}
        .stButton button:hover,
        button[data-testid="stBaseButton-secondary"]:hover,
        span[data-testid="stTooltipHoverTarget"] button:hover {{
            background-color: {"rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.07)"} !important;
            background: {"rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.07)"} !important;
            border-color: {card_border_hover} !important;
            color: {"#FFFFFF" if dark else "#000000"} !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2) !important;
        }}
        .stButton button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {{
            background-color: {"rgba(255, 255, 255, 0.12)" if dark else "#18181B"} !important;
            background: {"rgba(255, 255, 255, 0.12)" if dark else "#18181B"} !important;
            color: #FFFFFF !important;
            font-weight: 700 !important;
            border: 1px solid {"rgba(255, 255, 255, 0.22)" if dark else "#18181B"} !important;
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
    if hasattr(st, "html"):
        st.html(css)
    else:
        st.markdown(css, unsafe_allow_html=True)


def render_top_control_bar(active_page: str = "Overview"):
    """Render unified top observability ribbon with dynamic live/demo system connectivity badges."""
    c = get_theme_colors()
    dark = c["is_dark"]
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    status_color = "#22C55E" if is_live else c["amber"]
    status_text = "SYSTEM OPERATIONAL" if is_live else "DEMO MODE (LOCAL TELEMETRY)"
    pulse_dot_html = (
        '<span class="pulse-dot"></span>'
        if is_live
        else f'<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {c["amber"]}; margin-right: 6px;"></span>'
    )
    tier_label = "REDIS TIER-1" if is_live else "IN-MEMORY TELEMETRY"
    stream_badge = "● LIVE STREAMING" if is_live else "● SYNTHETIC TRACE"
    stream_color = "#22C55E" if is_live else c["amber"]
    stream_bg = (
        "rgba(34, 197, 94, 0.10)" if is_live else "rgba(245, 158, 11, 0.10)"
    )
    stream_border = (
        "rgba(34, 197, 94, 0.22)" if is_live else "rgba(245, 158, 11, 0.22)"
    )

    st.markdown(
        f"""
        <div class="control-ribbon">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 6px; background: {'rgba(255, 255, 255, 0.06)' if dark else 'rgba(0, 0, 0, 0.04)'}; border: 1px solid {c['card_border']};">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{c['text']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                        </svg>
                    </div>
                    <span style="font-weight: 800; font-size: 13.5px; letter-spacing: -0.2px; color: {c['text']};">
                        AdaptiveCache
                    </span>
                    <span style="color: {c['text_subtle']}; font-size: 12px;">/</span>
                    <span style="color: {c['text_muted']}; font-size: 12.5px; font-weight: 600;">{active_page}</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="display: flex; align-items: center; font-size: 11.5px; font-weight: 700; color: {status_color};">
                    {pulse_dot_html}{status_text}
                </div>
                <div style="display: none; @media (min-width: 768px) {{ display: block; }}">
                    <span style="font-size: 11px; font-weight: 600; color: {c['text_muted']}; background: {'rgba(255, 255, 255, 0.05)' if dark else 'rgba(0, 0, 0, 0.03)'}; border: 1px solid {c['card_border']}; padding: 3px 8px; border-radius: 5px;">
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
    dark = c["is_dark"]
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    tier_status_color = "#22C55E" if is_live else c["amber"]
    tier_status_text = "● ONLINE" if is_live else "○ DEMO MODE"
    tier_subtitle = "Redis + Telemetry Loop" if is_live else "Local High-Fidelity Trace"

    with st.sidebar:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 6px 0 14px 0;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 10px; background: {'rgba(255, 255, 255, 0.06)' if dark else 'rgba(0, 0, 0, 0.04)'}; border: 1px solid {c['card_border']}; margin-bottom: 8px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{c['text']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <h2 style="margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -0.2px; color: {c['text']} !important;">ADAPTIVE CACHE</h2>
                <p class="muted" style="font-size: 11px; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.8px; color: {c['text_muted']} !important;">Control Center &bull; v2.6</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Engine Tier Status Badge
        st.markdown(
            f"""
            <div class="hero-card" style="padding: 10px 14px; margin-bottom: 16px; background: {c['card_bg']} !important; border: 1px solid {c['card_border']} !important;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: {c['text_muted']};">
                        TIER 1 ARBITER
                    </span>
                    <span style="color: {tier_status_color}; font-size: 11px; font-weight: 700;">
                        {tier_status_text}
                    </span>
                </div>
                <div style="font-size: 13px; font-weight: 600; margin-top: 4px; color: {c['text']};">
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
            help="Toggle between Black/White Glassmorphism Dark Mode and Clean Light Mode",
        )

        if new_val != is_dark:
            st.session_state["dark_mode"] = new_val
            st.rerun()

        st.divider()