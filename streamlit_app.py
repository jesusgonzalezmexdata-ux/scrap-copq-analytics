"""Tablero interactivo: streamlit run streamlit_app.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scrap_copq import metrics as m, model as md
from scrap_copq.clean import load
from scrap_copq.config import PROCESSED, SHIFTS

st.set_page_config(page_title="Scrap y COPQ · planta de autopartes", page_icon="🏭", layout="wide")

mode = st.segmented_control("Modo", ["Planta de ejemplo", "Tus datos"], default="Planta de ejemplo", required=True,
                            label_visibility="collapsed")
if mode == "Tus datos":
    from scrap_copq.ui_diagnostico import render
    render()
    st.stop()

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
ACCENT, DIM, CRITICAL = SERIES[0], "#d6d5ce", "#d03b3b"
INK, INK_2, MUTED, GRID, BASE, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
LINES = ["L1", "L2", "L3"]
CURRENT_PM_H = 320
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SHORT = {"mantenimiento": "Mantenimiento de L2", "induccion": "Inducción", "proveedor": "Proveedor C → A"}


def style(fig, title, height=380, **layout):
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=16, color=INK)), height=height,
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color=INK_2),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, margin=dict(l=10, r=10, t=64, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None, traceorder="normal"),
        hoverlabel=dict(bgcolor="white", font_color=INK), barcornerradius=4, **layout)
    fig.update_xaxes(showgrid=False, linecolor=BASE, ticks="", automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=BASE, automargin=True)
    return fig


@st.cache_data
def get_data():
    t = load(PROCESSED)
    t["prod"] = m.with_costs(t["produccion_turnos"], t["catalogo_productos"])
    return t


@st.cache_resource
def get_model():
    prod = get_data()["prod"]
    threshold, _ = md.find_threshold(prod)
    return threshold, md.fit(prod, threshold)


@st.cache_data
def savings(interval, gap_closed):
    t, (threshold, res) = get_data(), get_model()
    return md.simulate_savings(res, t["prod"], t["catalogo_productos"], t["altas_operadores"],
                               t["mantenimientos"], t["reclamos_cliente"], threshold,
                               interval=interval, gap_closed=gap_closed, n_sims=500)


@st.cache_data
def maintenance_curve():
    t, (threshold, res) = get_data(), get_model()
    return md.maintenance_curve(res, t["prod"], t["catalogo_productos"], t["mantenimientos"], threshold)


def month_ticks(fig, dates):
    months = pd.date_range(dates.min().to_period("M").to_timestamp(), dates.max(), freq="MS")
    fig.update_xaxes(tickvals=months, ticktext=[MESES[d.month - 1] for d in months])
    return fig


def fecha_es(dates):
    return [f"{d.day} {MESES[d.month - 1]}" for d in dates]


def mxn(v):
    return f"${v / 1e6:,.2f} M" if abs(v) >= 1e6 else f"${v / 1e3:,.0f} mil"


t = get_data()
prod_all = t["prod"]
start, end = prod_all["fecha"].min().date(), prod_all["fecha"].max().date()

st.title("Scrap y costo de no calidad")
st.caption("Planta ficticia de autopartes · 3 líneas · 2025 · **datos sintéticos** generados con "
           "`scrap_copq/generate.py`. Análisis completo en `notebooks/analisis_scrap_copq.ipynb`.")

f1, f2, f3 = st.columns(3)
period = f1.date_input("Periodo", (start, end), min_value=start, max_value=end, format="DD/MM/YYYY")
lines = f2.multiselect("Líneas", LINES, default=LINES)
shifts = f3.multiselect("Turnos", SHIFTS, default=SHIFTS)
if len(period) != 2 or not lines or not shifts:
    st.info("Elige un periodo completo, al menos una línea y al menos un turno.")
    st.stop()

d0, d1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
prod = prod_all[prod_all["fecha"].between(d0, d1) & prod_all["linea"].isin(lines) & prod_all["turno"].isin(shifts)]
claims = t["reclamos_cliente"]
claims = claims[claims["fecha"].between(d0, d1) & claims["linea"].isin(lines)]
defects = t["scrap_por_defecto"][t["scrap_por_defecto"]["run_id"].isin(prod["run_id"])]
if prod.empty:
    st.warning("No hay producción con esos filtros.")
    st.stop()

k = m.kpis(prod, claims)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Costo de no calidad (MXN)", mxn(k["copq_mxn"]), border=True)
c2.metric("Tasa de scrap", f"{k['tasa_scrap']:.2%}", border=True)
c3.metric("COPQ / ventas", f"{k['copq_pct_ventas']:.2%}", border=True)
c4.metric("Reclamos de cliente", k["reclamos"], border=True)

tab_cost, tab_pareto, tab_spc, tab_causes, tab_sim = st.tabs(
    ["Costo por mes", "Pareto", "Control estadístico", "Causas", "Simulador de ahorro"])

with tab_cost:
    monthly = m.copq_by_month(prod, claims)
    fig = go.Figure()
    for (col, label), color in zip([("costo_scrap_mxn", "Scrap"), ("costo_retrabajo_mxn", "Retrabajo"),
                                    ("costo_reclamos_mxn", "Reclamos de cliente")], SERIES):
        fig.add_bar(x=monthly.index, y=monthly[col], name=label, marker=dict(color=color, line=dict(color=SURFACE, width=2)),
                    customdata=[MESES[d.month - 1] for d in monthly.index],
                    hovertemplate="%{customdata} · " + label + ": $%{y:,.0f}<extra></extra>")
    style(fig, "Costo de no calidad por mes (MXN)", barmode="stack", bargap=0.45)
    st.plotly_chart(month_ticks(fig, monthly.index), theme=None)
    with st.expander("Ver tabla"):
        st.dataframe(monthly.rename(index=lambda d: d.strftime("%Y-%m")).style.format("${:,.0f}"))

with tab_pareto:
    by = st.segmented_control("Ordenar por", ["Costo", "Piezas"], default="Costo", required=True)
    par = m.pareto(defects, prod, claims if by == "Costo" else None, by="costo" if by == "Costo" else "piezas")
    fig = go.Figure()
    fig.add_bar(x=par["defecto"], y=par["pct"], name="% del total",
                marker_color=[ACCENT if v else DIM for v in par["pocos_vitales"]],
                customdata=par["valor"], hovertemplate="%{x}: %{y:.1f} % (%{customdata:,.0f})<extra></extra>")
    fig.add_scatter(x=par["defecto"], y=par["pct_acum"], name="% acumulado", mode="lines+markers",
                    line=dict(color=INK_2, width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                    hovertemplate="%{x}: %{y:.1f} % acumulado<extra></extra>")
    fig.add_hline(y=80, line=dict(color=MUTED, width=1), annotation_text="80 %", annotation_position="top left")
    st.plotly_chart(style(fig, f"Pareto de defectos por {by.lower()} · en azul, los que suman el 80 %",
                          bargap=0.55, yaxis=dict(range=[0, 105], ticksuffix=" %")), theme=None)
    st.caption("Por costo se suman los reclamos de cliente atribuidos a cada defecto. La *falta de fusión* "
               "es poco frecuente, pero de las más caras.")

with tab_spc:
    s1, s2 = st.columns([1, 2])
    line = s1.segmented_control("Línea", [ln for ln in LINES if ln in lines], default="L2" if "L2" in lines else lines[0], required=True)
    laney = s2.toggle("Carta p′ de Laney (corrige la sobredispersión)", value=True)
    if line:
        chart = m.p_chart(m.daily(prod, line), laney=laney)
        out = chart[chart["regla_1"]]
        fig = go.Figure()
        for col, name, color in (("lsc", "LSC", MUTED), ("lic", "LIC", MUTED)):
            fig.add_scatter(x=chart.index, y=chart[col], name=name, line=dict(color=color, width=1, shape="hvh"),
                            hoverinfo="skip", showlegend=False)
        fig.add_hline(y=chart["lc"].iat[0], line=dict(color=INK_2, width=1), annotation_text="LC",
                      annotation_position="top left")
        fig.add_scatter(x=chart.index, y=chart["p"], name="Tasa diaria", line=dict(color=ACCENT, width=2),
                        customdata=list(zip(fecha_es(chart.index), chart["n"])),
                        hovertemplate="%{customdata[0]}: %{y:.2%} de %{customdata[1]:,} piezas<extra></extra>")
        fig.add_scatter(x=out.index, y=out["p"], mode="markers", name="Fuera de límites",
                        marker=dict(color=CRITICAL, size=9, line=dict(color=SURFACE, width=2)),
                        customdata=fecha_es(out.index), hovertemplate="%{customdata}: %{y:.2%} · fuera de límites<extra></extra>")
        kind = "p′ de Laney" if laney else "p clásica"
        style(fig, f"Carta {kind} · {line}: {len(out)} días fuera de límites de {len(chart)}",
              yaxis=dict(tickformat=".1%"))
        st.plotly_chart(month_ticks(fig, chart.index), theme=None)
        if laney:
            st.caption(f"σ_z = {chart.attrs['sigma_z']:.2f}: la variación real entre días es {chart.attrs['sigma_z']:.1f} "
                       "veces la binomial, por eso los límites son más anchos que en la carta clásica.")
        hours = prod[prod["linea"] == line].groupby("fecha")[["horas_desde_mantto", "paro_min"]].mean()
        with st.expander("Días fuera de límites"):
            st.dataframe(out[["n", "x", "p"]].join(hours).rename(columns={
                "n": "Piezas", "x": "Scrap", "p": "Tasa", "horas_desde_mantto": "Horas desde mantto (prom.)",
                "paro_min": "Paro (min, prom.)"}).style.format({"Tasa": "{:.2%}", "Horas desde mantto (prom.)": "{:.0f}",
                                                                "Paro (min, prom.)": "{:.0f}"}))

with tab_causes:
    left, right = st.columns(2)
    binned = m.rate_by_maintenance_hours(prod)
    binned = binned[binned["corridas"] >= 10]
    fig = go.Figure()
    for ln, g in binned.groupby("linea"):
        focus = ln == "L2"
        fig.add_scatter(x=g["horas"], y=g["tasa"], name=ln, mode="lines+markers",
                        line=dict(color=ACCENT if focus else DIM, width=2.5 if focus else 2),
                        marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                        hovertemplate=ln + " · %{x:.0f} h: %{y:.2%}<extra></extra>")
    threshold, res = get_model()
    fig.add_vline(x=threshold, line=dict(color=MUTED, width=1), annotation_text=f"Umbral: {threshold} h")
    left.plotly_chart(style(fig, "Scrap según horas desde el mantenimiento", height=360,
                            xaxis=dict(title="horas de operación desde el último preventivo"),
                            yaxis=dict(tickformat=".1%")), theme=None)

    night = prod[prod["turno"] == "Nocturno"].assign(con=lambda d: d["operadores_nuevos"] > 0)
    if not night.empty:
        rates = m.scrap_rate(night, ["linea", "con"]).unstack()
        fig = go.Figure()
        for flag, label, color in ((False, "Sin operadores nuevos", SERIES[0]), (True, "Con operadores nuevos", SERIES[1])):
            if flag in rates:
                fig.add_bar(x=rates.index, y=rates[flag], name=label, marker=dict(color=color, line=dict(color=SURFACE, width=2)),
                            hovertemplate="%{x} · " + label.lower() + ": %{y:.2%}<extra></extra>")
        right.plotly_chart(style(fig, "Turno nocturno: scrap con y sin operadores nuevos", height=360,
                                 barmode="group", bargap=0.45, yaxis=dict(tickformat=".1%")), theme=None)
    odds = md.odds_ratios(res).rename(columns={"odds_ratio": "Razón de momios", "ic95_inf": "IC 95 % inferior",
                                               "ic95_sup": "IC 95 % superior", "p_valor": "Valor p"})
    st.dataframe(odds.style.format("{:.2f}").format(lambda p: "< 0.001" if p < 0.001 else f"{p:.3f}", subset="Valor p"))
    st.caption("Razones de momios del GLM binomial (año completo). Mayor que 1 = eleva la probabilidad de scrap.")

with tab_sim:
    st.markdown("Ahorro anual estimado con el modelo, sobre el **año completo** (no usa los filtros de arriba).")
    a, b, c = st.columns(3)
    threshold, _ = get_model()
    interval = a.slider("Intervalo de mantenimiento en L2 (h)", 100, 340, int(threshold), 10)
    gap = b.slider("Brecha cerrada por la inducción", 0, 100, 50, 10, format="%d %%")
    use_supplier = c.toggle("Reasignar lotes del proveedor C al A", value=True)
    sav = savings(interval, gap / 100)
    chosen = sav if use_supplier else sav.drop(index="proveedor")
    k1, k2, k3, k4 = st.columns(4)
    for col, lever in zip((k1, k2, k3), ("mantenimiento", "induccion", "proveedor")):
        row = sav.loc[lever]
        col.metric(f"{SHORT[lever]} · neto", mxn(row["ahorro_neto_p50"]), border=True,
                   help=f"{md.LEVERS[lever]}. Bruto {mxn(row['ahorro_bruto_p50'])} − costo {mxn(row['costo_anual'])}. "
                        f"P10–P90: {mxn(row['ahorro_neto_p10'])} a {mxn(row['ahorro_neto_p90'])}.")
    k4.metric("Total seleccionado", mxn(chosen["ahorro_neto_p50"].sum()), border=True)

    curve = maintenance_curve()
    fig = go.Figure()
    fig.add_scatter(x=curve.index, y=curve["ahorro_neto"], name="Ahorro neto", line=dict(color=ACCENT, width=2),
                    hovertemplate="%{x} h: $%{y:,.0f}<extra></extra>")
    for x, label, color in ((interval, "Elegido", ACCENT), (CURRENT_PM_H, "Actual", INK_2)):
        if x in curve.index:
            fig.add_scatter(x=[x], y=[curve.loc[x, "ahorro_neto"]], mode="markers+text", text=[f"{label}: {x} h"],
                            textposition="top center", showlegend=False, hoverinfo="skip",
                            marker=dict(size=10, color=color, line=dict(color=SURFACE, width=2)))
    top = curve["ahorro_neto"].max() * 1.25
    st.plotly_chart(style(fig, "Ahorro neto del mantenimiento de L2 según el intervalo (MXN/año)", height=360,
                          showlegend=False, xaxis=dict(title="horas de operación entre preventivos"),
                          yaxis=dict(range=[min(0, curve["ahorro_neto"].min()) * 1.1, top])), theme=None)
    st.caption("Supuestos en `scrap_copq/config.py`: preventivo adicional 4,500 MXN; inducción 15,000 MXN por "
               "operador nuevo; el proveedor C es 2 % más barato. Incertidumbre: 500 simulaciones de los coeficientes.")
