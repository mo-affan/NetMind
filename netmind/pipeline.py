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
from netmind.anomaly import AnomalyDetector, detect, episodes, window_features
from netmind.capture import ns2 as ns2src
from netmind.performance import overall, rtt_samples, window_metrics
from netmind.storage import NetMindDB
from netmind.topology import build_graph, edges_frame, nodes_frame

MODELS_DIR = Path("data") / "models"
NS2_FEATURES = ["pps", "throughput_mbps", "latency_ms", "jitter_ms", "loss_pct"]


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
    db = db or NetMindDB()
    summ = summary(df)
    run_id = db.new_run(name, source, summ)
    metrics = window_metrics(df, window, link_capacity_mbps)
    feats = window_features(df, window, metrics)
    scores, det = detect(feats, train_until=train_until, model=model)
    inc = episodes(scores, df, window)
    rtt = rtt_samples(df)
    G = build_graph(df, rtt)
    db.save("protocols", run_id, protocol_distribution(df))
    db.save("flows", run_id, flows(df).head(500))
    db.save("rtt", run_id, rtt)
    _save_common(db, run_id, metrics, scores, inc, G, {
        "overall": overall(df, link_capacity_mbps), "window_s": window,
        "baseline": {k: round(v, 3) for k, v in det.baseline["median"].items()},
        "threshold": round(det.threshold, 3), "train_windows": det.baseline["train_windows"],
        "top_talkers": top_talkers(df).to_dict("records"), "incident_count": int(len(inc)),
        "link_capacity_mbps": link_capacity_mbps})
    if save_model:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        det.save(MODELS_DIR / f"run_{run_id}.joblib")
    return run_id


def analyze_ns2(trace: str, name: str | None = None, db: NetMindDB | None = None,
                window: float = 0.5, train_until: float = 3.0) -> int:
    """Analyse an NS2 trace and store it as a new run. The first `train_until` seconds
    (before the scenario's UDP burst at 3 s) are the normal baseline."""
    db = db or NetMindDB()
    ev = ns2src.read_trace(trace)
    if ev.empty:
        raise ValueError(f"no NS2 events found in {trace}")
    recs = ns2src.trace_records(ev)
    summ = summary(recs)
    run_id = db.new_run(name or Path(trace).name, "ns2", summ)
    metrics = ns2src.trace_metrics(ev, window)
    metrics = metrics[metrics["packets"] > 0].reset_index(drop=True)
    det = AnomalyDetector(NS2_FEATURES)
    det.fit(metrics[metrics["t"] < train_until])
    scores = det.score(metrics)
    # NS2 trace times start at 0, like the window times, so shift records to match
    inc = episodes(scores, recs.assign(ts=recs["ts"] - recs["ts"].min()), window, gap=0)
    routes = ns2src.path_changes(ev)
    first_path = routes.groupby("fid")["t"].transform("min") == routes["t"]
    changes = routes[~first_path]
    for i, e in inc.iterrows():
        if ((changes["t"] >= e["start_t"]) & (changes["t"] < e["end_t"])).any():
            inc.loc[i, ["type", "title"]] = ["reroute", "Link failure and rerouting"]
    links = ns2src.trace_links(ev)
    G = build_graph(pd.DataFrame(columns=recs.columns))
    for r in links.to_dict("records"):
        G.add_edge(r["a"], r["b"], packets=int(r["packets"]), bytes=int(r["bytes"]),
                   drops=int(r["drops"]), hops=1, latency=1.0, measured=False)
    for n in G.nodes:
        G.nodes[n]["kind"] = "ns2-node"
    db.save("protocols", run_id, protocol_distribution(recs))
    db.save("flows", run_id, flows(recs))
    _save_common(db, run_id, metrics, scores, inc, G, {
        "overall": {"latency_ms": round(float(metrics["latency_ms"].mean()), 2),
                    "loss_pct": round(100 * metrics["dropped"].sum() / max(metrics["packets"].sum(), 1), 2),
                    "throughput_mbps": round(float(metrics["throughput_mbps"].mean()), 4),
                    "jitter_ms": round(float(metrics["jitter_ms"].mean()), 2),
                    "dropped": int(metrics["dropped"].sum())},
        "window_s": window, "routes": routes.to_dict("records"),
        "baseline": {k: round(v, 3) for k, v in det.baseline["median"].items()},
        "threshold": round(det.threshold, 3), "train_windows": det.baseline["train_windows"],
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
            "top_talkers": s.get("top_talkers", [])}
