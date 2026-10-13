"""The common packet-record format used by every NetMind module.

Every packet, whether captured live, read from a pcap file or generated for the
demo, becomes one row with the columns below. Downstream modules only depend on
this table, never on Scapy, so they can be tested without capture rights.
"""
from __future__ import annotations

import pandas as pd

COLUMNS = [
    "ts",           # capture time, seconds (float)
    "src", "dst",   # IP addresses (or NS2 node names)
    "sport", "dport",  # ports, 0 when the protocol has none
    "proto",        # TCP, UDP, ICMP, OTHER
    "app",          # DNS, HTTP, HTTPS or "" (application protocol guessed from ports)
    "length",       # bytes on the wire (IP length)
    "payload_len",  # transport payload bytes
    "tcp_flags",    # e.g. "S", "SA", "A", "PA", "FA", "R"
    "seq", "ack",   # TCP sequence / acknowledgement numbers
    "icmp_type",    # 8 = echo request, 0 = echo reply, -1 when not ICMP
    "icmp_id", "icmp_seq",
    "dns_id",       # DNS transaction id, -1 when not DNS
    "dns_qr",       # 0 = query, 1 = response, -1 when not DNS
    "dns_qname",
]

DEFAULTS = {
    "sport": 0, "dport": 0, "proto": "OTHER", "app": "", "length": 0, "payload_len": 0,
    "tcp_flags": "", "seq": 0, "ack": 0, "icmp_type": -1, "icmp_id": -1, "icmp_seq": -1,
    "dns_id": -1, "dns_qr": -1, "dns_qname": "",
}

APP_PORTS = {53: "DNS", 80: "HTTP", 443: "HTTPS"}


def guess_app(proto: str, sport: int, dport: int) -> str:
    """Application protocol from well-known ports (DNS 53, HTTP 80, HTTPS 443)."""
    if proto not in ("TCP", "UDP"):
        return ""
    for port in (dport, sport):
        if port in APP_PORTS:
            return APP_PORTS[port]
    return ""


def to_frame(records: list[dict]) -> pd.DataFrame:
    """Turn a list of record dicts into a DataFrame with every column present, sorted by time."""
    rows = [{**DEFAULTS, **r} for r in records]
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return df
    int_cols = ["sport", "dport", "length", "payload_len", "seq", "ack", "icmp_type",
                "icmp_id", "icmp_seq", "dns_id", "dns_qr"]
    df[int_cols] = df[int_cols].fillna(-1).astype("int64")
    df["ts"] = df["ts"].astype(float)
    return df.sort_values("ts", kind="stable").reset_index(drop=True)
