"""M2 Traffic Analyzer: protocol classification, flows and traffic summaries."""
from __future__ import annotations

import pandas as pd


def label(df: pd.DataFrame) -> pd.Series:
    """Display protocol for each packet: the application protocol if known, else the transport."""
    return df["app"].where(df["app"] != "", df["proto"])


def protocol_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Packets and bytes per protocol (TCP, UDP, ICMP, DNS, HTTP, HTTPS...)."""
    if df.empty:
        return pd.DataFrame(columns=["protocol", "packets", "bytes", "share_pct"])
    g = df.assign(protocol=label(df)).groupby("protocol").agg(
        packets=("ts", "size"), bytes=("length", "sum")).reset_index()
    g["share_pct"] = (100 * g["packets"] / g["packets"].sum()).round(1)
    return g.sort_values("packets", ascending=False).reset_index(drop=True)


def add_flow_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `flow` column (the canonical 5-tuple as text)."""
    out = df.copy()
    if out.empty:
        out["flow"] = []
        return out
    a_ip, b_ip = out["src"], out["dst"]
    a_p, b_p = out["sport"], out["dport"]
    swap = (a_ip > b_ip) | ((a_ip == b_ip) & (a_p > b_p))
    lo_ip = a_ip.where(~swap, b_ip)
    hi_ip = b_ip.where(~swap, a_ip)
    lo_p = a_p.where(~swap, b_p)
    hi_p = b_p.where(~swap, a_p)
    out["flow"] = (lo_ip + ":" + lo_p.astype(str) + "-" + hi_ip + ":" + hi_p.astype(str)
                   + "/" + out["proto"])
    return out


def flows(df: pd.DataFrame) -> pd.DataFrame:
    """One row per conversation (5-tuple): packets, bytes, start, end and duration."""
    cols = ["flow", "proto", "app", "a", "b", "packets", "bytes", "start", "end", "duration_s"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    d = add_flow_ids(df)
    g = d.groupby("flow").agg(proto=("proto", "first"), app=("app", "first"),
                              a=("src", "first"), b=("dst", "first"),
                              packets=("ts", "size"), bytes=("length", "sum"),
                              start=("ts", "min"), end=("ts", "max")).reset_index()
    g["duration_s"] = (g["end"] - g["start"]).round(4)
    return g[cols].sort_values("bytes", ascending=False).reset_index(drop=True)


def top_talkers(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Hosts that sent the most bytes."""
    if df.empty:
        return pd.DataFrame(columns=["host", "packets", "bytes"])
    g = df.groupby("src").agg(packets=("ts", "size"), bytes=("length", "sum")).reset_index()
    return g.rename(columns={"src": "host"}).sort_values("bytes", ascending=False).head(n) \
        .reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    """Headline numbers for a capture."""
    if df.empty:
        return {"packets": 0, "bytes": 0, "duration_s": 0.0, "flows": 0, "hosts": 0,
                "tcp_connections": 0, "protocols": {}}
    syn = df[(df["proto"] == "TCP") & (df["tcp_flags"] == "S")]
    return {
        "packets": int(len(df)),
        "bytes": int(df["length"].sum()),
        "duration_s": round(float(df["ts"].max() - df["ts"].min()), 3),
        "flows": int(add_flow_ids(df)["flow"].nunique()),
        "hosts": int(pd.unique(pd.concat([df["src"], df["dst"]])).size),
        "tcp_connections": int(len(syn)),
        "protocols": dict(zip(*protocol_distribution(df)[["protocol", "packets"]]
                              .to_dict("list").values())),
    }
