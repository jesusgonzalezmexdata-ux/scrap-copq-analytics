"""Reporte de una página (HTML imprimible) con el diagnóstico y la acción propuesta en formato 8D."""
from __future__ import annotations

import datetime as dt
import html
import math

import pandas as pd

CLAUSES = [
    ("IATF 16949 · 8.5.1.5", "Mantenimiento productivo total: objetivos y frecuencia del preventivo"),
    ("IATF 16949 · 9.1.1.2", "Identificación de técnicas estadísticas: carta p′ de Laney y modelo binomial"),
    ("IATF 16949 · 10.2.3", "Solución de problemas: método estructurado (8D) con verificación de eficacia"),
    ("ISO 9001 · 9.1.3", "Análisis y evaluación de datos de desempeño del proceso"),
    ("ISO 9001 · 10.2", "No conformidad y acción correctiva"),
]


def mxn(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"${v / 1e6:,.2f} M" if abs(v) >= 1e6 else f"${v:,.0f}"


def _e(text) -> str:
    return html.escape(str(text))


def _table(df: pd.DataFrame) -> str:
    head = "".join(f"<th>{_e(c)}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(f"<td>{_e(v)}</td>" for v in row) + "</tr>" for row in df.itertuples(index=False))
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def headline(r) -> str:
    k, lev = r["kpis"], r["palancas"]
    share = "" if math.isnan(k["copq_pct_ventas"]) else f" ({k['copq_pct_ventas']:.2%} de las ventas)"
    text = f"El costo de no calidad fue {mxn(k['copq_mxn'])} en {k['dias']} días{share}, ≈ {mxn(k['copq_anual_mxn'])} al año."
    if lev.empty:
        return text + " Ninguna palanca tiene un efecto estadísticamente distinto de cero con estos datos."
    top = lev.iloc[0]
    total = lev["ahorro_neto_p50"].clip(lower=0).sum()
    text += (f" La palanca principal es «{top['palanca']}»: ahorro neto de {mxn(top['ahorro_neto_p50'])} al año "
             f"(P10–P90: {mxn(top['ahorro_neto_p10'])} a {mxn(top['ahorro_neto_p90'])})")
    if total > 0 and len(lev) > 1:
        text += f", {top['ahorro_neto_p50'] / total:.0%} del total de las palancas"
    return text + "."


def eight_d(r) -> list[tuple[str, str]]:
    lev, ctl, k = r["palancas"], r["control"], r["kpis"]
    worst = r["por_linea"].index[0]
    top_defect = r["pareto"]["costo"].iloc[0]["defecto"] if "costo" in r["pareto"] else None
    d2 = (f"La línea {worst} concentra {r['por_linea'].iloc[0]['pct_costo']:.0f} % del costo de scrap"
          + (f"; el defecto más caro es «{top_defect}»" if top_defect else "") + f". Tasa global {k['tasa_scrap']:.2%}.")
    steps = [("D2 · Problema", d2)]
    row = ctl[ctl["linea"] == worst]
    if not row.empty:
        row = row.iloc[0]
        steps.append(("D3 · Contención", f"Vigilar la carta p′ de {worst} a diario; hoy {row['dias_fuera_limites']} de {row['dias']} días "
                      "salen de límites. Inspección reforzada en los turnos con señal hasta cerrar D5."))
    if lev.empty:
        steps.append(("D4 · Causa raíz", "El modelo no aísla una causa con significancia estadística. Recolectar las columnas "
                      "opcionales que falten (horas desde mantenimiento, proveedor, operadores nuevos) y repetir."))
        return steps
    top = lev.iloc[0]
    evidence = ""
    if top["tipo"] == "mantenimiento":
        line = top["objetivo"]
        crow = ctl[ctl["linea"] == line]
        evidence = (f"El riesgo de scrap en {line} crece {100 * (top['razon_momios_10h'] - 1):.1f} % (momios) por cada 10 h "
                    f"después de {top['umbral_h']:.0f} h desde el preventivo.")
        if not crow.empty and "fuera_sobre_umbral" in crow and not pd.isna(crow.iloc[0].get("fuera_sobre_umbral")):
            c = crow.iloc[0]
            evidence += f" {int(c['fuera_sobre_umbral'])} de sus {c['dias_fuera_limites']} días fuera de control ocurren por encima de ese umbral."
    elif top["tipo"] == "proveedor":
        evidence = f"Los lotes del proveedor {top['objetivo']} multiplican los momios de scrap por {top['razon_momios']:.2f}."
    elif top["tipo"] == "induccion":
        evidence = f"Cada operador nuevo en la corrida multiplica los momios de scrap por {top['razon_momios_por_operador']:.2f}."
    steps += [
        ("D4 · Causa raíz", evidence + " Confirmar en piso con el equipo (5 porqués / Ishikawa) antes de D5."),
        ("D5 · Acción correctiva", f"{top['palanca']}. Ahorro neto esperado {mxn(top['ahorro_neto_p50'])} al año"
         + ("" if top["costo_capturado"] else " (bruto: falta capturar el costo de implementarla)") + "."),
        ("D6 · Verificación", "Aplicar en una línea o grupo piloto y dejar otro comparable como control durante 8 semanas; "
         "la acción es eficaz si la carta p′ del piloto baja de forma sostenida y el control no."),
        ("D7 · Prevención", "Actualizar plan de control, AMEF y plan de mantenimiento; repetir este diagnóstico cada trimestre."),
    ]
    return steps


def report_html(r, issues=None, plant: str = "Planta", data_rows=None) -> str:
    k, lev, val = r["kpis"], r["palancas"], r["validacion"]
    issues = issues or []
    errors = sum(i.nivel == "error" for i in issues)
    warnings = sum(i.nivel == "aviso" for i in issues)
    parts = [f"<h1>Diagnóstico de scrap en pesos · {_e(plant)}</h1>",
             f"<p class='meta'>Periodo {k['desde']:%d/%m/%Y} – {k['hasta']:%d/%m/%Y} · {k['lineas']} líneas · "
             f"generado el {dt.date.today():%d/%m/%Y} · Jesús R. L. González</p>",
             f"<p class='lead'>{_e(headline(r))}</p>"]

    if data_rows:
        parts.append(f"<h2>1 · Datos</h2><p>{data_rows[1]:,} de {data_rows[0]:,} filas válidas · {errors} filas excluidas por error · "
                     f"{warnings} avisos. Los datos se procesaron en el equipo del usuario.</p>")

    comp = pd.DataFrame([("Scrap", mxn(k["costo_scrap_mxn"])), ("Retrabajo", mxn(k["costo_retrabajo_mxn"])),
                         ("Reclamos de cliente", mxn(k["costo_reclamos_mxn"])), ("Total", mxn(k["copq_mxn"]))],
                        columns=["Componente", "MXN"])
    lines = r["por_linea"].reset_index()
    lines = pd.DataFrame({"Línea": lines["linea"], "Tasa de scrap": lines["tasa"].map("{:.2%}".format),
                          "Costo de scrap": lines["costo_scrap_mxn"].map(mxn), "% del costo": lines["pct_costo"].map("{:.0f} %".format)})
    parts.append("<h2>2 · Dónde está el dinero</h2><div class='cols'>" + _table(comp) + _table(lines) + "</div>")
    if "costo" in r["pareto"]:
        pc, pp = r["pareto"]["costo"], r["pareto"]["piezas"]
        rank = {d: i + 1 for i, d in enumerate(pp["defecto"])}
        top = pc.head(5)
        parts.append(_table(pd.DataFrame({"Defecto": top["defecto"], "% del costo": top["pct"].map("{:.1f} %".format),
                                          "Lugar por costo": range(1, len(top) + 1),
                                          "Lugar por piezas": top["defecto"].map(rank)})))

    ctl = r["control"]
    if not ctl.empty:
        t = pd.DataFrame({"Línea": ctl["linea"], "Días": ctl["dias"], "Fuera de límites (p′)": ctl["dias_fuera_limites"],
                          "σ_z (sobredispersión)": ctl["sigma_z"].map("{:.2f}".format)})
        if "fuera_sobre_umbral" in ctl:
            t["De ellos, sobre el umbral de horas"] = ctl["fuera_sobre_umbral"].map(lambda v: "—" if pd.isna(v) else int(v))
        parts.append("<h2>3 · Control estadístico</h2>" + _table(t)
                     + "<p class='note'>Carta p′ de Laney: corrige la sobredispersión de subgrupos grandes, que en la carta p clásica "
                       "dispara falsas alarmas.</p>")

    parts.append("<h2>4 · Palancas con efecto demostrado</h2>")
    if lev.empty:
        parts.append("<p>Ninguna.</p>")
    else:
        parts.append(_table(pd.DataFrame({
            "Palanca": lev["palanca"], "Piezas evitadas/año": lev["piezas_evitadas_anio"].map("{:,.0f}".format),
            "Costo anual": [mxn(c) if f else "sin capturar" for c, f in zip(lev["costo_anual"], lev["costo_capturado"])],
            "Ahorro neto P50": lev["ahorro_neto_p50"].map(mxn),
            "P10 – P90": [f"{mxn(a)} – {mxn(b)}" for a, b in zip(lev["ahorro_neto_p10"], lev["ahorro_neto_p90"])]})))
    if r["no_significativas"]:
        parts.append("<p class='note'>Sin efecto demostrado (no se proponen): " + _e("; ".join(r["no_significativas"])) + ".</p>")

    parts.append("<h2>5 · ¿Qué tan confiable es?</h2><ul>")
    if val:
        verdict = "le gana" if val["supera_base"] else "<b>no le gana</b>"
        parts.append(f"<li>Prueba fuera de muestra desde el {val['corte']:%d/%m/%Y} ({val['corridas_prueba']:,} corridas): el modelo "
                     f"{verdict} al promedio por línea (error medio {val['mae_modelo_pp']:.2f} contra {val['mae_base_pp']:.2f} pp, "
                     f"{val['mejora_pct']:+.0f} %).</li>")
    else:
        parts.append("<li>Menos de 60 días: no hay prueba fuera de muestra.</li>")
    parts.append(f"<li>Sobredispersión del modelo: {r['dispersion']:.2f} (los intervalos ya la incluyen).</li>"
                 "<li>Intervalos P10–P90 por simulación de los coeficientes; no incluyen cambios futuros del proceso.</li>"
                 "<li>El modelo muestra asociación con el scrap; la causa se confirma en piso (D4) y con el piloto (D6).</li></ul>")
    if val and not val["supera_base"]:
        parts.append("<p class='warn'>Criterio de abandono: el modelo no supera al promedio por línea. No pasar a piloto con estas palancas.</p>")

    parts.append("<h2>6 · Acción propuesta (8D)</h2><dl>"
                 + "".join(f"<dt>{_e(a)}</dt><dd>{_e(b)}</dd>" for a, b in eight_d(r)) + "</dl>")
    parts.append("<h2>Referencias</h2>" + _table(pd.DataFrame(CLAUSES, columns=["Requisito", "Cómo se atiende"])))

    css = """body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#1b1b1b;max-width:860px;margin:24px auto;
padding:0 16px;font-size:14px;line-height:1.5}h1{font-size:22px;margin-bottom:2px}h2{font-size:16px;margin:22px 0 6px;
border-bottom:2px solid #2a78d6;padding-bottom:2px}.meta{color:#666;margin-top:0}.lead{font-size:15px;background:#f3f6fb;
padding:10px 12px;border-left:4px solid #2a78d6}table{border-collapse:collapse;margin:6px 0;font-size:13px}th,td{border:1px solid #ddd;
padding:4px 8px;text-align:left}th{background:#f5f5f2}.cols{display:flex;gap:16px;flex-wrap:wrap}.note{color:#555;font-size:12.5px}
.warn{background:#fdecea;padding:8px 10px;border-left:4px solid #d03b3b}dt{font-weight:600;margin-top:6px}dd{margin:0 0 4px 0}
@media print{body{margin:0}h2{break-after:avoid}}"""
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Diagnóstico de scrap · "
            f"{_e(plant)}</title><style>{css}</style></head><body>" + "".join(parts) + "</body></html>")
