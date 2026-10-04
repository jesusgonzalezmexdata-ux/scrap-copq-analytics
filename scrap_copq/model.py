"""Modelo explicativo del scrap (GLM binomial) y simulación de ahorro por palanca."""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import PM_COST_MXN, SHIFT_HOURS, SUPPLIER_C_DISCOUNT, TRAINING_COST_MXN

LABELS = {
    "const": "Intercepto (L1)", "L2": "Línea L2", "L3": "Línea L3",
    "nocturno": "Turno nocturno", "cambio_modelo": "Cambio de modelo",
    "nuevos_L1": "Operador nuevo · L1", "nuevos_L2": "Operador nuevo · L2",
    "nuevos_L3": "Operador nuevo · L3", "exceso_mantto_L2": "+10 h sobre umbral de mantto · L2",
    "proveedor_C": "Lote del proveedor C · L1", "humedad_soldadura": "+10 pts de humedad · soldadura",
}
LEVERS = {
    "mantenimiento": "Mantenimiento preventivo de L2 en el umbral",
    "induccion": "Inducción por competencias a operadores nuevos",
    "proveedor": "Reasignar los lotes del proveedor C al A",
}


def design(prod, threshold=160):
    """Matriz de diseño; cada variable responde a una hipótesis del análisis exploratorio."""
    line = prod["linea"]
    X = pd.DataFrame({
        "const": 1.0,
        "L2": (line == "L2").astype(float),
        "L3": (line == "L3").astype(float),
        "nocturno": (prod["turno"] == "Nocturno").astype(float),
        "cambio_modelo": prod["cambio_modelo"].astype(float),
        **{f"nuevos_{ln}": prod["operadores_nuevos"] * (line == ln) for ln in ("L1", "L2", "L3")},
        "exceso_mantto_L2": (prod["horas_desde_mantto"] - threshold).clip(lower=0) / 10 * (line == "L2"),
        "proveedor_C": ((prod["proveedor_material"] == "C") & (line == "L1")).astype(float),
        "humedad_soldadura": (prod["humedad_rel_pct"] - 55) / 10 * (line != "L1"),
    }, index=prod.index)
    return X.astype(float)


def fit(prod, threshold=160):
    """Cuasi-binomial (escala = chi² de Pearson / gl) para no subestimar los errores estándar
    con sobredispersión. Se omiten variables sin variación en la muestra de entrenamiento."""
    X = design(prod, threshold)
    X = X.loc[:, X.ne(0).any()]
    n = prod["piezas_producidas"]
    return sm.GLM(prod["piezas_scrap"] / n, X, family=sm.families.Binomial(),
                  var_weights=n).fit(scale="X2")


def _exog(res, prod, threshold):
    return design(prod, threshold)[res.model.exog_names]


def find_threshold(prod, grid=range(80, 241, 10)):
    """Umbral de horas desde mantenimiento que minimiza la devianza."""
    dev = pd.Series({t: fit(prod, t).deviance for t in grid}, name="devianza")
    return int(dev.idxmin()), dev


def odds_ratios(res):
    ci = res.conf_int()
    out = pd.DataFrame({"odds_ratio": np.exp(res.params), "ic95_inf": np.exp(ci[0]),
                        "ic95_sup": np.exp(ci[1]), "p_valor": res.pvalues})
    out.index = [LABELS.get(i, i) for i in out.index]
    return out.drop(index=LABELS["const"])


def predict_rate(res, prod, threshold=160):
    return pd.Series(res.predict(_exog(res, prod, threshold)), index=prod.index)


def holdout(prod, cutoff="2025-10-01", threshold=160):
    """Entrena con ene–sep y evalúa oct–dic contra un modelo base (promedio por línea)."""
    train, test = prod[prod["fecha"] < cutoff], prod[prod["fecha"] >= cutoff]
    res = fit(train, threshold)
    real = test["piezas_scrap"] / test["piezas_producidas"]
    base_rate = train.groupby("linea")["piezas_scrap"].sum() / train.groupby("linea")["piezas_producidas"].sum()
    mae = {"Modelo base (promedio por línea)": (test["linea"].map(base_rate) - real).abs().mean(),
           "GLM binomial": (predict_rate(res, test, threshold) - real).abs().mean()}
    return pd.Series(mae, name="error_absoluto_medio_pp") * 100


def l2_hours(prod, interval):
    """Horas desde el mantenimiento si el preventivo de L2 se hiciera cada `interval` horas de operación."""
    order = prod.loc[prod["linea"] == "L2", "run_id"].sort_values().index
    op = SHIFT_HOURS - prod.loc[order, "paro_min"] / 60
    hours = prod["horas_desde_mantto"].copy()
    hours.loc[order] = (op.cumsum() - op) % interval
    return hours


