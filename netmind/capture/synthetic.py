"""Synthetic demo traffic with known problems at known times.

Used for the demo and the tests when live capture is not possible. The scenario
is a small LAN (three clients, a gateway) talking to DNS and web servers, with
four events injected:

    0-70 s     normal browsing, DNS lookups and pings
    70-100 s   congestion: RTT x4, more jitter, TCP retransmissions, ping loss
    120-128 s  port scan: 192.168.1.66 sends SYNs to ~1000 ports of 192.168.1.10
    150-158 s  ping flood: 192.168.1.66 floods the gateway with ICMP echo requests

Seed 7 (the default) is the fixed demo above, used by the slides and the tests. Any other
seed builds a different scenario: the seed picks when each problem starts and how long it
lasts, their order, how strong they are, which host attacks and which client is scanned
(see `scenario_for`). Every seed is reproducible: the same seed gives the same traffic.

`generate_scenario()` returns (records, events). `to_pcap()` writes the same
traffic as a real .pcap file using Scapy, so it can be opened in Wireshark.
"""
from __future__ import annotations

import random

CLIENTS = ["192.168.1.10", "192.168.1.11", "192.168.1.12"]
GATEWAY = "192.168.1.1"
ATTACKER = "192.168.1.66"
DNS_SERVER = "8.8.8.8"
WEB_SERVERS = {"93.184.216.34": ("example.com", 80), "142.250.183.14": ("google.com", 443),
               "151.101.1.69": ("stackoverflow.com", 443)}

EVENTS = [
    (70.0, 100.0, "congestion"),
    (120.0, 128.0, "port_scan"),
    (150.0, 158.0, "ping_flood"),
]

IP_H, TCP_H, UDP_H, ICMP_H = 20, 20, 8, 8

DEMO_SEED = 7
# Strength of each problem in the fixed demo (seed 7).
DEMO_PARAMS = {"rtt_factor": 4.0, "loss": 0.07, "ping_loss": 0.15, "scan_ports": 1000,
               "flood_pps": 250, "attacker": ATTACKER, "victim": CLIENTS[0]}


def scenario_for(seed: int, duration: float = 180.0) -> tuple[list[tuple], dict]:
    """The problems to inject for a seed: (events, params). Seed 7 is the fixed demo."""
    if seed == DEMO_SEED:
        return list(EVENTS), dict(DEMO_PARAMS)
    r = random.Random(seed * 7919 + 13)  # separate from the traffic's random numbers
    params = {"rtt_factor": round(r.uniform(3.0, 6.0), 2), "loss": round(r.uniform(0.05, 0.12), 3),
              "ping_loss": round(r.uniform(0.10, 0.25), 3), "scan_ports": r.randrange(400, 1501, 50),
              "flood_pps": r.randrange(150, 401, 10),
              "attacker": f"192.168.1.{r.choice([n for n in range(20, 250) if n not in (66,)])}",
              "victim": r.choice(CLIENTS)}
    # problems start after the normal baseline (first third, at most 60 s) and end before the close
    lo = min(60.0, duration * 0.33) + 4.0
    hi = duration - 4.0
    names = ["congestion", "port_scan", "ping_flood"]
    r.shuffle(names)
    want = {"congestion": r.uniform(14, 36), "port_scan": r.uniform(6, 12), "ping_flood": r.uniform(6, 12)}
    gaps = [r.uniform(8, 30) for _ in names]
    room = hi - lo
    need = sum(want.values()) + sum(gaps)
    k = min(1.0, room / need) if need > 0 else 1.0
    spare = max(0.0, room - need * k)  # spread spare time before, between and after
    t = lo + r.uniform(0, spare * 0.5)
    events = []
    for name, gap in zip(names, gaps):
        length = max(4.0, round(want[name] * k / 2) * 2)  # whole 2 s windows, at least 4 s
        start = round(t / 2) * 2
        if start + length > hi:
            break  # a short capture holds fewer problems
        events.append((float(start), float(start + length), name))
        # at least 8 s of normal traffic between problems, so they stay separate incidents
        t = start + length + max(8.0, gap * k) + r.uniform(0, spare * 0.25)
    return sorted(events), params


def _event_at(t: float, events=None) -> str:
    """Which injected problem (if any) is active at time t."""
    for start, end, name in (EVENTS if events is None else events):
        if start <= t < end:
            return name
    return "normal"


