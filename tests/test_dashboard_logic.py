"""Dashboard logic that needs neither Streamlit nor Plotly (KPIs, severity, routing simulation...)."""
import math

import networkx as nx
import pandas as pd
import pytest

from netmind.dashboard import logic


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory, demo):
    from netmind.pipeline import analyze_packets, get_state
    from netmind.storage import NetMindDB
    d = NetMindDB(tmp_path_factory.mktemp("dash") / "d.db")
    rid = analyze_packets(demo[0], "Synthetic demo", "synthetic", d, train_until=60, save_model=False)
    out = get_state(d, rid), d.load("metrics", rid), d.load("anomalies", rid), d.load("flows", rid)
    d.close()
    return out


def test_severity_bands():
    assert logic.severity({"peak_deviation": 45})[0] == "High"
    assert logic.severity({"peak_deviation": 12})[0] == "Medium"
    assert logic.severity({"peak_deviation": 4})[0] == "Low"
    assert logic.severity({"peak_deviation": float("nan")})[0] == "Low"
    assert logic.severity({})[0] == "Low"


def test_verdict_tones():
    assert logic.verdict({"incidents": [{}, {}]}, 180) == ("2 incidents in 180 s", "bad")
    assert logic.verdict({"incidents": [{}]}, None) == ("1 incident", "bad")
    assert logic.verdict({"incidents": []}, 60)[1] == "ok"
    st = {"incidents": [], "anomaly_status": {"state": "insufficient_data"}}
    assert logic.verdict(st, 5) == ("Not enough traffic to judge yet", "info")


def test_normal_share():
    s = pd.DataFrame({"is_anomaly": [True, False, False, False], "anomaly_score": [0.7, 0.4, 0.4, 0.4]})
    assert logic.normal_share(s) == 75.0
    skipped = pd.DataFrame({"is_anomaly": [False, False], "anomaly_score": [float("nan")] * 2})
    assert logic.normal_share(skipped) is None
    assert logic.normal_share(pd.DataFrame()) is None


def test_sparkline():
    svg = logic.sparkline_svg([1, 2, float("nan"), 3])
    assert svg.startswith("<svg") and svg.count(",") == 3  # three valid points
    assert logic.sparkline_svg([1]) == ""
    assert logic.sparkline_svg([5, 5, 5]) != ""  # flat series must not divide by zero


def test_kpis_on_demo(demo_run):
    state, metrics, scores, _ = demo_run
    cards = {c["label"]: c for c in logic.kpis(state, metrics, scores)}
    assert len(cards) == 6
    normal = float(cards["Normal latency"]["value"].split()[0])
    worst = float(cards["Worst latency"]["value"].split()[0])
    assert worst > 3 * normal  # congestion is far above the baseline
    assert cards["Worst latency"]["tone"] == "bad"
    share = float(cards["Normal windows"]["value"].rstrip("%"))
    flagged = int(scores["is_anomaly"].astype(bool).sum())
    assert flagged >= 15  # congestion alone covers 30 s = 15 two-second windows
    assert share == round(100 * (1 - flagged / len(scores)), 1)
    html_out = logic.kpi_cards_html(list(cards.values()))
    assert html_out.count('class="nm-kpi"') == 6


def test_report_and_compare(demo_run):
    state, metrics, _, _ = demo_run
    md = logic.run_report_md(state, metrics)
    assert "synthetic traffic" in md
    assert md.count("- **") == len(state["incidents"]) == 3
    cmp = logic.compare_runs(state, state)
    assert "Incidents" in list(cmp["Measure"])
    assert cmp.shape[1] == 2  # same run twice -> the two value columns share a name


def test_filter_flows(demo_run):
    *_, flows = demo_run
    assert len(logic.filter_flows(flows)) == len(flows)
    scan = logic.filter_flows(flows, "192.168.1.66")
    assert 0 < len(scan) < len(flows)
    assert scan["flow"].str.contains("192.168.1.66").all() or \
        (scan["a"].astype(str) + scan["b"].astype(str)).str.contains("192.168.1.66").all()
    proto = flows["proto"].iloc[0]
    only = logic.filter_flows(flows, protocols=[proto])
    assert len(only) > 0


def test_link_failure_reroutes():
    G = nx.Graph()
    G.add_edge("A", "B", latency=1.0)
    G.add_edge("B", "C", latency=1.0)
    G.add_edge("A", "C", latency=5.0)
    G.add_edge("C", "D", latency=1.0)
    df = logic.simulate_link_failure(G, ("A", "B"), "A")
    row = df.set_index("Destination")
    assert row.loc["C", "Next hop before"] == "B" and row.loc["C", "Cost before"] == 2.0
    assert row.loc["C", "Next hop after"] == "C" and row.loc["C", "Cost after"] == 5.0
    assert row.loc["B", "Changed"] and row.loc["C", "Changed"]
    assert df.attrs["dv_rounds"] >= 1
    assert G.has_edge("A", "B")  # the original graph is untouched


def test_link_failure_partition():
    G = nx.Graph()
    G.add_edge("A", "B", latency=1.0)
    G.add_edge("B", "C", latency=1.0)
    row = logic.simulate_link_failure(G, ("B", "C"), "A").set_index("Destination")
    assert row.loc["C", "Next hop after"] == "unreachable"
    assert math.isnan(row.loc["C", "Cost after"]) or row.loc["C", "Cost after"] is None
    assert not row.loc["B", "Changed"]


def test_fmt_seconds():
    assert logic.fmt_seconds(179.991) == "180 s"
    assert logic.fmt_seconds(7.25) == "7.2 s" or logic.fmt_seconds(7.25) == "7.3 s"
    assert logic.fmt_seconds(4.0) == "4 s"
    assert logic.fmt_seconds(None) == "? s"
    assert logic.verdict({"incidents": [{}, {}, {}]}, 179.991) == ("3 incidents in 180 s", "bad")
