import streamlit as st


def apply_global_styles():
    st.markdown(
        """
        <style>

        /* Main application */
        .stApp {
            background: #0e1117;
        }

        /* Main content */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: #111827;
            border-right: 1px solid #1f2937;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 2rem;
        }

        /* Headings */
        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px;
        }

        h2 {
            font-size: 1.5rem !important;
            font-weight: 600 !important;
        }

        h3 {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background: #151b26;
            border: 1px solid #263041;
            border-radius: 12px;
            padding: 18px;
            min-height: 120px;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
        }

        /* Dataframes */
        [data-testid="stDataFrame"] {
            border: 1px solid #263041;
            border-radius: 10px;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            min-height: 40px;
        }

        /* Select boxes */
        div[data-baseweb="select"] > div {
            border-radius: 8px;
        }

        /* Status cards */
        .status-card {
            background: #151b26;
            border: 1px solid #263041;
            border-radius: 12px;
            padding: 20px;
            margin: 10px 0;
        }

        /* Adaptive decision card */
        .decision-card {
            background: #151b26;
            border: 1px solid #263041;
            border-radius: 14px;
            padding: 24px;
            margin: 12px 0;
        }

        /* Small muted text */
        .muted {
            color: #9ca3af;
            font-size: 0.9rem;
        }

        /* Divider */
        hr {
            border-color: #263041;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )