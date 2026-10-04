"""Indicadores de calidad: costo de no calidad (COPQ), Pareto y cartas de control p / p' de Laney."""
import numpy as np
import pandas as pd


def with_costs(prod, catalog):
    """Agrega costos por corrida. El scrap pierde material + conversión; lo bueno se vende."""
    c = catalog.set_index("producto")
    unit_scrap = prod["producto"].map(c["costo_material_mxn"] + c["costo_conversion_mxn"])
    return prod.assign(
        costo_unitario_scrap_mxn=unit_scrap,
        costo_scrap_mxn=prod["piezas_scrap"] * unit_scrap,
        costo_retrabajo_mxn=prod["piezas_retrabajo"] * prod["producto"].map(c["costo_retrabajo_mxn"]),
        ventas_mxn=(prod["piezas_producidas"] - prod["piezas_scrap"]) * prod["producto"].map(c["precio_venta_mxn"]),
    )


def kpis(prod, claims):
    """prod debe venir de with_costs()."""
    produced, scrap = prod["piezas_producidas"].sum(), prod["piezas_scrap"].sum()
    parts = {"costo_scrap_mxn": prod["costo_scrap_mxn"].sum(),
             "costo_retrabajo_mxn": prod["costo_retrabajo_mxn"].sum(),
             "costo_reclamos_mxn": claims["costo_total_mxn"].sum()}
    copq = sum(parts.values())
    return {"piezas_producidas": int(produced), "piezas_scrap": int(scrap), "tasa_scrap": scrap / produced,
            **parts, "copq_mxn": copq, "copq_pct_ventas": copq / prod["ventas_mxn"].sum(),
            "copq_por_pieza_buena_mxn": copq / (produced - scrap), "reclamos": len(claims)}


def copq_by_month(prod, claims):
    month = prod["fecha"].dt.to_period("M")
    out = prod.groupby(month)[["costo_scrap_mxn", "costo_retrabajo_mxn"]].sum()
    out["costo_reclamos_mxn"] = claims.groupby(claims["fecha"].dt.to_period("M"))["costo_total_mxn"].sum()
    out = out.fillna(0)
    out["copq_mxn"] = out.sum(axis=1)
    out.index = out.index.to_timestamp()
    out.index.name = "mes"
    return out


def pareto(defects, prod, claims=None, by="piezas"):
    """Pareto de defectos por piezas o por costo (scrap + reclamos atribuidos al defecto)."""
    d = defects.merge(prod[["run_id", "costo_unitario_scrap_mxn"]], on="run_id")
    if by == "costo":
        values = (d["piezas"] * d["costo_unitario_scrap_mxn"]).groupby(d["defecto"]).sum()
        if claims is not None:
            values = values.add(claims.groupby("defecto")["costo_total_mxn"].sum(), fill_value=0)
    elif by == "piezas":
        values = d.groupby("defecto")["piezas"].sum()
    else:
        raise ValueError("by debe ser 'piezas' o 'costo'")
    out = values.sort_values(ascending=False).rename("valor").rename_axis("defecto").reset_index()
    out["pct"] = 100 * out["valor"] / out["valor"].sum()
    out["pct_acum"] = out["pct"].cumsum()
    out["pocos_vitales"] = (out["pct_acum"] - out["pct"]) < 80
    return out


def daily(prod, line=None):
    df = prod if line is None else prod[prod["linea"] == line]
    out = df.groupby("fecha").agg(n=("piezas_producidas", "sum"), x=("piezas_scrap", "sum"))
    out["p"] = out["x"] / out["n"]
    return out


def scrap_rate(prod, by):
    g = prod.groupby(by)[["piezas_scrap", "piezas_producidas"]].sum()
    return g["piezas_scrap"] / g["piezas_producidas"]


def rate_by_maintenance_hours(prod, width=20):
    """Tasa de scrap por línea y tramo de horas desde el último mantenimiento preventivo."""
    tramo = (prod["horas_desde_mantto"] // width) * width + width / 2
    out = prod.groupby(["linea", tramo]).agg(x=("piezas_scrap", "sum"), n=("piezas_producidas", "sum"),
                                             corridas=("run_id", "size"))
    out["tasa"] = out["x"] / out["n"]
    return out.reset_index().rename(columns={"horas_desde_mantto": "horas"})


def western_electric(z):
    """Reglas de Western Electric sobre la serie estandarizada z (marca el punto que completa la regla)."""
    z = pd.Series(z, dtype=float)

    def k_of_n(limit, k, n):
        hit = pd.Series(False, index=z.index)
        for sign in (1, -1):
            hit |= ((sign * z) > limit).astype(int).rolling(n).sum() >= k
        return hit

    rules = pd.DataFrame({
        "regla_1": z.abs() > 3,                                     # 1 punto fuera de 3σ
        "regla_2": k_of_n(2, 2, 3),                                 # 2 de 3 más allá de 2σ
        "regla_3": k_of_n(1, 4, 5),                                 # 4 de 5 más allá de 1σ
        "regla_4": np.sign(z).rolling(8).sum().abs() == 8,          # 8 seguidos del mismo lado
    })
    rules["senal"] = rules.any(axis=1)
    return rules


def p_chart(daily_df, laney=False):
    """Carta p con límites variables por tamaño de subgrupo; con laney=True, carta p' (Laney, 2002),
    que corrige la sobredispersión típica de subgrupos grandes."""
    pbar = daily_df["x"].sum() / daily_df["n"].sum()
    sigma = np.sqrt(pbar * (1 - pbar) / daily_df["n"])
    z = (daily_df["p"] - pbar) / sigma
    sigma_z = z.diff().abs().mean() / 1.128 if laney else 1.0
    out = daily_df.assign(lc=pbar, sigma=sigma * sigma_z, z=z / sigma_z)
    out["lsc"] = pbar + 3 * out["sigma"]
    out["lic"] = (pbar - 3 * out["sigma"]).clip(lower=0)
    out = out.join(western_electric(out["z"]))
    out.attrs["sigma_z"] = float(sigma_z)
    return out
