import plotly.graph_objects as go
import streamlit as st


def render_line_chart(
    x,
    y,
    title,
    y_title="",
):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name=y_title or title,
        )
    )

    fig.update_layout(
        title=title,
        height=320,
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            color="#e5e7eb",
        ),
        xaxis=dict(
            showgrid=False,
        ),
        yaxis=dict(
            gridcolor="#263041",
            title=y_title,
        ),
        legend=dict(
            orientation="h",
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )