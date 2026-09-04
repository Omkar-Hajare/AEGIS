import streamlit as st

from frontend.components.styles import apply_global_styles


st.set_page_config(
    page_title="Adaptive Cache System",
    page_icon="⚡",
    layout="wide",
)

# Apply global dashboard styling
apply_global_styles()


# Sidebar branding
with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 10px 0 25px 0;">
            <div style="font-size: 42px;">⚡</div>
            <h2 style="margin: 0;">Adaptive Cache</h2>
            <p style="color: #9ca3af; font-size: 13px;">
                Intelligent Cache Management
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        """
        <div style="
            background: #151b26;
            border: 1px solid #263041;
            border-radius: 10px;
            padding: 12px;
            margin-top: 10px;
        ">
            <div style="font-size: 13px; color: #9ca3af;">
                SYSTEM STATUS
            </div>
            <div style="
                font-size: 16px;
                font-weight: 600;
                margin-top: 6px;
            ">
                🟢 System Healthy
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Main landing page
st.title("⚡ Adaptive Cache System")

st.markdown(
    """
    ### Workload-aware intelligent caching

    Monitor cache performance, analyze workload behavior,
    and observe adaptive cache decisions in real time.
    """
)

st.divider()

# Quick overview cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="status-card">
            <h3>⚡ Adaptive Engine</h3>
            <p class="muted">
                Workload-aware cache optimization
            </p>
            <strong>● Active</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="status-card">
            <h3>🗄️ Cache Layer</h3>
            <p class="muted">
                Redis-backed intelligent caching
            </p>
            <strong>● Operational</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="status-card">
            <h3>📊 Monitoring</h3>
            <p class="muted">
                Performance and workload telemetry
            </p>
            <strong>● Connected</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.divider()

st.info(
    "Use the sidebar to explore cache performance, "
    "adaptive decisions, workload behavior, and benchmarks."
)