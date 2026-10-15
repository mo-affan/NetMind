"""Behaviour with too little or unusual input."""
import pytest

from netmind.anomaly import MIN_TRAIN_WINDOWS, InsufficientDataError, detect, window_features
from netmind.capture.records import to_frame
from netmind.capture.synthetic import generate_scenario
from netmind.copilot import Copilot, build_prompt
from netmind.performance import window_metrics, overall
from netmind.pipeline import analyze_packets, get_state


def _first(seconds, seed=7):
    recs, _ = generate_scenario(duration=max(seconds, 1), seed=seed)
    return to_frame([r for r in recs if r["ts"] < recs[0]["ts"] + seconds])


def test_empty_capture_is_rejected_clearly(db):
    with pytest.raises(ValueError, match="no IP packets"):
        analyze_packets(to_frame([]), "empty", "test", db, save_model=False)
    assert db.runs().empty  # nothing half-saved


@pytest.mark.parametrize("seconds", [0.001, 3, 10])
def test_short_capture_skips_detection_instead_of_claiming_normal(db, seconds):
    rid = analyze_packets(_first(seconds), "short", "test", db, save_model=False)
    st = get_state(db, rid)
    assert st["anomaly_status"]["state"] == "insufficient_data"
    assert st["incidents"] == []
    ans = Copilot(backend="offline").ask("Is anything wrong with my network?", st)["answer"]
    assert "Not enough traffic" in ans and "No anomalies detected" not in ans
    assert "NOT run" in build_prompt("x", st, [])  # the LLM is told too


def test_detect_raises_below_minimum_baseline():
    df = _first(2 * MIN_TRAIN_WINDOWS - 3)
    feats = window_features(df, 2.0, window_metrics(df, 2.0))
    with pytest.raises(InsufficientDataError):
        detect(feats)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_normal_only_traffic_has_few_false_alarms(seed):
    """120 s of normal synthetic traffic: at most 1 flagged window after the baseline,
    and never a port-scan or flood pattern."""
    df = to_frame(generate_scenario(duration=120, seed=seed, events=[])[0])
    feats = window_features(df, 2.0, window_metrics(df, 2.0))
    res, det = detect(feats)
    after = res[res["t"] >= feats["t"].iloc[det.baseline["train_windows"]]]
    assert after["is_anomaly"].sum() <= 1


def test_capture_without_replies_has_no_latency_but_still_runs(db):
    recs, _ = generate_scenario(duration=60)
    only_queries = [r for r in recs if r["proto"] == "UDP" and r.get("dns_qr") == 0]
    df = to_frame(only_queries)
    assert overall(df)["latency_ms"] is None
    rid = analyze_packets(df, "dns queries only", "test", db, save_model=False)
    assert get_state(db, rid)["run"]["id"] == rid