class _Gen:
    """The traffic generator: keeps the random seed, records and client ports."""
    def __init__(self, seed: int, events=None, params: dict | None = None):
        """Seeds the random generator so every run is reproducible."""
        self.events = EVENTS if events is None else events
        self.p = dict(DEMO_PARAMS if params is None else params)
        self.r = random.Random(seed)
        self.recs: list[dict] = []
        self.ports = {c: 49152 for c in CLIENTS}

    # --- helpers -------------------------------------------------------------
    def rtt(self, t: float, base: float, jitter: float) -> float:
        """Round-trip time in seconds; several times larger and noisier during congestion."""
        if _event_at(t, self.events) == "congestion":
            f = self.p["rtt_factor"]
            base, jitter = base * f, jitter * f
        return max(0.0005, self.r.gauss(base, jitter))

    def loss(self, t: float, p_congested: float | None = None) -> bool:
        """Drops a packet at random during congestion (7% in the demo)."""
        p = self.p["loss"] if p_congested is None else p_congested
        return _event_at(t, self.events) == "congestion" and self.r.random() < p

    def tcp(self, ts, src, dst, sport, dport, flags, seq, ack, payload=0):
        """Adds one TCP packet record."""
        self.recs.append(dict(ts=ts, src=src, dst=dst, sport=sport, dport=dport, proto="TCP",
                              tcp_flags=flags, seq=seq % 2**32, ack=ack % 2**32,
                              payload_len=payload, length=IP_H + TCP_H + payload))

    def next_port(self, c):
        """Next ephemeral client port (49152 upwards)"""
        self.ports[c] = 49152 + (self.ports[c] - 49151) % 16000
        return self.ports[c]

    # --- traffic types ---------------------------------------------------------
    def dns(self, t, client, name):
        """A DNS query and its response, same transaction id."""
        qid = self.r.randrange(65536)
        sport = self.next_port(client)
        q = 17 + len(name)
        self.recs.append(dict(ts=t, src=client, dst=DNS_SERVER, sport=sport, dport=53, proto="UDP",
                              dns_id=qid, dns_qr=0, dns_qname=name, payload_len=q,
                              length=IP_H + UDP_H + q))
        if self.loss(t):
            return
        a = q + 16
        self.recs.append(dict(ts=t + self.rtt(t, 0.028, 0.004), src=DNS_SERVER, dst=client,
                              sport=53, dport=sport, proto="UDP", dns_id=qid, dns_qr=1,
                              dns_qname=name, payload_len=a, length=IP_H + UDP_H + a))

    def web(self, t, client, server):
        """A full TCP connection: handshake, request, response, close."""
        _, port = WEB_SERVERS[server]
        sport = self.next_port(client)
        c_isn, s_isn = self.r.randrange(2**32), self.r.randrange(2**32)
        rtt = self.rtt(t, 0.045, 0.006)
        self.tcp(t, client, server, sport, port, "S", c_isn, 0)
        t1 = t + rtt
        self.tcp(t1, server, client, port, sport, "SA", s_isn, c_isn + 1)
        t2 = t1 + 0.0004
        self.tcp(t2, client, server, sport, port, "A", c_isn + 1, s_isn + 1)
        req = self.r.randint(300, 600)
        self.tcp(t2 + 0.0002, client, server, sport, port, "PA", c_isn + 1, s_isn + 1, req)
        # response: several full segments sent back to back
        n = self.r.randint(4, 14)
        ts = t2 + self.rtt(t, 0.045, 0.006)
        off = 0
        for i in range(n):
            size = 1400 if i < n - 1 else self.r.randint(200, 1400)
            seq = s_isn + 1 + off
            self.tcp(ts, server, client, port, sport, "PA" if i == n - 1 else "A", seq,
                     c_isn + 1 + req, size)
            if self.loss(ts):  # lost: retransmitted after a timeout
                self.tcp(ts + 0.2 + self.rtt(ts, 0.045, 0.006), server, client, port, sport,
                         "A", seq, c_isn + 1 + req, size)
            off += size
            ts += 0.0012 * (3 if _event_at(ts, self.events) == "congestion" else 1) + self.r.random() * 0.0005
        ack_t = ts + 0.0005
        self.tcp(ack_t, client, server, sport, port, "A", c_isn + 1 + req, s_isn + 1 + off)
        fin = ack_t + self.r.uniform(0.05, 0.4)
        self.tcp(fin, client, server, sport, port, "FA", c_isn + 1 + req, s_isn + 1 + off)
        self.tcp(fin + rtt, server, client, port, sport, "FA", s_isn + 1 + off, c_isn + 2 + req)
        self.tcp(fin + rtt + 0.0003, client, server, sport, port, "A", c_isn + 2 + req, s_isn + 2 + off)

    def ping(self, t, src, dst, ident, seq, base=0.003):
        """An ICMP echo request and (unless lost) its reply."""
        self.recs.append(dict(ts=t, src=src, dst=dst, proto="ICMP", icmp_type=8, icmp_id=ident,
                              icmp_seq=seq, payload_len=56, length=IP_H + ICMP_H + 56))
        if self.loss(t, self.p["ping_loss"]):
            return
        self.recs.append(dict(ts=t + self.rtt(t, base, base * 0.2), src=dst, dst=src, proto="ICMP",
                              icmp_type=0, icmp_id=ident, icmp_seq=seq, payload_len=56,
                              length=IP_H + ICMP_H + 56))


