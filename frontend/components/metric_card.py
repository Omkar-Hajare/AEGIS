import streamlit as st


def render_metric_card(
    title,
    value,
    subtitle="",
    icon="📊",
):
    html = (
        f'<div style="background:#151b26;'
        f'border:1px solid #263041;'
        f'border-radius:14px;'
        f'padding:20px;'
        f'min-height:135px;'
        f'box-shadow:0 4px 15px rgba(0,0,0,0.15);">'
        
        f'<div style="display:flex;'
        f'justify-content:space-between;'
        f'align-items:center;">'
        
        f'<span style="color:#9ca3af;'
        f'font-size:14px;'
        f'font-weight:500;">'
        f'{title}'
        f'</span>'
        
        f'<span style="font-size:22px;">'
        f'{icon}'
        f'</span>'
        
        f'</div>'
        
        f'<div style="font-size:32px;'
        f'font-weight:700;'
        f'margin-top:14px;">'
        f'{value}'
        f'</div>'
        
        f'<div style="color:#9ca3af;'
        f'font-size:12px;'
        f'margin-top:6px;">'
        f'{subtitle}'
        f'</div>'
        
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)