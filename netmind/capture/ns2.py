"""NS2 Simulation source: read an NS2 trace file into NetMind. Needs no NS2 installation.

Supported format: the standard ns-2 wired trace written by `$ns trace-all` (one event per line):

    event time from to type size flags fid src dst seq pktid
    + 0.5 0 2 tcp 1040 ------- 1 0.0 3.0 0 0

    event   + enqueued at `from` for link from->to, - dequeued (starts transmission),
            r received at `to`, d dropped at the queue of link from->to
    src/dst "node.port" of the packet's original source and final destination
    pktid   unique id of this packet (a TCP retransmission gets a new pktid, same seq)

Lines of other kinds are skipped, except link status lines containing "link-down" /
"link-up" (written by some ns-2 builds for rtmodel events), which are read when present.
The wireless "new trace" format (`-t ... -Hs ...`) is not supported.

Definitions (used everywhere in NetMind for NS2 data):
  sent        a data packet's first "+" at its own source node
  delivered   an "r" event at its final destination node
  dropped     a "d" event anywhere on its path (and never delivered)
  in flight   neither delivered nor dropped when the trace ends; excluded from loss
  delay       one-way: delivered time - sent time (NS2 knows both clocks exactly)
  loss %      dropped / (delivered + dropped), for packets SENT in the window
  throughput  bytes DELIVERED in the window x 8 / window length
  jitter      mean |difference| between consecutive delays of the SAME flow
              (in delivery order), averaged over flows
  retransmission  a TCP packet sent again with a sequence number already sent by that flow

Views of a trace:
  read_trace()        every packet event as a table
  read_link_events()  link-down / link-up lines, if the trace has them
  packet_table()      one row per data packet with its fate and delay
  trace_records()     packets in the NetMind packet-record format (src/dst "n0".."n4")
  trace_metrics()     per-window metrics (all flows, or per flow)
  flow_summary()      totals per flow
  trace_links()       links that carried data, with drops per link
  path_changes()      when each flow's route changed (rerouting after a link failure)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

DATA_TYPES = {"tcp", "cbr", "udp", "exp", "pareto", "ftp", "telnet"}
EVENT_COLS = ["ev", "t", "frm", "to", "type", "size", "flags", "fid", "src", "dst", "seq", "pkt"]


def _node(addr: str) -> int:
    """Node number from an NS2 address like '3.0'."""
    return int(addr.split(".")[0])


def read_trace(path: str) -> pd.DataFrame:
    """All packet events (+ - r d). Malformed or non-packet lines are skipped."""
    rows = []
    with open(path, errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) < 12 or p[0] not in ("+", "-", "r", "d"):
                continue
            try:
                rows.append((p[0], float(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]), p[6],
                             int(p[7]), _node(p[8]), _node(p[9]), int(p[10]), int(p[11])))
            except ValueError:
                continue
    return pd.DataFrame(rows, columns=EVENT_COLS)


def read_link_events(path: str) -> pd.DataFrame:
    """Link status changes written by ns-2 for rtmodel events, if present in the trace.

    Accepts lines containing "link-down" or "link-up" whose second field is the time and
    whose last two integer fields are the link's end nodes, e.g. "v 7 link-down 7 2 3".
    Returns an empty table when the trace has none (route changes are still detected
    from the packets themselves by path_changes()).
    """
    rows = []
    with open(path, errors="replace") as f:
        for line in f:
            m = re.search(r"link-(down|up)", line)
            if not m:
                continue
            p = line.split()
            ints = [x for x in p[2:] if re.fullmatch(r"\d+", x)]
            try:
                t = float(p[1])
            except (IndexError, ValueError):
                continue
            if len(ints) >= 2:
                a, b = sorted((int(ints[-2]), int(ints[-1])))
                rows.append({"t": t, "status": m.group(1), "link": f"n{a}-n{b}"})
    return pd.DataFrame(rows, columns=["t", "status", "link"]).drop_duplicates()


def _events(path_or_events) -> pd.DataFrame:
    """Accepts a trace path or an already-read events table."""
    return read_trace(path_or_events) if isinstance(path_or_events, str) else path_or_events


def _data(ev: pd.DataFrame) -> pd.DataFrame:
    """Keeps data packets (tcp, cbr...), drops routing and ack messages."""
    return ev[ev["type"].isin(DATA_TYPES)]


def packet_table(path_or_events) -> pd.DataFrame:
    """One row per data packet: send/receive/drop times, fate, one-way delay, retransmission flag."""
    d = _data(_events(path_or_events))
    cols = ["pkt", "t_sent", "fid", "type", "size", "src", "dst", "seq", "t_recv", "t_drop",
            "drop_link", "fate", "delay_ms", "retransmission"]
    sent = d[(d["ev"] == "+") & (d["frm"] == d["src"])].sort_values("t").drop_duplicates("pkt")
    if sent.empty:
        return pd.DataFrame(columns=cols)
    sent = sent[["pkt", "t", "fid", "type", "size", "src", "dst", "seq"]].rename(columns={"t": "t_sent"})
    recv = d[(d["ev"] == "r") & (d["to"] == d["dst"])].sort_values("t").drop_duplicates("pkt")
    recv = recv[["pkt", "t"]].rename(columns={"t": "t_recv"})
    drop = d[d["ev"] == "d"].sort_values("t").drop_duplicates("pkt")
    drop = drop.assign(drop_link="n" + drop["frm"].astype(str) + "-n" + drop["to"].astype(str))
    drop = drop[["pkt", "t", "drop_link"]].rename(columns={"t": "t_drop"})
    out = sent.merge(recv, on="pkt", how="left").merge(drop, on="pkt", how="left")
    out["fate"] = np.where(out["t_recv"].notna(), "delivered",
                           np.where(out["t_drop"].notna(), "dropped", "in_flight"))
    out["delay_ms"] = (out["t_recv"] - out["t_sent"]) * 1000
    out = out.sort_values("t_sent").reset_index(drop=True)
    is_tcp = out["type"] == "tcp"
    out["retransmission"] = is_tcp & out.duplicated(subset=["fid", "seq"], keep="first")
    return out[cols]


def trace_records(path_or_events) -> pd.DataFrame:
    """Data packets as NetMind packet records (src/dst = "n<id>"), for the traffic analyzer."""
    from .records import to_frame
    pk = packet_table(path_or_events)
    recs = [{"ts": r.t_sent, "src": f"n{r.src}", "dst": f"n{r.dst}",
             "proto": "TCP" if r.type == "tcp" else "UDP", "app": str(r.type).upper(),
             "length": int(r.size), "payload_len": int(r.size), "seq": int(r.seq),
             "sport": int(r.fid), "dport": int(r.fid)}
            for r in pk.itertuples(index=False)]
    return to_frame(recs)


def _flow_jitter(delivered: pd.DataFrame) -> float:
    """Mean |delta delay| within each flow (delivery order), averaged over flows with >= 2 packets."""
    vals = []
    for _, g in delivered.sort_values("t_recv").groupby("fid"):
        d = g["delay_ms"].to_numpy()
        if len(d) > 1:
            vals.append(float(np.abs(np.diff(d)).mean()))
    return float(np.mean(vals)) if vals else 0.0


def trace_metrics(path_or_events, window: float = 0.5, per_flow: bool = False) -> pd.DataFrame:
    """Per-window metrics. See the module docstring for the exact definitions.

    Columns: t, window_start, packets (= sent), delivered, dropped, in_flight, loss_pct,
    retransmissions, throughput_mbps, latency_ms (mean one-way delay), jitter_ms, pps.
    """
    pk = packet_table(path_or_events)
    cols = ["t", "window_start", "packets", "delivered", "dropped", "in_flight", "loss_pct",
            "retransmissions", "throughput_mbps", "latency_ms", "jitter_ms", "pps"]
    if pk.empty:
        return pd.DataFrame(columns=cols)
    pk["w"] = (pk["t_sent"] // window).astype(int)
    pk["w_recv"] = pk["t_recv"] // window
    last = int(max(pk["w"].max(), pk["w_recv"].max(skipna=True) if pk["w_recv"].notna().any() else 0))
    rows = []
    for fid in ([None] if not per_flow else sorted(pk["fid"].unique())):
        sub = pk if fid is None else pk[pk["fid"] == fid]
        for k in range(last + 1):
            s = sub[sub["w"] == k]
            got = s[s["fate"] == "delivered"]
            arrived = sub[sub["w_recv"] == k]
            n_drop = int((s["fate"] == "dropped").sum())
            known = len(got) + n_drop
            row = {"t": round(k * window, 3), "window_start": round(k * window, 3),
                   "packets": int(len(s)), "delivered": int(len(got)), "dropped": n_drop,
                   "in_flight": int((s["fate"] == "in_flight").sum()),
                   "loss_pct": round(100 * n_drop / known, 2) if known else 0.0,
                   "retransmissions": int(s["retransmission"].sum()),
                   "throughput_mbps": round(arrived["size"].sum() * 8 / window / 1e6, 4),
                   "latency_ms": round(float(got["delay_ms"].mean()), 2) if len(got) else np.nan,
                   "jitter_ms": round(_flow_jitter(got), 2),
                   "pps": round(len(s) / window, 2)}
            if fid is not None:
                row["fid"] = int(fid)
            rows.append(row)
    return pd.DataFrame(rows)


def flow_summary(path_or_events) -> pd.DataFrame:
    """Totals per flow: sent, delivered, dropped, loss %, delay, retransmissions, throughput."""
    pk = packet_table(path_or_events)
    if pk.empty:
        return pd.DataFrame()
    rows = []
    for fid, g in pk.groupby("fid"):
        got = g[g["fate"] == "delivered"]
        n_drop = int((g["fate"] == "dropped").sum())
        span = (got["t_recv"].max() - g["t_sent"].min()) if len(got) else 0
        rows.append({"fid": int(fid), "type": g["type"].iloc[0],
                     "src": f"n{g['src'].iloc[0]}", "dst": f"n{g['dst'].iloc[0]}",
                     "start_s": round(float(g["t_sent"].min()), 3),
                     "end_s": round(float(g["t_sent"].max()), 3),
                     "sent": int(len(g)), "delivered": int(len(got)), "dropped": n_drop,
                     "in_flight": int((g["fate"] == "in_flight").sum()),
                     "loss_pct": round(100 * n_drop / (len(got) + n_drop), 2) if len(got) + n_drop else 0.0,
                     "retransmissions": int(g["retransmission"].sum()),
                     "avg_delay_ms": round(float(got["delay_ms"].mean()), 2) if len(got) else None,
                     "max_delay_ms": round(float(got["delay_ms"].max()), 2) if len(got) else None,
                     "throughput_mbps": round(float(got["size"].sum() * 8 / span / 1e6), 4) if span else 0.0})
    return pd.DataFrame(rows)


def trace_links(path_or_events) -> pd.DataFrame:
    """Links that carried data, with packets (enqueued) and drops per link (both directions)."""
    d = _data(_events(path_or_events))
    hop = d[d["ev"] == "+"]
    if hop.empty:
        return pd.DataFrame(columns=["a", "b", "packets", "bytes", "drops"])
    a = hop[["frm", "to"]].min(axis=1)
    b = hop[["frm", "to"]].max(axis=1)
    links = hop.assign(a=a, b=b).groupby(["a", "b"]).agg(packets=("pkt", "size"),
                                                         bytes=("size", "sum")).reset_index()
    drops = d[d["ev"] == "d"]
    dcount = drops.assign(a=drops[["frm", "to"]].min(axis=1), b=drops[["frm", "to"]].max(axis=1)) \
        .groupby(["a", "b"]).size().rename("drops")
    links = links.merge(dcount, on=["a", "b"], how="left").fillna({"drops": 0})
    links["drops"] = links["drops"].astype(int)
    links["a"] = "n" + links["a"].astype(str)
    links["b"] = "n" + links["b"].astype(str)
    return links


def path_changes(path_or_events) -> pd.DataFrame:
    """When each flow's route changed. A delivered packet's path is its source followed by
    every node it was received at; a new row is written whenever a flow's path differs
    from the previous delivered packet's path (in send order)."""
    d = _data(_events(path_or_events))
    pk = packet_table(d)
    got = pk[pk["fate"] == "delivered"].sort_values("t_sent")
    if got.empty:
        return pd.DataFrame(columns=["t", "fid", "path"])
    hops = d[(d["ev"] == "r") & d["pkt"].isin(got["pkt"])].sort_values("t") \
        .groupby("pkt")["to"].apply(tuple)
    rows, last = [], {}
    for r in got.itertuples(index=False):
        path = (int(r.src),) + hops.get(r.pkt, ())
        if last.get(r.fid) != path:
            rows.append({"t": float(r.t_sent), "fid": int(r.fid),
                         "path": "-".join(f"n{x}" for x in path)})
            last[r.fid] = path
    return pd.DataFrame(rows, columns=["t", "fid", "path"]).sort_values(["fid", "t"]) \
        .reset_index(drop=True)
