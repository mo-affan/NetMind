import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netmind.capture.records import to_frame  # noqa: E402
from netmind.capture.synthetic import generate_scenario  # noqa: E402

NS2_SAMPLE = ROOT / "tests" / "data" / "sample_ns2.tr"


@pytest.fixture(scope="session")
def demo():
    recs, events = generate_scenario()
    df = to_frame(recs)
    t0 = df["ts"].min()
    return df, [(s - t0, e - t0, n) for s, e, n in events]


@pytest.fixture
def db(tmp_path):
    from netmind.storage import NetMindDB
    d = NetMindDB(tmp_path / "test.db")
    yield d
    d.close()
