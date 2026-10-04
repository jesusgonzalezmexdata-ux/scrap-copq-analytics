import pandas as pd

from scrap_copq.clean import clean, load
from scrap_copq.config import RAW, SHIFTS
from scrap_copq.generate import generate


def test_generator_is_reproducible():
    a, b = generate(seed=1), generate(seed=1)
    pd.testing.assert_frame_equal(a["produccion_turnos"], b["produccion_turnos"])


def test_raw_data_has_the_documented_issues():
    raw = load(RAW)["produccion_turnos"]
    assert raw["run_id"].duplicated().any()
    assert raw["humedad_rel_pct"].isna().any()
    assert not set(raw["turno"]).issubset(SHIFTS)


def test_clean_fixes_every_issue():
    tables, log = clean(load(RAW))
    prod, defects = tables["produccion_turnos"], tables["scrap_por_defecto"]
    assert not prod["run_id"].duplicated().any()
    assert set(prod["turno"]) == set(SHIFTS)
    assert prod["humedad_rel_pct"].notna().all()
    assert (prod["piezas_scrap"] <= prod["piezas_producidas"]).all()
    by_run = defects.groupby("run_id")["piezas"].sum()
    assert (prod.set_index("run_id")["piezas_scrap"] == by_run.reindex(prod["run_id"]).fillna(0).to_numpy()).all()
    assert log["filas_limpias"] == len(prod)
