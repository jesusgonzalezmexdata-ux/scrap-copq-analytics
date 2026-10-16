"""Pestaña «Tus datos»: el diagnóstico sobre el Excel de una planta real, procesado en el navegador."""
import plotly.graph_objects as go
import streamlit as st

from . import diagnose as dg, intake, report as rp

BLUE, GREY, INK = "#2a78d6", "#d6d5ce", "#0b0b0b"


@st.cache_data(show_spinner=False)
def _template():
    return intake.template_bytes()


@st.cache_data(show_spinner=False)
def _dirty_example():
    return intake.example_with_errors()


@st.cache_data(show_spinner="Validando y analizando…")
def _run(content: bytes, settings: dg.Settings):
    data, issues = intake.validate(intake.read_workbook(content))
    return data, issues, dg.diagnose(data, settings)


def _pareto_fig(pc, pp):
    rank = {d: i + 1 for i, d in enumerate(pp["defecto"])}
    fig = go.Figure()
    fig.add_bar(x=pc["defecto"], y=pc["pct"], marker_color=[BLUE if v else GREY for v in pc["pocos_vitales"]],
                customdata=[rank.get(d) for d in pc["defecto"]],
                hovertemplate="%{x}: %{y:.1f} % del costo · lugar %{customdata} por piezas<extra></extra>")
    fig.update_layout(title="Pareto por costo (en azul, el 80 %)", height=340, margin=dict(l=10, r=10, t=50, b=10),
                      yaxis=dict(ticksuffix=" %"), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", font_color=INK)
    return fig


def render():
    st.subheader("Diagnóstico de scrap con tus datos")
    st.markdown("Sube el Excel de tu planta y obtén el costo de no calidad, las cartas p′ y las palancas de ahorro con su "
                "intervalo, más un reporte de una página en formato 8D. **El archivo se procesa en tu navegador: "
                "no se envía a ningún servidor.**")
    st.download_button("Descargar plantilla de Excel (con datos de ejemplo)", _template(), "plantilla_scrap.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Hojas: *produccion* (una fila por corrida), *costos* (por producto) y *reclamos* (opcional). "
               "La hoja *instrucciones* explica cada columna. Mínimo 3 meses; ideal 12.")

    up = st.file_uploader("Tu archivo .xlsx", type=["xlsx"])
    if st.button("O prueba con un archivo de ejemplo que trae errores de captura"):
        st.session_state["ejemplo"] = True
    plant = st.text_input("Nombre de la planta o línea (aparece en el reporte)", "Mi planta")
    with st.expander("Costos de implementar cada palanca"):
        a, b, c = st.columns(3)
        pm = a.number_input("Un preventivo adicional (MXN)", 0, 1_000_000, 4_500, 500)
        ind = b.number_input("Programa de inducción al año (MXN)", 0, 10_000_000, 0, 5_000)
        sup = c.number_input("Cambiar de proveedor al año (MXN)", 0, 10_000_000, 0, 5_000)
        gap = st.slider("Parte del efecto de operadores nuevos que cierra la inducción", 0, 100, 50, 10, format="%d %%")
        st.caption("Sin costo capturado, el ahorro de esa palanca se reporta como bruto.")
    if up is not None:
        content = up.getvalue()
    elif st.session_state.get("ejemplo"):
        content = _dirty_example()
        st.caption("Analizando el archivo de ejemplo: la planta sintética con encabezados en otro formato, 4 filas con error, turnos mal escritos y 2 filas duplicadas.")
    else:
        st.info("Para probar, descarga la plantilla y súbela tal cual, o usa el archivo de ejemplo con errores.")
        return

    settings = dg.Settings(costo_preventivo_mxn=pm, costo_induccion_mxn=ind, costo_cambio_proveedor_mxn=sup,
                           brecha_induccion=gap / 100)
    try:
        data, issues, r = _run(content, settings)
    except intake.DataError as exc:
        st.error(str(exc))
        return

    errors = [i for i in issues if i.nivel == "error"]
    st.markdown(f"**{data['filas_validas']:,} de {data['filas_leidas']:,} filas válidas** · {len(errors)} filas excluidas · "
                f"{len(issues) - len(errors)} avisos")
    if issues:
        with st.expander("Ver errores y avisos de los datos", expanded=bool(errors)):
            st.dataframe(intake.issues_frame(issues), hide_index=True)

    k = r["kpis"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Costo de no calidad", rp.mxn(k["copq_mxn"]), border=True)
    c2.metric("Anualizado", rp.mxn(k["copq_anual_mxn"]), border=True)
    c3.metric("Tasa de scrap", f"{k['tasa_scrap']:.2%}", border=True)
    c4.metric("COPQ / ventas", "—" if k["copq_pct_ventas"] != k["copq_pct_ventas"] else f"{k['copq_pct_ventas']:.2%}", border=True)
    st.success(rp.headline(r))

    lev = r["palancas"]
    if not lev.empty:
        st.markdown("**Palancas con efecto demostrado (ahorro anual)**")
        st.dataframe(lev[["palanca", "piezas_evitadas_anio", "costo_anual", "ahorro_neto_p10", "ahorro_neto_p50", "ahorro_neto_p90"]]
                     .rename(columns={"palanca": "Palanca", "piezas_evitadas_anio": "Piezas evitadas", "costo_anual": "Costo",
                                      "ahorro_neto_p10": "Neto P10", "ahorro_neto_p50": "Neto P50", "ahorro_neto_p90": "Neto P90"})
                     .style.format({"Piezas evitadas": "{:,.0f}", "Costo": "${:,.0f}", "Neto P10": "${:,.0f}",
                                    "Neto P50": "${:,.0f}", "Neto P90": "${:,.0f}"}), hide_index=True)
    left, right = st.columns(2)
    if "costo" in r["pareto"]:
        left.plotly_chart(_pareto_fig(r["pareto"]["costo"], r["pareto"]["piezas"]), theme=None)
    if not r["control"].empty:
        right.markdown("**Carta p′ de Laney por línea**")
        right.dataframe(r["control"].rename(columns={"linea": "Línea", "dias": "Días", "dias_fuera_limites": "Fuera de límites",
                                                     "dias_con_senal": "Con señal", "sigma_z": "σ_z", "tasa_media": "Tasa media",
                                                     "fuera_sobre_umbral": "Fuera y sobre umbral de horas"}),
                        hide_index=True)
    val = r["validacion"]
    if val:
        (st.caption if val["supera_base"] else st.warning)(
            f"Prueba fuera de muestra: error medio {val['mae_modelo_pp']:.2f} pp contra {val['mae_base_pp']:.2f} pp del promedio "
            f"por línea ({val['mejora_pct']:+.0f} %)." + ("" if val["supera_base"] else " No pasar a piloto con estas palancas."))

    for a, b in rp.eight_d(r):
        st.markdown(f"**{a}.** {b}")
    html_report = rp.report_html(r, issues, plant, (data["filas_leidas"], data["filas_validas"]))
    st.download_button("Descargar reporte de una página (HTML, imprimible a PDF)", html_report.encode("utf-8"),
                       "diagnostico_scrap.html", "text/html", type="primary")
