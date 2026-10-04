import numpy as np
import pandas as pd
import pytest

from scrap_copq import metrics as m


def test_p_chart_limits_follow_the_formula():
    daily = pd.DataFrame({"n": [100, 200, 400], "x": [2, 6, 4]})
    daily["p"] = daily["x"] / daily["n"]
    out = m.p_chart(daily)
    pbar = 12 / 700
    expected = pbar + 3 * np.sqrt(pbar * (1 - pbar) / daily["n"])
    assert out["lc"].iat[0] == pytest.approx(pbar)
    assert np.allclose(out["lsc"], expected)
    assert (out["lic"] >= 0).all()


def test_laney_widens_limits_when_there_is_overdispersion():
    rng = np.random.default_rng(0)
    n = np.full(200, 5000)
    p = np.clip(0.02 + rng.normal(0, 0.004, 200), 0.001, None)   # variación extra entre días
    daily = pd.DataFrame({"n": n, "x": rng.binomial(n, p)})
    daily["p"] = daily["x"] / daily["n"]
    classic, laney = m.p_chart(daily), m.p_chart(daily, laney=True)
    assert laney.attrs["sigma_z"] > 1.5
    assert (laney["lsc"] > classic["lsc"]).all()
    assert laney["regla_1"].sum() < classic["regla_1"].sum()


def test_western_electric_rules():
    z = pd.Series([0.0] * 5 + [3.5] + [0.5] * 8 + [-2.5, 0.0, -2.2])
    rules = m.western_electric(z)
    assert rules["regla_1"].tolist().index(True) == 5
    assert rules.loc[13, "regla_4"]                 # 8 puntos seguidos por encima del centro
    assert rules.loc[16, "regla_2"]                 # 2 de 3 por debajo de -2σ
    assert not rules.loc[:4, "senal"].any()


def test_pareto_is_complete_and_sorted(tables, prod):
    for by in ("piezas", "costo"):
        out = m.pareto(tables["scrap_por_defecto"], prod, tables["reclamos_cliente"], by=by)
        assert out["pct"].sum() == pytest.approx(100)
        assert out["pct_acum"].is_monotonic_increasing
        assert out["valor"].is_monotonic_decreasing


def test_cost_pareto_includes_claims(tables, prod):
    defects, claims = tables["scrap_por_defecto"], tables["reclamos_cliente"]
    scrap_only = m.pareto(defects, prod, by="costo")["valor"].sum()
    with_claims = m.pareto(defects, prod, claims, by="costo")["valor"].sum()
    assert with_claims - scrap_only == pytest.approx(claims["costo_total_mxn"].sum())


def test_copq_adds_up(tables, prod):
    k = m.kpis(prod, tables["reclamos_cliente"])
    monthly = m.copq_by_month(prod, tables["reclamos_cliente"])
    assert k["copq_mxn"] == pytest.approx(k["costo_scrap_mxn"] + k["costo_retrabajo_mxn"] + k["costo_reclamos_mxn"])
    assert monthly["copq_mxn"].sum() == pytest.approx(k["copq_mxn"])
