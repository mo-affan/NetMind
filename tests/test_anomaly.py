import json

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
