"""Render the Streamlit dashboard headless with Streamlit's AppTest (skipped without streamlit).

Every page is drawn for a real demo run, and the main interactions are exercised: creating a run
from the sidebar, asking the Copilot, opening the Copilot from an incident and simulating a link
failure."""
import pytest
from conftest import ROOT

APP = str(ROOT / "netmind" / "dashboard" / "app.py")
PAGES = ["Overview", "Incidents", "Traffic", "Performance", "Topology & routing", "Copilot",
         "Compare runs", "Data & export"]


@pytest.fixture
def apptest(monkeypatch, tmp_path):
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest
    dbp = tmp_path / "dash.db"
    monkeypatch.setenv("NETMIND_DB", str(dbp))
    return AppTest, dbp


@pytest.fixture
def demo_app(apptest, demo):
    AppTest, dbp = apptest
    from netmind.pipeline import analyze_packets
    from netmind.storage import NetMindDB
    d = NetMindDB(dbp)
    analyze_packets(demo[0], "Synthetic demo", "synthetic", d, train_until=60, save_model=False)
    d.close()
    return AppTest.from_file(APP, default_timeout=180).run()


def _html(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def _button(at, key):
    return next(b for b in at.button if b.key == key)


def test_dashboard_empty_database(apptest):
    AppTest, _ = apptest
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert "Welcome to NetMind" in _html(at)
    assert any(b.key == "btn_demo" for b in at.sidebar.button)


def test_overview_shows_verdict_kpis_and_copilot(demo_app):
    at = demo_app
    assert not at.exception
    page = _html(at)
    assert "Synthetic demo" in page and "3 incidents in 180 s" in page
    assert page.count('class="nm-kpi"') == 6
    assert "Ask the Copilot" in page
    assert any(b.key == "ov_sugg_0" for b in at.button)


def test_every_page_renders(demo_app):
    at = demo_app
    for p in PAGES:
        at.sidebar.radio[0].set_value(p).run()
        assert not at.exception, p


def test_suggestion_gets_an_answer_from_the_data(demo_app):
    at = demo_app
    _button(at, "ov_sugg_0").click().run()  # "Why is the network slow?"
    assert not at.exception
    msgs = [m for m in at.chat_message]
    assert len(msgs) == 2 and msgs[0].name == "user" and msgs[1].name == "assistant"
    answer = " ".join(str(x.value) for x in msgs[1].markdown)
    assert "congestion" in answer.lower()


def test_incident_button_opens_copilot_with_answer(demo_app):
    at = demo_app
    at.sidebar.radio[0].set_value("Incidents").run()
    _button(at, "inc_ask_0").click().run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "Copilot"
    assert len(at.chat_message) == 2


def test_link_failure_simulation(demo_app):
    at = demo_app
    at.sidebar.radio[0].set_value("Topology & routing").run()
    fail = next(s for s in at.selectbox if s.key == "topo_fail")
    assert len(fail.options) > 1
    fail.set_value(fail.options[1]).run()
    assert not at.exception
    assert len(at.dataframe) >= 2  # LS vs DV table and the before/after table


def test_dashboard_demo_button_creates_a_run(apptest):
    AppTest, dbp = apptest
    at = AppTest.from_file(APP, default_timeout=300).run()
    _button(at, "btn_demo").click().run()
    assert not at.exception
    from netmind.storage import NetMindDB
    d = NetMindDB(dbp)
    assert list(d.runs()["source"]) == ["synthetic"]
    d.close()
    assert "3 incidents" in _html(at)
