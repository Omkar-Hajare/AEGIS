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
            "bg": "#0B0F19",
            "card_bg": "rgba(22, 31, 48, 0.75)",
            "card_border": "rgba(255, 255, 255, 0.08)",
            "card_border_glow": "rgba(56, 189, 248, 0.35)",
            "text": "#F8FAFC",
            "text_muted": "#94A3B8",
            "text_subtle": "#64748B",
            "sidebar_bg": "#0B0F19",
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
            "chart_grid": "rgba(255, 255, 255, 0.07)",
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


def apply_global_styles():
    """Inject responsive, polished CSS for Dark and Light modes with floating UI elements."""
    c = get_theme_colors()
    dark = c["is_dark"]

    if dark:
        body_bg = "radial-gradient(circle at 10% 20%, #0d1527 0%, #070a12 90%)"
        card_shadow = "0 4px 20px rgba(0, 0, 0, 0.4)"
        sidebar_bg = "#0B0F19"
        sidebar_border = "rgba(255, 255, 255, 0.08)"
        hr_color = "#1E293B"
        dock_bg = "rgba(15, 23, 42, 0.75)"
    else:
        body_bg = "#F4F6F9"
        card_shadow = "0 4px 16px rgba(15, 23, 42, 0.05)"
        sidebar_bg = "#EAEEF4"
        sidebar_border = "#CBD5E1"
        hr_color = "#E2E8F0"
        dock_bg = "rgba(255, 255, 255, 0.92)"

    sidebar_link_color = "#CBD5E1" if dark else "#1E293B"
    sidebar_hover_bg = "rgba(56, 189, 248, 0.1)" if dark else "rgba(2, 132, 199, 0.08)"
    sidebar_active_bg = "rgba(56, 189, 248, 0.18)" if dark else "rgba(2, 132, 199, 0.14)"

    css = f"""
    <style>
        /* Base typography & Canvas */
        .stApp {{
            background: {body_bg} !important;
            color: {c["text"]} !important;
        }}

        .main .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1420px;
        }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
            border-right: 1px solid {sidebar_border} !important;
        }}

        /* Sidebar Navigation Links */
        [data-testid="stSidebarNav"] {{
            padding-top: 0.5rem;
        }}
        [data-testid="stSidebarNav"] a {{
            border-radius: 8px !important;
            padding: 6px 12px !important;
            transition: all 0.15s ease-in-out;
        }}
        [data-testid="stSidebarNav"] a span {{
            color: {sidebar_link_color} !important;
            font-weight: 600 !important;
            font-size: 13.5px !important;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background-color: {sidebar_hover_bg} !important;
        }}
        [data-testid="stSidebarNav"] a:hover span {{
            color: {c["cyan"]} !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background-color: {sidebar_active_bg} !important;
            border-left: 3px solid {c["cyan"]} !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"] span {{
            color: {c["cyan"]} !important;
            font-weight: 700 !important;
        }}

        /* Sidebar General Elements */
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span:not(.badge-pill):not(.pulse-dot),
        [data-testid="stSidebar"] label {{
            color: {c["text"]} !important;
        }}
        [data-testid="stSidebar"] .muted {{
            color: {c["text_muted"]} !important;
        }}

        /* Toggle switch labels */
        [data-testid="stToggle"] label p,
        [data-testid="stToggle"] p,
        [data-testid="stToggle"] span {{
            color: {c["text"]} !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }}

        /* Text colors */
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
        div[data-baseweb="select"] > div {{
            background-color: {c["card_bg"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="select"] span {{
            color: {c["text"]} !important;
            font-weight: 500 !important;
        }}
        div[data-baseweb="popover"], div[data-baseweb="menu"] {{
            background-color: {c["card_bg"]} !important;
        }}
        li[role="option"] {{
            background-color: {c["card_bg"]} !important;
            color: {c["text"]} !important;
        }}

        [data-testid="stTextInput"] input {{
            background-color: {c["card_bg"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
            border-radius: 8px !important;
        }}
        [data-testid="stTextInput"] input::placeholder {{
            color: {c["text_subtle"]} !important;
        }}

        [data-testid="stSlider"] div[data-testid="stThumbValue"] {{
            color: {c["text"]} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stSlider"] div[data-testid="stTickBar"] div {{
            color: {c["text_muted"]} !important;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            color: {c["text_muted"]} !important;
            font-weight: 600 !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: {c["cyan"]} !important;
            border-bottom-color: {c["cyan"]} !important;
            font-weight: 700 !important;
        }}

        @keyframes pulseGlow {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }}
            70% {{ box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        .pulse-dot {{
            display: inline-block;
            width: 9px;
            height: 9px;
            background-color: #10B981;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulseGlow 2s infinite;
        }}

        /* Clean Glass Dock / Pill Header (Hardware Accelerated, No Repaint Jank) */
        .floating-dock {{
            background: {dock_bg};
            border: 1px solid {c["card_border"]};
            border-radius: 12px;
            padding: 10px 18px;
            margin-bottom: 18px;
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

        .hero-card:hover, .status-card:hover, .decision-card:hover {{
            border-color: {c["card_border_glow"]} !important;
            transform: translateY(-2px);
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
            background-color: {c["terminal_bg"]} !important;
            border: 1px solid {c["terminal_border"]} !important;
            border-radius: 10px;
            padding: 16px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 12px;
            color: #38BDF8;
            line-height: 1.7;
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 8px;
            font-weight: 600;
            min-height: 40px;
            transition: all 0.2s ease;
        }}
        .stButton > button:not([kind="primary"]) {{
            background-color: {c["card_bg"]} !important;
            color: {c["text"]} !important;
            border: 1px solid {c["card_border"]} !important;
        }}
        .stButton > button:not([kind="primary"]):hover {{
            border-color: {c["cyan"]} !important;
            color: {c["cyan"]} !important;
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

        /* Image frame styling */
        .img-container {{
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid {c["card_border"]};
            box-shadow: {card_shadow};
            margin-bottom: 16px;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_sidebar_branding(active_page: str = ""):
    """Render unified branding, engine tier status, and the Dark/White theme toggler (clean vector SVG icon)."""
    c = get_theme_colors()
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
                <p class="muted" style="font-size: 11px; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.8px; color: {c["text_muted"]} !important;">Observability Engine</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Engine Tier Status Badge with floating style
        st.markdown(
            f"""
            <div class="hero-card" style="padding: 10px 14px; margin-bottom: 16px; background: {c["card_bg"]} !important; border: 1px solid {c["card_border"]} !important;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: {c["text_muted"]};">
                        TIER 1 ARBITER
                    </span>
                    <span style="color: #10B981; font-size: 11px; font-weight: 700;">
                        ● ONLINE
                    </span>
                </div>
                <div style="font-size: 13px; font-weight: 600; margin-top: 4px; color: {c["text"]};">
                    Redis + Telemetry Loop
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