"""Genera los datos sintéticos de la planta: python -m scrap_copq.generate

Los patrones (desgaste entre mantenimientos, operadores nuevos, lotes del
proveedor C, humedad, cambios de modelo y una falla de fixture en agosto)
están sembrados a propósito; el análisis debe redescubrirlos con los datos.
"""
import numpy as np
import pandas as pd

from .config import (DEFECTS, HOLIDAYS, HUMIDITY_BY_MONTH, LINES, NEW_OPERATOR_MONTHS,
                     PRODUCTS, RAW, SEED, SHIFT_HOURS, SHIFTS, YEAR)

MAINT_THRESHOLD_H = 160
CREW_SIZE = 4
TENURE_EFFECT = {"L1": 0.10, "L2": 0.12, "L3": 0.28}  # por cada operador nuevo en la cuadrilla
TURNOVER_DAYS = {True: (150, 450), False: (300, 1000)}  # días entre relevos: nocturno vs. diurnos
MAINT_EFFECT = {"Porosidad": 0.012, "Perforación": 0.010, "Dimensional": 0.004}
SUPPLIER_C_EFFECT = {"Grieta": 1.4, "Dimensional": 0.25}
FIXTURE_FAILURE = ("L2", pd.Timestamp("2025-08-12"), pd.Timestamp("2025-08-15"))


def _logit(p):
    return np.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + np.exp(-x))


def production_days(year=YEAR):
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    return days[(days.dayofweek < 6) & ~days.isin(pd.to_datetime(HOLIDAYS))]


def _ambient_humidity(days, rng):
    rh = {}
    for d in days:
        base = HUMIDITY_BY_MONTH[d.month] + rng.normal(0, 5)
        for shift, bump in zip(SHIFTS, (-3, 0, 7)):
            rh[(d, shift)] = float(np.clip(base + bump + rng.normal(0, 2), 25, 98))
    return rh


def _simulate_line(line, cfg, days, rh, rng):
    runs, defects, pms, hires = [], [], [], []
    base = {d: _logit(cfg["scrap_base"] * s) for d, s in DEFECTS[cfg["proceso"]].items()}
    suppliers, sup_p = list(cfg["proveedores"]), list(cfg["proveedores"].values())
    hours = rng.uniform(0, cfg["intervalo_pm_h"])
    next_pm = cfg["intervalo_pm_h"] * rng.uniform(0.92, 1.08)
    product = cfg["productos"][0]
    tenure = {s: rng.uniform(0.5, 18, CREW_SIZE) if s == "Nocturno" else rng.uniform(1, 72, CREW_SIZE)
              for s in SHIFTS}
    next_change = {s: rng.uniform(*TURNOVER_DAYS[s == "Nocturno"], CREW_SIZE) for s in SHIFTS}
    prev_day = days[0]
    for day in days:
        supplier = rng.choice(suppliers, p=sup_p)
        elapsed = (day - days[0]).days
        for s in SHIFTS:
            tenure[s] += (day - prev_day).days / 30.4
            for i in np.flatnonzero(elapsed >= next_change[s]):  # rotación: entra un operador nuevo
                tenure[s][i] = rng.uniform(0, 1.5)
                next_change[s][i] = elapsed + rng.uniform(*TURNOVER_DAYS[s == "Nocturno"])
                hires.append({"fecha": day, "linea": line, "turno": s})
        prev_day = day
        for s in SHIFTS:
            if hours >= next_pm:
                pms.append({"fecha": day, "linea": line, "turno": s,
                            "horas_acumuladas": round(hours, 1)})
                hours, next_pm = 0.0, cfg["intervalo_pm_h"] * rng.uniform(0.92, 1.08)
            changeover = rng.random() < 0.15
            if changeover:
                product = next(p for p in cfg["productos"] if p != product)
            special = line == FIXTURE_FAILURE[0] and FIXTURE_FAILURE[1] <= day <= FIXTURE_FAILURE[2]
            downtime = rng.gamma(1.5, 12) + (rng.uniform(40, 90) if special else 0)
            n = int(rng.integers(*cfg["piezas_turno"]) * (1 - downtime / (SHIFT_HOURS * 60)))
            new_ops = int((tenure[s] < NEW_OPERATOR_MONTHS).sum())
            noise = rng.normal(0, 0.15)
            common = noise + 0.12 * (s == "Nocturno") + TENURE_EFFECT[line] * new_ops
            counts = {}
            for name, b in base.items():
                eta = b + common
                if name == "Dimensional":
                    eta += 0.6 * changeover + 1.7 * special
                if line == "L2":
                    eta += MAINT_EFFECT.get(name, 0) * max(0.0, hours - MAINT_THRESHOLD_H)
                if name == "Porosidad" and cfg["proceso"].startswith("Soldadura"):
                    eta += 0.30 * (rh[(day, s)] - 55) / 10
                if supplier == "C":
                    eta += SUPPLIER_C_EFFECT.get(name, 0)
                counts[name] = int(rng.binomial(n, _expit(eta)))
            scrap = sum(counts.values())
            rework = int(rng.binomial(n - scrap, cfg["retrabajo_base"] * np.exp(0.5 * noise + 0.15 * new_ops)))
            key = len(runs)
            runs.append({"key": (line, key), "fecha": day, "linea": line, "proceso": cfg["proceso"],
                         "turno": s, "producto": product, "piezas_producidas": n,
                         "piezas_scrap": scrap, "piezas_retrabajo": rework,
                         "horas_desde_mantto": round(hours, 1), "cambio_modelo": int(changeover),
                         "proveedor_material": supplier,
                         "operadores_nuevos": new_ops,
                         "humedad_rel_pct": round(rh[(day, s)], 1), "paro_min": round(downtime)})
            defects += [{"key": (line, key), "defecto": k, "piezas": v} for k, v in counts.items() if v]
            hours += SHIFT_HOURS - downtime / 60
    return runs, defects, pms, hires


