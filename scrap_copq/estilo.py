"""Acabado «Señal de campo» que el tema no cubre en todas partes: tipografía Barlow (también en la demo del navegador),
botón principal amarillo y cifras condensadas."""
import streamlit as st

CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;600&display=swap");
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp td, .stApp th { font-family: Barlow, system-ui, sans-serif; }
.stApp h1, .stApp h2, .stApp h3 { font-family: "Barlow Condensed", "Arial Narrow", sans-serif; font-weight: 700; }
[data-testid="stBaseButton-primary"], button[kind="primary"] { background: #FFD21F !important; color: #0E0F11 !important; border: 0 !important; font-weight: 600 !important; }
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover { background: #F2C400 !important; }
[data-testid="stMetricValue"] { font-family: "Barlow Condensed", "Arial Narrow", sans-serif; font-weight: 600; }
[data-testid="stMetric"] { background: #FFFFFF; border-radius: 4px; }
</style>
"""


def aplicar():
    st.html(CSS)
