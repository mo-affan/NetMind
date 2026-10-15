import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netmind.capture.records import to_frame  # noqa: E402
from netmind.capture.synthetic import generate_scenario  # noqa: E402

NS2_SAMPLE = ROOT / "tests" / "data" / "sample_ns2.tr"


@pytest.fixture(autouse=True)
def offline_copilot(monkeypatch):
    """Tests never call an external LLM, even if ANTHROPIC_API_KEY is set on this machine."""
    monkeypatch.setenv("NETMIND_LLM", "offline")


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


def run_cli(*args, db_path=None, cwd=None, timeout=300):
    """Run `python -m netmind ...` in a subprocess with an isolated database."""
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(ROOT), "NETMIND_LLM": "offline"}
    if db_path is not None:
        env["NETMIND_DB"] = str(db_path)
    return subprocess.run([sys.executable, "-m", "netmind", *map(str, args)], capture_output=True,
                          text=True, cwd=cwd or ROOT, env=env, timeout=timeout)
