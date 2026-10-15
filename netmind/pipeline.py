"""End-to-end pipeline: packets -> analysis -> anomaly detection -> database.

    analyze_packets(df, ...)  live capture, pcap file or demo traffic
    analyze_ns2(trace, ...)   NS2 trace file
    get_state(db, run_id)     everything the Copilot and dashboard need about a run
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from netmind.analyzer import flows, protocol_distribution, summary, top_talkers
from netmind.anomaly import (MIN_TRAIN_WINDOWS, AnomalyDetector, InsufficientDataError, detect,
                             episodes, window_features)
from netmind.capture import ns2 as ns2src
from netmind.performance import overall, rtt_samples, window_metrics
from netmind.storage import NetMindDB
from netmind.topology import build_graph, edges_frame, nodes_frame

NS2_FEATURES = ["pps", "throughput_mbps", "latency_ms", "jitter_ms", "loss_pct", "retransmissions"]
# NS2 output is a controlled, repeatable simulation, so a shorter baseline is enough:
# 4 windows of 0.5 s (the scenario has 5 normal windows, 0.5-3 s, before the UDP burst).
NS2_MIN_TRAIN_WINDOWS = 4


def _no_detection(feats: pd.DataFrame, reason: str,
                  min_windows: int = MIN_TRAIN_WINDOWS) -> tuple[pd.DataFrame, dict]:
    """Scores table for a run where detection was skipped: no score, nothing flagged."""
    scores = feats[[c for c in ("t", "window_start") if c in feats.columns]].copy()
    scores["anomaly_score"] = float("nan")
    scores["max_deviation"] = float("nan")
    scores["is_anomaly"] = False
    scores["top_features"] = "[]"
    return scores, {"state": "insufficient_data", "reason": reason, "min_windows": min_windows}


def _save_common(db, run_id, metrics, scores, incidents, G, extra_summary):
    db.save("metrics", run_id, metrics)
    db.save("anomalies", run_id, scores)
    db.save("nodes", run_id, nodes_frame(G))
    db.save("links", run_id, edges_frame(G))
    if not incidents.empty:
        inc = incidents.copy()
        inc["top_features"] = inc["top_features"].astype(str)
        db.save("incidents", run_id, inc)
    s = db.run(run_id)["summary"]
    s.update(extra_summary)
    db.update_summary(run_id, s)


def analyze_packets(df: pd.DataFrame, name: str, source: str = "pcap", db: NetMindDB | None = None,
                    window: float = 2.0, train_until: float | None = None,
                    model: AnomalyDetector | None = None, link_capacity_mbps: float = 100.0,
                    save_model: bool = True) -> int:
    """Analyse packet records and store everything as a new run. Returns the run id.

    The anomaly model is trained on the first `train_until` seconds (default: first 30%
    of the capture), which should be normal traffic, unless a trained `model` is given.
    """
    if df is None or df.empty:
        raise ValueError("no IP packets to analyse (the capture or file is empty)")
    db = db or NetMindDB()
    summ = summary(df)
    run_id = db.new_run(name, source, summ)
    metrics = window_metrics(df, window, link_capacity_mbps)
    feats = window_features(df, window, metrics)
    try:
        scores, det = detect(feats, train_until=train_until, model=model)
        status = {"state": "ok", "train_windows": det.baseline["train_windows"]}
        inc = episodes(scores, df, window)
    except InsufficientDataError as e:
        det = None
        scores, status = _no_detection(feats, str(e))
        inc = episodes(scores, df, window)
    rtt = rtt_samples(df)
    G = build_graph(df, rtt)
    db.save("protocols", run_id, protocol_distribution(df))
    db.save("flows", run_id, flows(df).head(500))
    db.save("rtt", run_id, rtt)
    _save_common(db, run_id, metrics, scores, inc, G, {
        "overall": overall(df, link_capacity_mbps), "window_s": window,
        "anomaly_status": status,
        "baseline": {k: round(v, 3) for k, v in det.baseline["median"].items()} if det else {},
        "threshold": round(det.threshold, 3) if det else None,
        "train_windows": det.baseline["train_windows"] if det else 0,
        "top_talkers": top_talkers(df).to_dict("records"), "incident_count": int(len(inc)),
        "link_capacity_mbps": link_capacity_mbps})
    if save_model and det is not None:  # saved next to the database it belongs to
        models = Path(db.path).parent / "models"
        models.mkdir(parents=True, exist_ok=True)
        det.save(models / f"run_{run_id}.joblib")
    return run_id


def analyze_ns2(trace: str, name: str | None = None, db: NetMindDB | None = None,
                window: float = 0.5, train_until: float = 3.0) -> int:
    """Analyse an existing NS2 trace file (no NS2 needed) and store it as a new run.

    The first `train_until` seconds (before the scenario's UDP burst at 3 s) are the
    normal baseline for anomaly detection. Metric definitions: netmind/capture/ns2.py.
    """
    db = db or NetMindDB()
    ev = ns2src.read_trace(trace)
    if ev.empty:
        raise ValueError(f"no NS2 packet events found in {trace}: is it a wired trace "
                         "written by `$ns trace-all`?")
    pk = ns2src.packet_table(ev)
    if pk.empty:
        raise ValueError(f"{trace} has events but no data packets (tcp/cbr/udp)")
    recs = ns2src.trace_records(ev)
    summ = summary(recs)
    run_id = db.new_run(name or Path(trace).name, "ns2", summ)
    metrics = ns2src.trace_metrics(ev, window)
    metrics = metrics[metrics["packets"] > 0].reset_index(drop=True)
    base = metrics[metrics["t"] < train_until]
    if len(base) < NS2_MIN_TRAIN_WINDOWS:  # too little before train_until: first 30% of windows
        base = metrics.iloc[:max(NS2_MIN_TRAIN_WINDOWS, int(len(metrics) * 0.3))]
    if len(base) >= NS2_MIN_TRAIN_WINDOWS:
        det = AnomalyDetector(NS2_FEATURES)
        det.fit(base)
        scores = det.score(metrics)
        status = {"state": "ok", "train_windows": int(len(base))}
    else:
        det = None
        scores, status = _no_detection(metrics, f"only {len(metrics)} window(s) of {window:g} s in "
                                       f"the trace; at least {NS2_MIN_TRAIN_WINDOWS} are needed",
                                       NS2_MIN_TRAIN_WINDOWS)
    # trace times and window times both start at 0, so records are aligned to 0 as well
    inc = episodes(scores, recs.assign(ts=recs["ts"] - recs["ts"].min()), window, gap=0)
    routes = ns2src.path_changes(ev)
    link_events = ns2src.read_link_events(trace)
    first_path = routes.groupby("fid")["t"].transform("min") == routes["t"]
    changes = list(routes[~first_path]["t"]) + list(link_events["t"])
    for i, e in inc.iterrows():
        if any(e["start_t"] <= t < e["end_t"] for t in changes):
            inc.loc[i, ["type", "title"]] = ["reroute", "Link failure and rerouting"]
    links = ns2src.trace_links(ev)
    G = build_graph(pd.DataFrame(columns=recs.columns))
    for r in links.to_dict("records"):
        G.add_edge(r["a"], r["b"], packets=int(r["packets"]), bytes=int(r["bytes"]),
                   drops=int(r["drops"]), hops=1, latency=1.0, measured=False)
    for n in G.nodes:
        G.nodes[n]["kind"] = "ns2-node"
    flows_ns2 = ns2src.flow_summary(ev)
    got = pk[pk["fate"] == "delivered"]
    n_drop = int((pk["fate"] == "dropped").sum())
    db.save("protocols", run_id, protocol_distribution(recs))
    db.save("flows", run_id, flows(recs))
    _save_common(db, run_id, metrics, scores, inc, G, {
        "overall": {"latency_ms": round(float(got["delay_ms"].mean()), 2) if len(got) else None,
                    "loss_pct": round(100 * n_drop / (len(got) + n_drop), 2) if len(got) + n_drop else 0.0,
                    "throughput_mbps": round(float(metrics["throughput_mbps"].mean()), 4),
                    "jitter_ms": round(float(metrics["jitter_ms"].mean()), 2),
                    "sent": int(len(pk)), "delivered": int(len(got)), "dropped": n_drop,
                    "in_flight": int((pk["fate"] == "in_flight").sum()),
                    "retransmissions": int(pk["retransmission"].sum())},
        "window_s": window, "routes": routes.to_dict("records"),
        "link_events": link_events.to_dict("records"),
        "ns2_flows": flows_ns2.to_dict("records"), "anomaly_status": status,
        "baseline": {k: round(v, 3) for k, v in det.baseline["median"].items()} if det else {},
        "threshold": round(det.threshold, 3) if det else None,
        "train_windows": det.baseline["train_windows"] if det else 0,
        "incident_count": int(len(inc))})
    return run_id


def get_state(db: NetMindDB, run_id: int | None = None) -> dict:
    """Network state of one run, in the shape the Copilot and API use."""
    run_id = run_id or db.latest_run_id()
    if run_id is None:
        return {"run": {}, "incidents": []}
    run = db.run(run_id)
    s = run["summary"]
    metrics = db.load("metrics", run_id)
    inc = db.load("incidents", run_id)
    incidents = []
    for r in inc.to_dict("records") if not inc.empty else []:
        r["top_features"] = json.loads(r["top_features"]) if isinstance(r["top_features"], str) else []
        incidents.append(r)
    latest = None
    if not metrics.empty:
        keep = [c for c in ("t", "pps", "throughput_mbps", "latency_ms", "jitter_ms", "loss_pct",
                            "retransmissions") if c in metrics.columns]
        latest = {k: (None if pd.isna(v) else v) for k, v in metrics.iloc[-1][keep].to_dict().items()}
    traffic = {k: s.get(k) for k in ("packets", "bytes", "duration_s", "flows", "hosts",
                                    "tcp_connections", "protocols")}
    return {"run": {"id": run["id"], "name": run["name"], "source": run["source"]},
            "summary": traffic, "overall": s.get("overall", {}), "baseline": s.get("baseline", {}),
            "latest_window": latest, "incidents": incidents, "routes": s.get("routes", []),
            "anomaly_status": s.get("anomaly_status", {"state": "ok"}),
            "top_talkers": s.get("top_talkers", [])}
