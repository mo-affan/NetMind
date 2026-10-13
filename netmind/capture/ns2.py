"""NS2 Simulation source: read an NS2 trace file into NetMind.

NS2 wired trace line:
    event time from to type size flags fid src dst seq pktid
    event: + enqueue  - dequeue  r receive  d drop
    src / dst look like "0.0" = node.port

Three views of a trace:
  read_trace()      every event as a table
  trace_records()   one row per data packet in the NetMind packet-record format
                    (src/dst are node names like "n0"), so the traffic analyzer works on it
  trace_metrics()   throughput, loss, one-way delay and jitter per time window
  trace_links()     links that carried traffic, for the topology graph
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DATA_TYPES = {"tcp", "cbr", "udp", "exp", "pareto"}
EVENT_COLS = ["ev", "t", "frm", "to", "type", "size", "flags", "fid", "src", "dst", "seq", "pkt"]


def read_trace(path: str) -> pd.DataFrame:
    rows = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) < 12 or p[0] not in ("+", "-", "r", "d"):
                continue
            try:
                rows.append((p[0], float(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), p[6],
                             int(p[7]), int(p[8].split(".")[0]), int(p[9].split(".")[0]),
                             int(p[10]), int(p[11])))
            except ValueError:
                continue
    return pd.DataFrame(rows, columns=EVENT_COLS)


def _data(ev: pd.DataFrame) -> pd.DataFrame:
    return ev[ev["type"].isin(DATA_TYPES)]


def _packet_table(ev: pd.DataFrame) -> pd.DataFrame:
    """One row per data packet: when it left its source, when (if) it arrived, if it was dropped."""
    d = _data(ev)
    sent = d[(d["ev"] == "+") & (d["frm"] == d["src"])].drop_duplicates("pkt")[
        ["pkt", "t", "fid", "type", "size", "src", "dst", "seq"]].rename(columns={"t": "t_sent"})
    recv = d[(d["ev"] == "r") & (d["to"] == d["dst"])].drop_duplicates("pkt")[["pkt", "t"]] \
        .rename(columns={"t": "t_recv"})
    drop = d[d["ev"] == "d"].drop_duplicates("pkt")[["pkt", "t", "frm", "to"]] \
        .rename(columns={"t": "t_drop", "frm": "drop_frm", "to": "drop_to"})
    out = sent.merge(recv, on="pkt", how="left").merge(drop, on="pkt", how="left")
    out["delay_ms"] = (out["t_recv"] - out["t_sent"]) * 1000
    out["dropped"] = out["t_recv"].isna() & out["t_drop"].notna()
    return out.sort_values("t_sent").reset_index(drop=True)


def trace_records(path_or_events) -> pd.DataFrame:
    """Data packets as NetMind packet records (src/dst = "n<id>")."""
    from .records import to_frame
    ev = read_trace(path_or_events) if isinstance(path_or_events, str) else path_or_events
    pk = _packet_table(ev)
    recs = [{"ts": r.t_sent, "src": f"n{r.src}", "dst": f"n{r.dst}",
             "proto": "TCP" if r.type == "tcp" else "UDP", "app": r.type.upper(),
             "length": int(r.size), "payload_len": int(r.size), "seq": int(r.seq),
             "sport": int(r.fid), "dport": int(r.fid)}
            for r in pk.itertuples(index=False)]
    return to_frame(recs)


def trace_metrics(path_or_events, window: float = 0.5, per_flow: bool = False) -> pd.DataFrame:
    """Per-window metrics from a trace.

    latency_ms here is one-way delay (receive time - send time); NS2 knows both ends.
    loss_pct = dropped / sent for packets that left their source in the window.
    throughput_mbps = bytes delivered to destinations in the window.
    """
    ev = read_trace(path_or_events) if isinstance(path_or_events, str) else path_or_events
    pk = _packet_table(ev)
    cols = ["t", "window_start", "packets", "dropped", "loss_pct", "throughput_mbps",
            "latency_ms", "jitter_ms", "pps"]
    if pk.empty:
        return pd.DataFrame(columns=cols)
    pk["w"] = (pk["t_sent"] // window).astype(int)
    pk["w_recv"] = (pk["t_recv"] // window)
    keys = ["w", "fid"] if per_flow else ["w"]
    rows = []
    last = int(max(pk["w"].max(), np.nanmax(pk["w_recv"].fillna(0))))
    groups = [None] if not per_flow else sorted(pk["fid"].unique())
    for fid in groups:
        sub = pk if fid is None else pk[pk["fid"] == fid]
        for k in range(last + 1):
            s = sub[sub["w"] == k]
            delivered = sub[sub["w_recv"] == k]
            delays = s.dropna(subset=["delay_ms"]).sort_values("t_recv")["delay_ms"].to_numpy()
            n = len(s)
            row = {"t": round(k * window, 3), "window_start": round(k * window, 3),
                   "packets": n, "dropped": int(s["dropped"].sum()),
                   "loss_pct": round(100 * s["dropped"].sum() / n, 2) if n else 0.0,
                   "throughput_mbps": round(delivered["size"].sum() * 8 / window / 1e6, 4),
                   "latency_ms": round(float(delays.mean()), 2) if len(delays) else np.nan,
                   "jitter_ms": round(float(np.abs(np.diff(delays)).mean()), 2) if len(delays) > 1 else 0.0,
                   "pps": round(n / window, 2)}
            if fid is not None:
                row["fid"] = int(fid)
            rows.append(row)
    return pd.DataFrame(rows)


def trace_links(path_or_events) -> pd.DataFrame:
    """Links that carried data, with packets and drops per link (from hop-by-hop events)."""
    ev = read_trace(path_or_events) if isinstance(path_or_events, str) else path_or_events
    d = _data(ev)
    hop = d[d["ev"] == "+"]
    a = hop[["frm", "to"]].min(axis=1)
    b = hop[["frm", "to"]].max(axis=1)
    links = hop.assign(a=a, b=b).groupby(["a", "b"]).agg(packets=("pkt", "size"),
                                                         bytes=("size", "sum")).reset_index()
    drops = d[d["ev"] == "d"]
    da = drops[["frm", "to"]].min(axis=1)
    db = drops[["frm", "to"]].max(axis=1)
    dcount = drops.assign(a=da, b=db).groupby(["a", "b"]).size().rename("drops")
    links = links.merge(dcount, on=["a", "b"], how="left").fillna({"drops": 0})
    links["drops"] = links["drops"].astype(int)
    links["a"] = "n" + links["a"].astype(str)
    links["b"] = "n" + links["b"].astype(str)
    return links


def path_changes(path_or_events) -> pd.DataFrame:
    """Times when the route a flow takes changes (e.g. rerouting after a link failure).

    For each data packet, the sequence of nodes it was received at gives its path.
    """
    ev = read_trace(path_or_events) if isinstance(path_or_events, str) else path_or_events
    d = _data(ev)
    r = d[d["ev"] == "r"].sort_values("t")
    first = d[(d["ev"] == "+") & (d["frm"] == d["src"])].drop_duplicates("pkt").set_index("pkt")
    paths = r.groupby("pkt")["to"].apply(lambda s: tuple(s))
    rows = []
    last = {}
    for pkt, hops in paths.items():
        if pkt not in first.index:
            continue
        f = first.loc[pkt]
        full = (int(f["src"]),) + hops
        if full[-1] != int(f["dst"]):
            continue
        fid = int(f["fid"])
        if last.get(fid) != full:
            rows.append({"t": float(f["t"]), "fid": fid, "path": "-".join(f"n{x}" for x in full)})
            last[fid] = full
    return pd.DataFrame(rows, columns=["t", "fid", "path"])