def generate_scenario(duration: float = 180.0, seed: int = 7,
                      events: list[tuple] | None = None) -> tuple[list[dict], list[tuple]]:
    """Return (records, events). Records are dicts in the netmind.capture.records format.

    events: (start_s, end_s, name) to inject, with names "congestion", "port_scan",
    "ping_flood". Default: the seed's scenario (seed 7 = EVENTS, the fixed demo; see
    scenario_for). Pass [] for normal traffic only.
    """
    planned, params = scenario_for(seed, duration)
    events = planned if events is None else list(events)
    g = _Gen(seed, events, params)
    servers = list(WEB_SERVERS)
    # normal browsing for each client: a DNS lookup then a web request, every ~1.5 s
    for ci, c in enumerate(CLIENTS):
        t = 0.3 * ci
        while t < duration:
            server = g.r.choice(servers)
            g.dns(t, c, WEB_SERVERS[server][0])
            g.web(t + 0.06, c, server)
            t += g.r.uniform(0.8, 2.2)
    # each client pings the gateway every 2 s
    for ci, c in enumerate(CLIENTS):
        for k, t in enumerate(range(0, int(duration), 2)):
            g.ping(t + 0.11 * ci, c, GATEWAY, ident=100 + ci, seq=k)
    # port scan: SYN to ports 1..N (1000 in the demo), target answers RST-ACK
    attacker, victim, n_ports, pps = params["attacker"], params["victim"], params["scan_ports"], params["flood_pps"]
    for start, end, name in events:
        if name == "port_scan":
            for i, port in enumerate(range(1, n_ports + 1)):
                t = start + i * (end - start) / n_ports
                isn = g.r.randrange(2**32)
                g.tcp(t, attacker, victim, 40000 + i % 50, port, "S", isn, 0)
                g.tcp(t + 0.0008, victim, attacker, port, 40000 + i % 50, "RA", 0, isn + 1)
        elif name == "ping_flood":  # echo requests to the gateway (250 per second in the demo)
            for i in range(int((end - start) * pps)):
                g.ping(start + i / pps, attacker, GATEWAY, ident=999, seq=i)
    recs = sorted((r for r in g.recs if r["ts"] < duration), key=lambda r: r["ts"])
    base = 1_760_000_000.0  # an absolute epoch so times look like real captures
    for r in recs:
        r["ts"] = round(base + r["ts"], 6)
        r.setdefault("app", "")
    from .records import guess_app
    for r in recs:
        if not r["app"]:
            r["app"] = guess_app(r["proto"], r.get("sport", 0), r.get("dport", 0))
    return recs, [(base + s, base + e, name) for s, e, name in events if s < duration]


def to_pcap(records: list[dict], path: str) -> None:
    """Write records as real packets (needs Scapy). Opens in Wireshark."""
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    from scapy.layers.dns import DNS, DNSQR, DNSRR
    from scapy.packet import Raw
    from scapy.utils import wrpcap

    pkts = []
    for r in records:
        ip = IP(src=r["src"], dst=r["dst"])
        p = r.get("payload_len", 0)
        if r["proto"] == "TCP":
            pkt = ip / TCP(sport=r["sport"], dport=r["dport"], flags=r["tcp_flags"],
                           seq=r["seq"], ack=r["ack"])
            if p:
                pkt = pkt / Raw(b"x" * p)
        elif r["proto"] == "UDP" and r.get("dns_id", -1) >= 0:
            qd = DNSQR(qname=r.get("dns_qname") or "example.com")
            if r["dns_qr"] == 1:
                dns = DNS(id=r["dns_id"], qr=1, qd=qd,
                          an=DNSRR(rrname=qd.qname, rdata="93.184.216.34"))
            else:
                dns = DNS(id=r["dns_id"], qr=0, rd=1, qd=qd)
            pkt = ip / UDP(sport=r["sport"], dport=r["dport"]) / dns
        elif r["proto"] == "UDP":
            pkt = ip / UDP(sport=r["sport"], dport=r["dport"]) / Raw(b"x" * p)
        elif r["proto"] == "ICMP":
            pkt = ip / ICMP(type=r["icmp_type"], id=max(r.get("icmp_id", 0), 0),
                            seq=max(r.get("icmp_seq", 0), 0)) / Raw(b"x" * p)
        else:
            continue
        pkt.time = r["ts"]
        pkts.append(pkt)
    wrpcap(path, pkts)
