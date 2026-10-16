"""Diagnóstico de scrap en pesos sobre los datos de una planta real (salida de intake.validate).

Generaliza el análisis del caso sintético: no supone nombres de líneas, turnos ni proveedores.
Cada palanca se reporta solo si su efecto es estadísticamente distinto de cero.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from . import metrics as m

MIN_SUPPLIER_RUNS = 30


@dataclass
class Settings:
    costo_preventivo_mxn: float = 4_500      # costo de un preventivo adicional
    costo_induccion_mxn: float = 0.0         # costo anual del programa de inducción
    costo_cambio_proveedor_mxn: float = 0.0  # costo anual de mover los lotes de un proveedor
    brecha_induccion: float = 0.5            # fracción del efecto de operadores nuevos que cierra la inducción
    n_sims: int = 1000
    seed: int = 7


# ------------------------------------------------------------------ modelo
def _spec(prod, cols):
    count = lambda c: prod[c].value_counts()  # noqa: E731
    spec = {"lines": list(count("linea").index), "shifts": list(count("turno").index),
            "suppliers": [], "operators": False, "hinge_lines": []}
    if cols.get("proveedor"):
        runs = prod.dropna(subset=["proveedor"]).groupby("proveedor")
        ok = runs.size()[runs.size() >= MIN_SUPPLIER_RUNS].index
        if len(ok) > 1:
            rate = (runs["piezas_scrap"].sum() / runs["piezas_producidas"].sum())[ok]
            spec["suppliers"] = list(rate.sort_values().index)        # el primero (mejor) es la referencia
    if cols.get("operadores") and prod["operadores_nuevos"].nunique() > 1:
        spec["operators"] = True
    if cols.get("horas"):
        for line, h in prod.groupby("linea")["horas_desde_mantto"]:
            if h.notna().mean() >= 0.8 and h.max() - h.min() > 50:
                spec["hinge_lines"].append(line)
    return spec


def _col(prefix, name):
    return f"{prefix}{name}"


def design(prod, spec, thresholds):
    X = {"const": np.ones(len(prod))}
    for line in spec["lines"][1:]:
        X[_col("linea=", line)] = (prod["linea"] == line).to_numpy(float)
    for shift in spec["shifts"][1:]:
        X[_col("turno=", shift)] = (prod["turno"] == shift).to_numpy(float)
    for sup in spec["suppliers"][1:]:
        X[_col("proveedor=", sup)] = (prod["proveedor"] == sup).to_numpy(float)
    if spec["operators"]:
        X["operadores_nuevos"] = prod["operadores_nuevos"].to_numpy(float)
    for line, thr in thresholds.items():
        excess = (prod["horas_desde_mantto"] - thr).clip(lower=0).fillna(0) / 10
        X[_col("exceso_mantto=", line)] = (excess * (prod["linea"] == line)).to_numpy(float)
    return pd.DataFrame(X, index=prod.index)


def fit(prod, spec, thresholds):
    """GLM binomial con escala cuasi-binomial (χ² de Pearson / gl) por la sobredispersión."""
    X = design(prod, spec, thresholds)
    X = X.loc[:, X.ne(0).any()]
    n = prod["piezas_producidas"].astype(float)
    return sm.GLM(prod["piezas_scrap"] / n, X, family=sm.families.Binomial(), var_weights=n).fit(scale="X2")


def find_thresholds(prod, spec):
    """Umbral de horas desde el preventivo, por línea, que minimiza la devianza."""
    out, curves = {}, {}
    for line in spec["hinge_lines"]:
        h = prod.loc[prod["linea"] == line, "horas_desde_mantto"].dropna()
        grid = np.unique(np.round(np.quantile(h, np.linspace(0.1, 0.9, 17)) / 10) * 10)
        dev = pd.Series({float(t): fit(prod, spec, {line: t}).deviance for t in grid})
        out[line], curves[line] = float(dev.idxmin()), dev
    return out, curves


def _exog(res, prod, spec, thresholds):
    return design(prod, spec, thresholds).reindex(columns=res.model.exog_names, fill_value=0.0)


def _expected(X, betas, n):
    return n * (1 / (1 + np.exp(-(X.to_numpy() @ np.atleast_2d(betas).T)))).T


# ------------------------------------------------------------------ palancas
def _pm_cost(prod, line, thr, settings, annual):
    """Preventivos adicionales al año si la línea se interviene cada `thr` horas."""
    h = prod.loc[prod["linea"] == line].sort_values(["fecha", "run_id"])["horas_desde_mantto"].dropna().to_numpy()
    if len(h) < 2:
        return 0.0, None
    d = np.diff(h)
    resets = d < -0.5 * h[:-1]
    accrued = d[~resets & (d > 0)].sum() + h[1:][resets].sum()
    peaks = h[:-1][resets]
    current = float(np.median(peaks)) if len(peaks) else float(h.max())
    hours_year = accrued * annual
    extra = max(0.0, hours_year / thr - hours_year / current)
    return extra * settings.costo_preventivo_mxn, current


def levers(res, prod, spec, thresholds, settings, annual):
    params, ci = res.params, res.conf_int()
    sig = lambda c: c in params and ci.loc[c, 0] > 0  # noqa: E731
    base_X = _exog(res, prod, spec, thresholds)
    n = prod["piezas_producidas"].to_numpy(float)
    unit = prod["costo_unitario_scrap_mxn"].to_numpy(float)
    betas = np.random.default_rng(settings.seed).multivariate_normal(params, res.cov_params(), settings.n_sims)
    base = _expected(base_X, betas, n)
    candidates, not_sig = [], []

    for line, thr in thresholds.items():
        c = _col("exceso_mantto=", line)
        if sig(c):
            X = base_X.copy()
            X[c] = 0.0
            cost, current = _pm_cost(prod, line, thr, settings, annual)
            candidates.append(("mantenimiento", line, f"Preventivo de la línea {line} cada {thr:.0f} h"
                               + (f" (hoy ≈ {current:.0f} h)" if current else ""), X, cost,
                               {"umbral_h": thr, "intervalo_actual_h": current,
                                "razon_momios_10h": float(np.exp(params[c]))}))
        else:
            not_sig.append(f"Desgaste por horas desde el preventivo en la línea {line}")
    for sup in spec["suppliers"][1:]:
        c = _col("proveedor=", sup)
        if sig(c):
            X = base_X.copy()
            X[c] = 0.0
            candidates.append(("proveedor", sup, f"Mover los lotes del proveedor {sup} al {spec['suppliers'][0]}", X,
                               settings.costo_cambio_proveedor_mxn, {"razon_momios": float(np.exp(params[c]))}))
        elif c in params:
            not_sig.append(f"Proveedor {sup} frente a {spec['suppliers'][0]}")
    if spec["operators"]:
        c = "operadores_nuevos"
        if sig(c):
            X = base_X.copy()
            X[c] = X[c] * (1 - settings.brecha_induccion)
            candidates.append(("induccion", "todas", f"Inducción por competencias (cierra {settings.brecha_induccion:.0%} "
                               "del efecto de operadores nuevos)", X, settings.costo_induccion_mxn,
                               {"razon_momios_por_operador": float(np.exp(params[c]))}))
        else:
            not_sig.append("Operadores nuevos")

    rows = []
    for kind, target, label, X, cost, extra in candidates:
        alt = _expected(X, betas, n)
        avoided = (base - alt).sum(axis=1) * annual
        gross = ((base - alt) * unit).sum(axis=1) * annual
        p10, p50, p90 = np.percentile(gross, [10, 50, 90])
        rows.append({"tipo": kind, "objetivo": target, "palanca": label,
                     "piezas_evitadas_anio": float(np.median(avoided)),
                     "ahorro_bruto_p10": p10, "ahorro_bruto_p50": p50, "ahorro_bruto_p90": p90,
                     "costo_anual": float(cost), "ahorro_neto_p10": p10 - cost, "ahorro_neto_p50": p50 - cost,
                     "ahorro_neto_p90": p90 - cost, "costo_capturado": cost > 0, **extra})
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values("ahorro_neto_p50", ascending=False).reset_index(drop=True)
    return table, not_sig


# ------------------------------------------------------------------ validación y control
def validate_holdout(prod, cols, frac=0.25):
    """Entrena con el primer 75 % de los días y evalúa el resto contra el promedio por línea."""
    days = np.sort(prod["fecha"].unique())
    if len(days) < 60:
        return None
    cutoff = days[int(len(days) * (1 - frac))]
    train, test = prod[prod["fecha"] < cutoff], prod[prod["fecha"] >= cutoff]
    spec = _spec(train, cols)
    thresholds, _ = find_thresholds(train, spec)
    res = fit(train, spec, thresholds)
    real = test["piezas_scrap"] / test["piezas_producidas"]
    base_rate = train.groupby("linea")["piezas_scrap"].sum() / train.groupby("linea")["piezas_producidas"].sum()
    base_pred = test["linea"].map(base_rate).fillna(train["piezas_scrap"].sum() / train["piezas_producidas"].sum())
    pred = res.predict(_exog(res, test, spec, thresholds))
    out = {"corte": pd.Timestamp(cutoff), "corridas_prueba": len(test),
           "mae_base_pp": float((base_pred - real).abs().mean() * 100),
           "mae_modelo_pp": float((pred - real).abs().mean() * 100)}
    out["mejora_pct"] = 100 * (1 - out["mae_modelo_pp"] / out["mae_base_pp"])
    out["supera_base"] = out["mae_modelo_pp"] < out["mae_base_pp"]
    return out


def control_summary(prod, thresholds):
    rows = []
    for line in sorted(prod["linea"].unique()):
        d = m.daily(prod, line)
        if len(d) < 20:
            continue
        chart = m.p_chart(d, laney=True)
        out_days = chart.index[chart["regla_1"]]
        row = {"linea": line, "dias": len(chart), "dias_fuera_limites": len(out_days),
               "dias_con_senal": int(chart["senal"].sum()), "sigma_z": chart.attrs["sigma_z"], "tasa_media": chart["lc"].iat[0]}
        if line in thresholds and len(out_days):
            hours = prod[prod["linea"] == line].groupby("fecha")["horas_desde_mantto"].mean()
            row["fuera_sobre_umbral"] = int((hours.reindex(out_days) > thresholds[line]).sum())
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ orquestación
def diagnose(data, settings: Settings | None = None):
    settings = settings or Settings()
    cols = data["columns"]
    prod = m.with_costs(data["prod"], data["catalog"])
    claims = data["claims"]
    days = (prod["fecha"].max() - prod["fecha"].min()).days + 1
    annual = 365 / days

    with np.errstate(divide="ignore", invalid="ignore"):
        k = m.kpis(prod, claims if not claims.empty else pd.DataFrame({"costo_total_mxn": []}))
    if prod["ventas_mxn"].sum() == 0:
        k["copq_pct_ventas"] = float("nan")
    k.update({"dias": days, "desde": prod["fecha"].min(), "hasta": prod["fecha"].max(),
              "copq_anual_mxn": k["copq_mxn"] * annual, "lineas": prod["linea"].nunique()})

    paretos = {}
    if cols["defectos"] and not data["defects"].empty:
        claim_arg = claims if not claims.empty else None
        paretos["costo"] = m.pareto(data["defects"], prod, claim_arg, by="costo")
        paretos["piezas"] = m.pareto(data["defects"], prod, by="piezas")

    by_line = prod.groupby("linea").agg(piezas=("piezas_producidas", "sum"), scrap=("piezas_scrap", "sum"),
                                        costo_scrap_mxn=("costo_scrap_mxn", "sum"))
    by_line["tasa"] = by_line["scrap"] / by_line["piezas"]
    by_line["pct_costo"] = 100 * by_line["costo_scrap_mxn"] / by_line["costo_scrap_mxn"].sum()

    spec = _spec(prod, cols)
    thresholds, curves = find_thresholds(prod, spec)
    res = fit(prod, spec, thresholds)
    lever_table, not_sig = levers(res, prod, spec, thresholds, settings, annual)
    ci = res.conf_int()
    effects = pd.DataFrame({"razon_momios": np.exp(res.params), "ic95_inf": np.exp(ci[0]),
                            "ic95_sup": np.exp(ci[1]), "p_valor": res.pvalues}).drop(index="const")

    return {"kpis": k, "pareto": paretos, "por_linea": by_line.sort_values("costo_scrap_mxn", ascending=False),
            "control": control_summary(prod, thresholds), "umbrales": thresholds, "curvas_umbral": curves,
            "efectos": effects, "dispersion": float(res.scale), "palancas": lever_table, "no_significativas": not_sig,
            "validacion": validate_holdout(prod, cols), "settings": settings, "anualizacion": annual}
