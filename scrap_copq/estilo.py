"""Acabado «Señal de campo» que el tema de Streamlit no cubre: botón principal amarillo y cifras condensadas."""
import streamlit as st

CSS = """
<style>
[data-testid="stBaseButton-primary"], button[kind="primary"] { background: #FFD21F !important; color: #0E0F11 !important; border: 0 !important; font-weight: 600 !important; }
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover { background: #F2C400 !important; }
[data-testid="stMetricValue"] { font-family: "Barlow Condensed", "Arial Narrow", sans-serif; font-weight: 600; }
[data-testid="stMetric"] { background: #FFFFFF; border-radius: 4px; }
</style>
"""


def aplicar():
    st.html(CSS)