def _scenario(res, prod, lever, threshold, interval, gap_closed):
    if lever == "mantenimiento":
        return _exog(res, prod.assign(horas_desde_mantto=l2_hours(prod, interval)), threshold)
    X = _exog(res, prod, threshold)
    if lever == "induccion":
        cols = X.columns.intersection(["nuevos_L1", "nuevos_L2", "nuevos_L3"])
        X[cols] *= 1 - gap_closed
    elif lever == "proveedor":
        X["proveedor_C"] = 0.0
    else:
        raise ValueError(lever)
    return X


def lever_cost(lever, prod, catalog, hires, maint, interval):
    """Costo anual de implementar cada palanca (supuestos en config.py)."""
    if lever == "mantenimiento":
        hours = (SHIFT_HOURS - prod.loc[prod["linea"] == "L2", "paro_min"] / 60).sum()
        return (hours / interval - (maint["linea"] == "L2").sum()) * PM_COST_MXN
    if lever == "induccion":
        return len(hires) * TRAINING_COST_MXN
    if lever == "proveedor":
        material = prod["producto"].map(catalog.set_index("producto")["costo_material_mxn"])
        c_lots = (prod["proveedor_material"] == "C") & (prod["linea"] == "L1")
        return float((prod.loc[c_lots, "piezas_producidas"] * material[c_lots]).sum() * SUPPLIER_C_DISCOUNT)
    raise ValueError(lever)


def _expected_scrap(X, betas, n):
    return n * (1 / (1 + np.exp(-(X.to_numpy() @ np.atleast_2d(betas).T)))).T


def simulate_savings(res, prod, catalog, hires, maint, claims, threshold, interval=None, gap_closed=0.5,
                     levers=("mantenimiento", "induccion", "proveedor"), n_sims=2000, seed=7):
    """Ahorro anual por palanca con incertidumbre paramétrica (β ~ Normal(β̂, Σ̂)).
    El mantenimiento se simula recalculando el ciclo de horas de L2 con el nuevo intervalo
    (por omisión, el umbral). A la palanca de proveedor se suman los reclamos por grieta,
    trazados a lotes del proveedor C."""
    interval = interval or threshold
    betas = np.random.default_rng(seed).multivariate_normal(res.params, res.cov_params(), n_sims)
    n = prod["piezas_producidas"].to_numpy()
    unit_cost = prod["costo_unitario_scrap_mxn"].to_numpy()
    base = _expected_scrap(_exog(res, prod, threshold), betas, n)
    traced = {"proveedor": claims.loc[claims["defecto"] == "Grieta", "costo_total_mxn"].sum()}
    rows = []
    for lever in levers:
        alt = _expected_scrap(_scenario(res, prod, lever, threshold, interval, gap_closed), betas, n)
        gross = ((base - alt) * unit_cost).sum(axis=1) + traced.get(lever, 0)
        cost = lever_cost(lever, prod, catalog, hires, maint, interval)
        p10, p50, p90 = np.percentile(gross, [10, 50, 90])
        rows.append({"palanca": lever, "piezas_evitadas": float(np.median((base - alt).sum(axis=1))),
                     "ahorro_bruto_p50": p50, "ahorro_bruto_p10": p10, "ahorro_bruto_p90": p90,
                     "costo_anual": cost, "ahorro_neto_p50": p50 - cost,
                     "ahorro_neto_p10": p10 - cost, "ahorro_neto_p90": p90 - cost})
    return pd.DataFrame(rows).set_index("palanca")


def maintenance_curve(res, prod, catalog, maint, threshold, intervals=range(100, 341, 10)):
    """Ahorro neto (estimación puntual) según el intervalo de mantenimiento preventivo de L2."""
    n = prod["piezas_producidas"].to_numpy()
    unit_cost = prod["costo_unitario_scrap_mxn"].to_numpy()
    base = _expected_scrap(_exog(res, prod, threshold), res.params, n)
    rows = []
    for interval in intervals:
        alt = _expected_scrap(_scenario(res, prod, "mantenimiento", threshold, interval, 0), res.params, n)
        gross = float(((base - alt) * unit_cost).sum())
        cost = lever_cost("mantenimiento", prod, catalog, None, maint, interval)
        rows.append({"intervalo_h": interval, "ahorro_bruto": gross, "costo_anual": cost,
                     "ahorro_neto": gross - cost})
    return pd.DataFrame(rows).set_index("intervalo_h")
