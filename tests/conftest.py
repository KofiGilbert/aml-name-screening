from pathlib import Path

import pytest

from screening.watchlist import Watchlist

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_sdn.csv"


@pytest.fixture(scope="session")
def watchlist() -> Watchlist:
    return Watchlist.from_csv(DATA)


@pytest.fixture
def queue(tmp_path):
    from screening.queue import ReviewQueue
    return ReviewQueue(tmp_path / "alerts.db")
