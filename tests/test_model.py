import pytest

from scrap_copq import model as md


@pytest.fixture(scope="module")
def fitted(prod):
    threshold, _ = md.find_threshold(prod)
    return threshold, md.fit(prod, threshold)


def test_threshold_is_recovered(fitted):
    threshold, _ = fitted
    assert 150 <= threshold <= 190          # el generador usa 160 h


def test_model_beats_the_baseline_out_of_sample(prod, fitted):
    mae = md.holdout(prod, threshold=fitted[0])
    assert mae["GLM binomial"] < 0.8 * mae["Modelo base (promedio por línea)"]


def test_effects_have_the_expected_direction(fitted):
    ors = md.odds_ratios(fitted[1])
    for factor in ("Operador nuevo · L3", "Lote del proveedor C · L1", "+10 h sobre umbral de mantto · L2"):
        assert ors.loc[factor, "ic95_inf"] > 1


def test_savings_are_consistent(tables, prod, fitted):
    threshold, res = fitted
    sav = md.simulate_savings(res, prod, tables["catalogo_productos"], tables["altas_operadores"],
                              tables["mantenimientos"], tables["reclamos_cliente"], threshold, n_sims=300)
    assert list(sav.index) == ["mantenimiento", "induccion", "proveedor"]
    assert (sav["ahorro_neto_p10"] <= sav["ahorro_neto_p50"]).all()
    assert (sav["ahorro_neto_p50"] <= sav["ahorro_neto_p90"]).all()
    assert sav.loc["mantenimiento", "ahorro_neto_p50"] > 0


def test_l2_hours_cycle_resets_at_the_interval(prod):
    hours = md.l2_hours(prod, 170)
    l2 = prod["linea"] == "L2"
    assert hours[l2].max() < 170
    assert hours[~l2].equals(prod.loc[~l2, "horas_desde_mantto"])
