import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrap_copq import metrics as m  # noqa: E402
from scrap_copq.clean import load  # noqa: E402
from scrap_copq.config import PROCESSED  # noqa: E402


@pytest.fixture(scope="session")
def tables():
    return load(PROCESSED)


@pytest.fixture(scope="session")
def prod(tables):
    return m.with_costs(tables["produccion_turnos"], tables["catalogo_productos"])