def _claims(runs, defects, rng):
    """Reclamos del cliente: escapes de falta de fusión (soldadura) y grietas de lotes C."""
    df = defects.merge(runs[["run_id", "fecha", "producto", "linea", "proveedor_material"]], on="run_id")
    df["semana"] = df["fecha"].dt.to_period("W").dt.start_time
    fdf = df[df["defecto"] == "Falta de fusión"].assign(lam=lambda x: x["piezas"] * 0.0015)
    grieta = df[(df["defecto"] == "Grieta") & (df["proveedor_material"] == "C")].assign(
        lam=lambda x: x["piezas"] * 0.0003)
    weekly = (pd.concat([fdf, grieta]).groupby(["semana", "producto", "linea", "defecto"],
                                                as_index=False)["lam"].sum())
    weekly = weekly[rng.poisson(weekly["lam"].to_numpy()) > 0]
    rows = []
    for _, w in weekly.iterrows():
        pieces = int(rng.integers(800, 3500))
        rows.append({"fecha": min(w["semana"] + pd.Timedelta(days=int(rng.integers(7, 21))),
                                  pd.Timestamp(f"{YEAR}-12-31")),
                     "producto": w["producto"], "linea": w["linea"], "defecto": w["defecto"],
                     "piezas_afectadas": pieces, "costo_seleccion_mxn": round(pieces * 6.5),
                     "costo_flete_mxn": int(rng.integers(12, 26)) * 1000,
                     "penalizacion_mxn": int(rng.integers(40, 150)) * 1000})
    claims = pd.DataFrame(rows).sort_values("fecha", ignore_index=True)
    claims["costo_total_mxn"] = claims[["costo_seleccion_mxn", "costo_flete_mxn",
                                        "penalizacion_mxn"]].sum(axis=1)
    claims.insert(0, "reclamo_id", [f"RC-{i:03d}" for i in range(1, len(claims) + 1)])
    return claims


def _inject_issues(runs, rng):
    """Problemas típicos de una exportación del MES, para el paso de limpieza."""
    runs = runs.copy()
    runs.loc[rng.choice(runs.index, int(len(runs) * 0.006), replace=False), "humedad_rel_pct"] = np.nan
    night = runs.index[runs["turno"] == "Nocturno"]
    runs.loc[rng.choice(night, 12, replace=False), "turno"] = "NOCTURNO"
    evening = runs.index[runs["turno"] == "Vespertino"]
    runs.loc[rng.choice(evening, 6, replace=False), "turno"] = " Vespertino "
    welding = runs.index[(runs["linea"] != "L1") & (runs["piezas_scrap"] > runs["piezas_producidas"] // 100)]
    typo = rng.choice(welding, 3, replace=False)
    runs.loc[typo, "piezas_producidas"] = runs.loc[typo, "piezas_producidas"] // 100
    dup = runs.loc[rng.choice(runs.index, 6, replace=False)]
    return pd.concat([runs, dup]).sort_values(["fecha", "run_id"], kind="stable", ignore_index=True)


def generate(seed=SEED):
    rng = np.random.default_rng(seed)
    days = production_days()
    rh = _ambient_humidity(days, rng)
    runs, defects, pms, hires = [], [], [], []
    for line, cfg in LINES.items():
        r, d, p, h = _simulate_line(line, cfg, days, rh, rng)
        runs += r
        defects += d
        pms += p
        hires += h
    runs = pd.DataFrame(runs)
    runs["orden_turno"] = runs["turno"].map({s: i for i, s in enumerate(SHIFTS)})
    runs = runs.sort_values(["fecha", "orden_turno", "linea"], ignore_index=True)
    runs.insert(0, "run_id", [f"R{i:05d}" for i in range(1, len(runs) + 1)])
    id_map = dict(zip(runs["key"], runs["run_id"]))
    defects = pd.DataFrame(defects)
    defects.insert(0, "run_id", defects.pop("key").map(id_map))
    defects = defects.sort_values(["run_id", "defecto"], ignore_index=True)
    runs = runs.drop(columns=["key", "orden_turno"])
    claims = _claims(runs, defects, rng)
    catalog = pd.DataFrame(
        [{"producto": k, "descripcion": v[0], "linea": ln, "costo_material_mxn": v[1],
          "costo_conversion_mxn": v[2], "costo_retrabajo_mxn": v[3], "precio_venta_mxn": v[4]}
         for ln, cfg in LINES.items() for k, v in PRODUCTS.items() if k in cfg["productos"]])
    return {"produccion_turnos": _inject_issues(runs, rng), "scrap_por_defecto": defects,
            "reclamos_cliente": claims, "mantenimientos": pd.DataFrame(pms),
            "altas_operadores": pd.DataFrame(hires),
            "catalogo_productos": catalog}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name, df in generate().items():
        df.to_csv(RAW / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        print(f"{name:20s} {len(df):>6,d} filas")


if __name__ == "__main__":
    main()
