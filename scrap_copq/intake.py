"""Entrada de datos de una planta real: plantilla de Excel y validación con mensajes en español.

python -m scrap_copq.intake plantilla_scrap.xlsx   # escribe la plantilla con datos de ejemplo
"""
from __future__ import annotations

import io
import sys
import unicodedata
from dataclasses import dataclass

import pandas as pd

from .clean import load
from .config import PROCESSED

REQUIRED = ["fecha", "linea", "turno", "producto", "piezas_producidas", "piezas_scrap"]
OPTIONAL = ["piezas_retrabajo", "horas_desde_mantto", "proveedor", "operadores_nuevos"]
COST_COLS = ["producto", "costo_material_mxn", "costo_conversion_mxn"]
COST_OPTIONAL = ["costo_retrabajo_mxn", "precio_venta_mxn"]
CLAIM_COLS = ["fecha", "linea", "defecto", "costo_total_mxn"]
DEFECT_PREFIX = "scrap_"
ALIASES = {"produccion": "piezas_producidas", "producidas": "piezas_producidas", "scrap": "piezas_scrap",
           "retrabajo": "piezas_retrabajo", "horas_mantto": "horas_desde_mantto",
           "horas_desde_mantenimiento": "horas_desde_mantto", "proveedor_material": "proveedor"}
MIN_DAYS = 90

INSTRUCTIONS = [
    ("Hoja", "Columna", "Obligatoria", "Qué poner"),
    ("produccion", "fecha", "Sí", "Día de la corrida (dd/mm/aaaa)"),
    ("produccion", "linea", "Sí", "Nombre o código de la línea"),
    ("produccion", "turno", "Sí", "Nombre del turno, siempre escrito igual"),
    ("produccion", "producto", "Sí", "Número de parte; debe existir en la hoja costos"),
    ("produccion", "piezas_producidas", "Sí", "Piezas fabricadas en la corrida, buenas y malas"),
    ("produccion", "piezas_scrap", "Sí", "Piezas desechadas en la corrida"),
    ("produccion", "piezas_retrabajo", "No", "Piezas retrabajadas"),
    ("produccion", "horas_desde_mantto", "No", "Horas de operación desde el último preventivo de la línea"),
    ("produccion", "proveedor", "No", "Proveedor del material usado en la corrida"),
    ("produccion", "operadores_nuevos", "No", "Operadores con menos de 6 meses en el puesto, en la corrida"),
    ("produccion", "scrap_<defecto>", "No", "Una columna por defecto (p. ej. scrap_Porosidad) con sus piezas"),
    ("costos", "producto", "Sí", "Número de parte"),
    ("costos", "costo_material_mxn", "Sí", "Material por pieza"),
    ("costos", "costo_conversion_mxn", "Sí", "Mano de obra y gastos de fabricación por pieza"),
    ("costos", "costo_retrabajo_mxn", "No", "Costo de retrabajar una pieza"),
    ("costos", "precio_venta_mxn", "No", "Precio de venta por pieza (para el costo de no calidad sobre ventas)"),
    ("reclamos", "fecha, linea, defecto, costo_total_mxn", "No", "Reclamos de cliente con su defecto y costo total"),
    ("", "", "", "Mínimo 3 meses de corridas; ideal 12. Los datos se procesan en tu navegador y no se envían a ningún servidor."),
]


class DataError(ValueError):
    """El archivo no se puede analizar (falta una hoja, una columna obligatoria o no hay filas válidas)."""


@dataclass
class Issue:
    nivel: str          # "error" (fila excluida) o "aviso"
    hoja: str
    fila: int | None    # fila de Excel (encabezado = 1)
    mensaje: str


def _key(text) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return "_".join(text.strip().lower().replace("-", " ").split())


def _norm(text) -> str:
    key = _key(text)
    return ALIASES.get(key, key)


def _colname(col) -> str:
    key = _norm(col)
    if key.startswith(DEFECT_PREFIX):
        return DEFECT_PREFIX + str(col).strip()[len(DEFECT_PREFIX):].strip(" _")
    return key


