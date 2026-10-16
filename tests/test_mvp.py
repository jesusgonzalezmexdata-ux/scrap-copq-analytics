"""MVP «Tus datos»: plantilla, validación de un Excel sucio, diagnóstico genérico y reporte 8D."""
import io

import pandas as pd
import pytest

from scrap_copq import diagnose as dg, intake, report as rp


def to_xlsx(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
    return buf.getvalue()


@pytest.fixture(scope="module")
def example():
    return intake.example_tables()


@pytest.fixture(scope="module")
def clean_result(example):
    data, issues = intake.validate(intake.read_workbook(intake.template_bytes(example)))
    return data, issues, dg.diagnose(data, dg.Settings(n_sims=300))


def test_template_roundtrip_has_no_issues(clean_result, example):
    data, issues, _ = clean_result
    assert issues == []
    assert data["filas_validas"] == len(example[0])
    assert all(data["columns"].values())


def test_generic_model_recovers_the_planted_levers(clean_result):
    _, _, r = clean_result
    lev = r["palancas"]
    top = lev.iloc[0]
    assert (top["tipo"], top["objetivo"]) == ("mantenimiento", "L2")
    assert 140 <= top["umbral_h"] <= 200 and 300 <= top["intervalo_actual_h"] <= 340
    assert top["ahorro_neto_p10"] > 0
    assert {"proveedor", "induccion"} <= set(lev["tipo"])
    assert "L1" not in set(lev.loc[lev["tipo"] == "mantenimiento", "objetivo"])
    assert r["validacion"]["supera_base"]
    l2 = r["control"].set_index("linea").loc["L2"]
    assert l2["fuera_sobre_umbral"] == l2["dias_fuera_limites"] > 0


def test_dirty_workbook_is_reported_by_row(example):
    prod, costs, claims = (df.copy() for df in example)
    prod = prod.rename(columns={"linea": "Línea", "piezas_producidas": "Piezas Producidas", "piezas_scrap": "Scrap",
                                "horas_desde_mantto": "Horas desde mantenimiento"})
    prod["fecha"] = prod["fecha"].dt.strftime("%d/%m/%Y")
    prod.loc[3, "turno"] = "  nocturno "
    prod.loc[5, "Scrap"] = prod.loc[5, "Piezas Producidas"] + 1
    prod.loc[7, "fecha"] = "31/02/2025"
    prod.loc[9, "producto"] = "XYZ-999"
    prod.loc[11, "Piezas Producidas"] = -5
    prod = pd.concat([prod, prod.iloc[[20]]], ignore_index=True)
    data, issues = intake.validate(intake.read_workbook(to_xlsx({"Producción": prod, "Costos": costs, "reclamos": claims})))

    errors = {i.fila: i.mensaje for i in issues if i.nivel == "error"}
    assert set(errors) == {7, 9, 11, 13}
    assert "Más scrap" in errors[7] and "Fecha no reconocida" in errors[9]
    assert "XYZ-999" in errors[11] and "número ≥ 0" in errors[13]
    notes = " ".join(i.mensaje for i in issues if i.nivel == "aviso")
    assert "duplicadas" in notes and "capitalización" in notes
    assert data["filas_validas"] == len(prod) - 5
    assert "Nocturno" in set(data["prod"]["turno"]) and "nocturno" not in set(data["prod"]["turno"])


def test_bundled_error_example_shows_validation():
    data, issues = intake.validate(intake.read_workbook(intake.example_with_errors()))
    assert sum(i.nivel == "error" for i in issues) == 4
    assert data["filas_leidas"] - data["filas_validas"] == 6


def test_fatal_problems_raise_clear_errors(example):
    prod, costs, _ = example
    with pytest.raises(intake.DataError, match="piezas_scrap"):
        intake.validate(intake.read_workbook(to_xlsx({"produccion": prod.drop(columns="piezas_scrap"), "costos": costs})))
    with pytest.raises(intake.DataError, match="costos"):
        intake.validate(intake.read_workbook(to_xlsx({"produccion": prod})))
    with pytest.raises(intake.DataError, match="Excel"):
        intake.read_workbook(b"esto no es un excel")


def test_minimal_file_runs_with_warnings(example):
    prod, costs, _ = example
    short = prod[prod["fecha"] < "2025-02-15"][intake.REQUIRED]
    data, issues = intake.validate(intake.read_workbook(to_xlsx({"produccion": short, "costos": costs[intake.COST_COLS]})))
    notes = " ".join(i.mensaje for i in issues)
    assert "exploratorios" in notes and "horas_desde_mantto" in notes
    r = dg.diagnose(data, dg.Settings(n_sims=100))
    assert r["validacion"] is None and r["pareto"] == {}
    assert r["palancas"].empty or "mantenimiento" not in set(r["palancas"]["tipo"])
    assert "costo de no calidad" in rp.report_html(r, issues, "Mínima", (len(short), data["filas_validas"]))


def test_report_is_self_contained_and_escaped(clean_result):
    data, issues, r = clean_result
    page = rp.report_html(r, issues, "<script>alert(1)</script>", (data["filas_leidas"], data["filas_validas"]))
    assert "<script>" not in page and "&lt;script&gt;" in page
    for text in ("D5 · Acción correctiva", "IATF 16949 · 8.5.1.5", "Preventivo de la línea L2", "le gana"):
        assert text in page
    assert "http" not in page
