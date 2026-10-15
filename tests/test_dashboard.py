"""Render the Streamlit dashboard headless with Streamlit's AppTest (skipped without streamlit)."""
import pytest
from conftest import ROOT

APP = str(ROOT / "netmind" / "dashboard" / "app.py")


@pytest.fixture
def apptest(monkeypatch, tmp_path):
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest
    dbp = tmp_path / "dash.db"
    monkeypatch.setenv("NETMIND_DB", str(dbp))
    return AppTest, dbp


def test_dashboard_empty_database(apptest):
    AppTest, _ = apptest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("Welcome" in h.value for h in at.header)


def test_dashboard_with_demo_run(apptest, demo):
    AppTest, dbp = apptest
    from netmind.pipeline import analyze_packets
    from netmind.storage import NetMindDB
    d = NetMindDB(dbp)
    analyze_packets(demo[0], "Synthetic demo", "synthetic", d, train_until=60, save_model=False)
    d.close()
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    assert any("Synthetic demo" in h.value for h in at.header)
    assert any("3 incidents" in e.value for e in at.error)
    assert len(at.metric) == 5


def test_dashboard_demo_button_creates_a_run(apptest):
    AppTest, dbp = apptest
    at = AppTest.from_file(APP, default_timeout=300).run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    from netmind.storage import NetMindDB
    d = NetMindDB(dbp)
    assert list(d.runs()["source"]) == ["synthetic"]
    d.close()