def _columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns=_colname)
    return out.dropna(how="all")


def read_workbook(source) -> dict[str, pd.DataFrame]:
    """Lee un .xlsx (ruta, bytes o archivo subido) y devuelve sus hojas con nombres normalizados."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    try:
        sheets = pd.read_excel(source, sheet_name=None)
    except Exception as exc:  # archivo dañado o que no es Excel
        raise DataError(f"No se pudo leer el archivo como Excel (.xlsx): {exc}") from exc
    return {_key(name): _columns(df) for name, df in sheets.items()}


def _numeric(df, col, issues, sheet, rows, allow_missing=False):
    values = pd.to_numeric(df[col], errors="coerce")
    bad = values.isna() & (~df[col].isna() if allow_missing else True)
    bad |= values < 0
    for r in df.index[bad]:
        issues.append(Issue("error", sheet, int(rows[r]), f"«{col}» debe ser un número ≥ 0 (valor: {df.at[r, col]!r})"))
    return values, bad


def _text(series):
    return series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


def validate(book: dict[str, pd.DataFrame]):
    """Convierte las hojas en las tablas del análisis. Devuelve (datos, avisos).

    Las filas con errores se excluyen y se reportan con su número de fila de Excel; los problemas
    que impiden cualquier análisis lanzan DataError."""
    issues: list[Issue] = []
    if "produccion" not in book:
        raise DataError("Falta la hoja «produccion». Usa la plantilla descargable.")
    prod = book["produccion"].copy()
    missing = [c for c in REQUIRED if c not in prod.columns]
    if missing:
        raise DataError("A la hoja «produccion» le faltan columnas obligatorias: " + ", ".join(missing))
    rows = pd.Series(prod.index + 2, index=prod.index)
    bad = pd.Series(False, index=prod.index)

    fecha = pd.to_datetime(prod["fecha"], errors="coerce", dayfirst=True)
    for r in prod.index[fecha.isna()]:
        issues.append(Issue("error", "produccion", int(rows[r]), f"Fecha no reconocida: {prod.at[r, 'fecha']!r}"))
    bad |= fecha.isna()
    prod["fecha"] = fecha.dt.normalize()

    for col in ("linea", "turno", "producto"):
        raw = _text(prod[col])
        empty = raw.isna() | (raw == "")
        for r in prod.index[empty]:
            issues.append(Issue("error", "produccion", int(rows[r]), f"«{col}» está vacío"))
        bad |= empty
        prod[col] = raw
    titled = prod["turno"].str.title()
    changed = int((titled != prod["turno"]).fillna(False).sum())
    if changed:
        issues.append(Issue("aviso", "produccion", None, f"{changed} turnos escritos con otra capitalización se unificaron"))
    prod["turno"] = titled

    for col in ("piezas_producidas", "piezas_scrap"):
        prod[col], b = _numeric(prod, col, issues, "produccion", rows)
        bad |= b
    over = prod["piezas_scrap"] > prod["piezas_producidas"]
    for r in prod.index[over & ~bad]:
        issues.append(Issue("error", "produccion", int(rows[r]),
                            f"Más scrap ({prod.at[r, 'piezas_scrap']:.0f}) que producción ({prod.at[r, 'piezas_producidas']:.0f})"))
    zero = prod["piezas_producidas"] == 0
    for r in prod.index[zero & ~bad]:
        issues.append(Issue("error", "produccion", int(rows[r]), "Corrida sin producción"))
    bad |= over | zero

    present = [c for c in OPTIONAL if c in prod.columns]
    for col in OPTIONAL:
        if col not in prod.columns:
            issues.append(Issue("aviso", "produccion", None, f"Sin columna «{col}»: el análisis que depende de ella se omite"))
    for col in ("piezas_retrabajo", "horas_desde_mantto", "operadores_nuevos"):
        if col in present:
            prod[col], b = _numeric(prod, col, issues, "produccion", rows, allow_missing=True)
            bad |= b
    if "piezas_retrabajo" in present:
        prod["piezas_retrabajo"] = prod["piezas_retrabajo"].fillna(0)
    else:
        prod["piezas_retrabajo"] = 0.0
    if "operadores_nuevos" in present:
        prod["operadores_nuevos"] = prod["operadores_nuevos"].fillna(0)
    if "proveedor" in present:
        prod["proveedor"] = _text(prod["proveedor"])

    defect_cols = [c for c in prod.columns if c.startswith(DEFECT_PREFIX)]
    for col in defect_cols:
        prod[col], b = _numeric(prod, col, issues, "produccion", rows, allow_missing=True)
        bad |= b
        prod[col] = prod[col].fillna(0)

    # Costos
    if "costos" not in book:
        raise DataError("Falta la hoja «costos» con el costo por producto.")
    cost = book["costos"].copy()
    missing = [c for c in COST_COLS if c not in cost.columns]
    if missing:
        raise DataError("A la hoja «costos» le faltan columnas obligatorias: " + ", ".join(missing))
    cost["producto"] = _text(cost["producto"])
    crows = pd.Series(cost.index + 2, index=cost.index)
    cbad = pd.Series(False, index=cost.index)
    for col in COST_COLS[1:] + [c for c in COST_OPTIONAL if c in cost.columns]:
        cost[col], b = _numeric(cost, col, issues, "costos", crows, allow_missing=col in COST_OPTIONAL)
        cbad |= b
    cost = cost[~cbad]
    for col in COST_OPTIONAL:
        cost[col] = cost[col].fillna(0) if col in cost.columns else 0.0
    dup = cost["producto"].duplicated(keep="first")
    if dup.any():
        issues.append(Issue("aviso", "costos", None, f"{int(dup.sum())} productos repetidos; se usa la primera fila de cada uno"))
    cost = cost[~dup]
    unknown = ~prod["producto"].isin(cost["producto"])
    for r in prod.index[unknown & ~bad]:
        issues.append(Issue("error", "produccion", int(rows[r]), f"El producto «{prod.at[r, 'producto']}» no está en la hoja costos"))
    bad |= unknown

    keys = ["fecha", "linea", "turno", "producto"]
    dups = prod.duplicated(keys + ["piezas_producidas", "piezas_scrap"], keep="first") & ~bad
    if dups.any():
        issues.append(Issue("aviso", "produccion", None,
                            f"{int(dups.sum())} filas duplicadas eliminadas (filas {', '.join(map(str, rows[dups].head(10)))}"
                            + ("…" if dups.sum() > 10 else "") + ")"))
    bad |= dups

    clean = prod[~bad].copy()
    if clean.empty:
        raise DataError("Ninguna fila de «produccion» es válida. Revisa los errores por fila.")
    clean["run_id"] = "F" + rows[~bad].astype(str)
    for col in ("linea", "turno", "producto") + (("proveedor",) if "proveedor" in present else ()):
        clean[col] = clean[col].astype(object).where(clean[col].notna(), None)

    if defect_cols:
        total = clean[defect_cols].sum(axis=1)
        mismatch = (total > 0) & (total.round() != clean["piezas_scrap"].round())
        if mismatch.any():
            issues.append(Issue("aviso", "produccion", None,
                                f"En {int(mismatch.sum())} corridas la suma de columnas scrap_ no coincide con piezas_scrap; "
                                "el Pareto usa las columnas por defecto"))
        defects = clean.melt(id_vars="run_id", value_vars=defect_cols, var_name="defecto", value_name="piezas")
        defects["defecto"] = defects["defecto"].str[len(DEFECT_PREFIX):]
        defects = defects[defects["piezas"] > 0].reset_index(drop=True)
    else:
        issues.append(Issue("aviso", "produccion", None, "Sin columnas scrap_<defecto>: no hay Pareto por defecto"))
        defects = pd.DataFrame(columns=["run_id", "defecto", "piezas"])

    if "horas_desde_mantto" in clean.columns:
        none = clean.groupby("linea")["horas_desde_mantto"].apply(lambda s: s.notna().mean() < 0.8)
        for line in none[none].index:
            issues.append(Issue("aviso", "produccion", None,
                                f"La línea {line} tiene menos de 80 % de corridas con horas desde mantenimiento; no se modela su desgaste"))

    days = (clean["fecha"].max() - clean["fecha"].min()).days + 1
    if days < MIN_DAYS:
        issues.append(Issue("aviso", "produccion", None,
                            f"Solo {days} días de datos; con menos de {MIN_DAYS} los resultados son exploratorios"))

    claims = pd.DataFrame(columns=CLAIM_COLS)
    if "reclamos" in book and not book["reclamos"].empty:
        c = book["reclamos"].copy()
        missing = [col for col in CLAIM_COLS if col not in c.columns]
        if missing:
            issues.append(Issue("aviso", "reclamos", None, "Hoja reclamos ignorada; faltan columnas: " + ", ".join(missing)))
        else:
            c["fecha"] = pd.to_datetime(c["fecha"], errors="coerce", dayfirst=True)
            c["costo_total_mxn"] = pd.to_numeric(c["costo_total_mxn"], errors="coerce")
            ok = c["fecha"].notna() & c["costo_total_mxn"].notna()
            if (~ok).any():
                issues.append(Issue("aviso", "reclamos", None, f"{int((~ok).sum())} reclamos sin fecha o costo válidos ignorados"))
            c = c[ok]
            for col in ("linea", "defecto"):
                c[col] = _text(c[col])
            claims = c.reset_index(drop=True)

    catalog = cost.reset_index(drop=True)
    data = {"prod": clean.reset_index(drop=True), "defects": defects, "catalog": catalog, "claims": claims,
            "columns": {"retrabajo": "piezas_retrabajo" in present,
                        "horas": "horas_desde_mantto" in present,
                        "proveedor": "proveedor" in present,
                        "operadores": "operadores_nuevos" in present,
                        "defectos": bool(defect_cols)},
            "filas_leidas": len(prod), "filas_validas": int((~bad).sum())}
    return data, issues


def issues_frame(issues: list[Issue]) -> pd.DataFrame:
    return pd.DataFrame([vars(i) for i in issues], columns=["nivel", "hoja", "fila", "mensaje"])


def example_tables():
    """Tablas de la planta sintética en el formato de la plantilla."""
    t = load(PROCESSED)
    prod = t["produccion_turnos"].rename(columns={"proveedor_material": "proveedor"})
    wide = t["scrap_por_defecto"].pivot_table(index="run_id", columns="defecto", values="piezas", aggfunc="sum", fill_value=0)
    wide.columns = [DEFECT_PREFIX + c for c in wide.columns]
    prod = prod.merge(wide, left_on="run_id", right_index=True, how="left").fillna({c: 0 for c in wide.columns})
    produccion = prod[REQUIRED + OPTIONAL + list(wide.columns)]
    costos = t["catalogo_productos"][["producto"] + COST_COLS[1:] + COST_OPTIONAL]
    reclamos = t["reclamos_cliente"][["fecha", "linea", "producto", "defecto", "costo_total_mxn"]]
    return produccion, costos, reclamos


def template_bytes(tables=None) -> bytes:
    """Plantilla .xlsx con instrucciones y, por omisión, el año de la planta sintética como ejemplo."""
    produccion, costos, reclamos = tables or example_tables()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl", date_format="DD/MM/YYYY", datetime_format="DD/MM/YYYY") as xw:
        pd.DataFrame(INSTRUCTIONS[1:], columns=INSTRUCTIONS[0]).to_excel(xw, sheet_name="instrucciones", index=False)
        produccion.to_excel(xw, sheet_name="produccion", index=False)
        costos.to_excel(xw, sheet_name="costos", index=False)
        reclamos.to_excel(xw, sheet_name="reclamos", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in list(col)[:50])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 70)
    return buf.getvalue()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "plantilla_scrap.xlsx"
    with open(out, "wb") as fh:
        fh.write(template_bytes())
    print(f"Plantilla escrita en {out}")
