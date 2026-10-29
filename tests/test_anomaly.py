import json
import pytest

import pandas as pd

from netmind.anomaly import AnomalyDetector, detect, episodes, window_features
from netmind.performance import window_metrics


def _label(t, events):
    return next((n for s, e, n in events if s <= t < e), "normal")


def test_detects_all_injected_events(demo):
    df, events = demo
    feats = window_features(df, 2.0, window_metrics(df, 2.0))
    res, model = detect(feats, train_until=60)
    res["label"] = [_label(t, events) for t in res["t"]]
    for name in ("congestion", "port_scan", "ping_flood"):
        assert res[res["label"] == name]["is_anomaly"].mean() >= 0.75, name
    normal = res[res["label"] == "normal"]
    assert normal["is_anomaly"].mean() < 0.05
    inc = episodes(res, df, 2.0)
    assert list(inc["type"]) == ["congestion", "port_scan", "flood"]
    scan = inc.iloc[1]
    assert scan["top_src"] == "192.168.1.66" and scan["top_dst"] == "192.168.1.10"
    assert json.loads(scan["top_features"])[0]["feature"] in ("dst_ports", "connections")


def test_scores_are_on_0_1_scale_and_model_saves(tmp_path, demo):
    df, _ = demo
    feats = window_features(df, 2.0)
    det = AnomalyDetector().fit(feats[feats["t"] < 60])
    s = det.score(feats)
    assert s["anomaly_score"].between(0, 1).all()
    det.save(tmp_path / "m.joblib")
    again = AnomalyDetector.load(tmp_path / "m.joblib").score(feats)
    pd.testing.assert_series_equal(s["anomaly_score"], again["anomaly_score"])


@pytest.mark.parametrize("seed", [1, 2, 5])
def test_other_seeds_move_the_problems_and_all_are_still_found(seed, db):
    """Any seed other than 7 builds a different scenario; NetMind must still find every problem."""
    from netmind.capture.records import to_frame
    from netmind.capture.synthetic import EVENTS, generate_scenario, scenario_for
    from netmind.pipeline import analyze_packets, get_state
    planned, params = scenario_for(seed, 180)
    assert planned != EVENTS and len(planned) == 3
    assert scenario_for(seed, 180) == (planned, params)  # reproducible
    recs, _ = generate_scenario(duration=180, seed=seed)
    st = get_state(db, analyze_packets(to_frame(recs), "seed", "synthetic", db, train_until=60, save_model=False))
    kind = {"congestion": "congestion", "port_scan": "port_scan", "ping_flood": "flood"}
    for start, end, name in planned:
        hits = [e for e in st["incidents"] if e["start_t"] < end + 2 and e["end_t"] > start - 2]
        assert any(e["type"] == kind[name] for e in hits), (name, start, end, st["incidents"])
    scan = next(e for e in st["incidents"] if e["type"] == "port_scan")
    assert scan["top_src"] == params["attacker"]


def test_seed_7_is_still_the_fixed_demo():
    from netmind.capture.synthetic import EVENTS, scenario_for
    assert scenario_for(7, 180)[0] == EVENTS and scenario_for(7, 180)[1]["attacker"] == "192.168.1.66"
