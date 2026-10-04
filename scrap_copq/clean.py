"""Limpieza y validación de la exportación del MES: python -m scrap_copq.clean"""
import json

import pandas as pd

from .config import PROCESSED, RAW, SHIFTS

TABLES = ["produccion_turnos", "scrap_por_defecto", "reclamos_cliente", "mantenimientos",
          "altas_operadores", "catalogo_productos"]
DATES = {"produccion_turnos", "reclamos_cliente", "mantenimientos", "altas_operadores"}


def load(folder=RAW):
    return {t: pd.read_csv(folder / f"{t}.csv", parse_dates=["fecha"] if t in DATES else None)
            for t in TABLES}


def clean(raw):
    prod, defects = raw["produccion_turnos"].copy(), raw["scrap_por_defecto"]
    log = {"filas_originales": len(prod)}

    turno = prod["turno"].str.strip().str.title()
    log["turnos_normalizados"] = int((turno != prod["turno"]).sum())
    prod["turno"] = turno
    unknown = set(prod["turno"]) - set(SHIFTS)
    if unknown:
        raise ValueError(f"Turnos no reconocidos: {unknown}")

    log["duplicados_eliminados"] = int(prod.duplicated("run_id").sum())
    prod = prod.drop_duplicates("run_id")

    by_defect = defects.groupby("run_id")["piezas"].sum()
    defect_total = prod["run_id"].map(by_defect).fillna(0)
    invalid = (prod["piezas_scrap"] > prod["piezas_producidas"]) | (prod["piezas_scrap"] != defect_total)
    log["corridas_invalidas_excluidas"] = prod.loc[invalid, "run_id"].tolist()
    prod = prod[~invalid]

    # La humedad es del ambiente de planta: se toma la lectura del mismo turno en otra línea.
    missing = prod["humedad_rel_pct"].isna()
    log["humedad_imputada"] = int(missing.sum())
    same_shift = prod.groupby(["fecha", "turno"])["humedad_rel_pct"].transform("median")
    prod["humedad_rel_pct"] = prod["humedad_rel_pct"].fillna(same_shift)
    if prod["humedad_rel_pct"].isna().any():
        raise ValueError("Quedan lecturas de humedad sin imputar")

    out = dict(raw)
    out["produccion_turnos"] = prod.reset_index(drop=True)
    out["scrap_por_defecto"] = defects[defects["run_id"].isin(prod["run_id"])].reset_index(drop=True)
    log["filas_limpias"] = len(prod)
    return out, log


def main():
    tables, log = clean(load())
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(PROCESSED / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    (PROCESSED / "reporte_calidad_datos.json").write_text(json.dumps(log, indent=2, ensure_ascii=False))
    print(json.dumps(log, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
