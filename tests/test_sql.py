"""Las consultas de sql/ (escritas para PostgreSQL) dan lo mismo que el código en Python.
Aquí se ejecutan en DuckDB para no requerir un servidor."""
from pathlib import Path

import duckdb
import pytest

from scrap_copq import metrics as m
from scrap_copq.clean import TABLES
from scrap_copq.config import PROCESSED

SQL = Path(__file__).resolve().parents[1] / "sql"


@pytest.fixture(scope="module")
def con():
    con = duckdb.connect()
    for table in TABLES:
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{(PROCESSED / f'{table}.csv').as_posix()}')")
    return con


def run(con, name):
    return con.execute((SQL / name).read_text()).df()


def test_copq_mensual(con, tables, prod):
    sql = run(con, "03_copq_mensual.sql")
    py = m.copq_by_month(prod, tables["reclamos_cliente"])
    assert sql["copq_mxn"].to_numpy() == pytest.approx(py["copq_mxn"].to_numpy())


def test_pareto_costo(con, tables, prod):
    sql = run(con, "04_pareto_costo.sql")
    py = m.pareto(tables["scrap_por_defecto"], prod, tables["reclamos_cliente"], by="costo")
    assert sql["defecto"].tolist() == py["defecto"].tolist()
    assert sql["pct"].to_numpy() == pytest.approx(py["pct"].to_numpy(), abs=0.01)


def test_carta_p_laney(con, prod):
    sql = run(con, "05_carta_p_laney.sql")
    for line, g in sql.groupby("linea"):
        assert g["fuera_p"].sum() == m.p_chart(m.daily(prod, line))["regla_1"].sum()
        assert g["fuera_laney"].sum() == m.p_chart(m.daily(prod, line), laney=True)["regla_1"].sum()
