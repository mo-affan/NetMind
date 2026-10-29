"""M1 Packet Capture: live capture and pcap reading with Scapy.

Live capture needs administrator rights (and Npcap on Windows). Only capture on
networks you own or have permission to monitor.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .records import guess_app, to_frame


def _flags(tcp) -> str:
    # Scapy prints flags in bit order F S R P A U E C, giving "S", "SA", "A", "PA", "FA", "R".
    """TCP flags as text: S, SA, A, PA, FA, R."""
    return str(tcp.flags)


def packet_to_record(pkt) -> dict | None:
    """Convert one Scapy packet to a NetMind record. Non-IP packets return None."""
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    from scapy.layers.dns import DNS

    if IP not in pkt:
        return None
    ip = pkt[IP]
    rec = {"ts": float(pkt.time), "src": ip.src, "dst": ip.dst, "length": int(ip.len or len(ip))}
    if TCP in pkt:
        t = pkt[TCP]
        rec.update(proto="TCP", sport=int(t.sport), dport=int(t.dport), tcp_flags=_flags(t),
                   seq=int(t.seq), ack=int(t.ack), payload_len=len(bytes(t.payload)))
    elif UDP in pkt:
        u = pkt[UDP]
        rec.update(proto="UDP", sport=int(u.sport), dport=int(u.dport),
                   payload_len=len(bytes(u.payload)))
    elif ICMP in pkt:
        ic = pkt[ICMP]
        rec.update(proto="ICMP", icmp_type=int(ic.type))
        if ic.type in (0, 8):
            rec.update(icmp_id=int(ic.id), icmp_seq=int(ic.seq))
    else:
        rec["proto"] = "OTHER"
    rec["app"] = guess_app(rec["proto"], rec.get("sport", 0), rec.get("dport", 0))
    if DNS in pkt:
        d = pkt[DNS]
        rec.update(app="DNS", dns_id=int(d.id), dns_qr=int(d.qr))
        if d.qd is not None:
            try:
                rec["dns_qname"] = d.qd.qname.decode(errors="ignore").rstrip(".")
            except AttributeError:
                pass
    return rec


def packets_to_frame(packets: Iterable) -> pd.DataFrame:
    """Converts Scapy packets to the packet table."""
    return to_frame([r for r in (packet_to_record(p) for p in packets) if r is not None])


def read_pcap(path: str) -> pd.DataFrame:
    """Read a .pcap / .pcapng file (for example one saved from Wireshark)."""
    from scapy.utils import rdpcap
    return packets_to_frame(rdpcap(path))


def live_capture(iface: str | None = None, count: int = 0, timeout: int = 30,
                 bpf: str | None = "ip", save_pcap: str | None = None) -> pd.DataFrame:
    """Capture packets from a network interface.

    count=0 means no packet limit (stops after `timeout` seconds).
    `bpf` is a Wireshark-style capture filter, e.g. "tcp port 80" or "icmp".
    """
    from scapy.sendrecv import sniff
    from scapy.utils import wrpcap
    pkts = sniff(iface=iface, count=count, timeout=timeout, filter=bpf)
    if save_pcap:
        wrpcap(save_pcap, pkts)
    return packets_to_frame(pkts)


def list_interfaces() -> list[str]:
    """Names of the network interfaces Scapy can capture on."""
    from scapy.all import get_if_list
    return list(get_if_list())
