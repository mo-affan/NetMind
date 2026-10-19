"""TCP connection outcomes, DNS insights, host inventory and the health score."""
import pandas as pd
import pytest

from netmind.analyzer.insights import (connection_summary, dns_summary, health_summary, host_inventory,
                                       ip_scope, tcp_connections, window_health)
from netmind.capture.records import to_frame


def _tcp(ts, src, dst, sport, dport, flags, length=60):
    return dict(ts=ts, src=src, dst=dst, sport=sport, dport=dport, proto="TCP", tcp_flags=flags,
                length=length)


def test_connection_states_from_handshakes():
    c, s = "10.0.0.2", "10.0.0.9"
    recs = [
        # established and closed
        _tcp(0.00, c, s, 5000, 80, "S"), _tcp(0.02, s, c, 80, 5000, "SA"), _tcp(0.03, c, s, 5000, 80, "A"),
        _tcp(0.10, c, s, 5000, 80, "FA"),
        # refused
        _tcp(1.00, c, s, 5001, 22, "S"), _tcp(1.01, s, c, 22, 5001, "RA"),
        # unanswered (SYN retransmitted once)
        _tcp(2.00, c, s, 5002, 23, "S"), _tcp(3.00, c, s, 5002, 23, "S"),
        # established, then reset
        _tcp(4.00, c, s, 5003, 443, "S"), _tcp(4.05, s, c, 443, 5003, "SA"), _tcp(4.50, s, c, 443, 5003, "R"),
    ]
    conns = tcp_connections(to_frame(recs)).set_index("sport")
    assert conns.loc[80, "state"] == "established" and conns.loc[80, "closed"]
    assert conns.loc[80, "handshake_ms"] == pytest.approx(20.0)
    assert conns.loc[22, "state"] == "refused"
    assert conns.loc[23, "state"] == "unanswered"
    assert conns.loc[443, "state"] == "reset"
    assert conns.loc[80, "service"] == "HTTP" and conns.loc[23, "service"] == "Telnet"
    summ = connection_summary(conns.reset_index())
    assert summ["attempts"] == 4 and summ["success_pct"] == 50.0
    assert summ["likely_scanners"] == []  # 2 failures is not a scan


def test_demo_scan_is_found_from_connections(demo):
    df, _ = demo
    conns = tcp_connections(df)
    summ = connection_summary(conns)
    assert summ["refused"] >= 900                     # the scan's 1000 SYNs answered with RST
    assert summ["likely_scanners"] == ["192.168.1.66"]
    normal = conns[conns["client"] != "192.168.1.66"]
    assert (normal["state"] == "established").all()   # ordinary browsing always connects
    inv = host_inventory(df, conns).set_index("host")
    assert inv.loc["192.168.1.66", "role"] == "likely scanner"
    assert inv.loc["8.8.8.8", "services"] == "DNS 53" and inv.loc["8.8.8.8", "scope"] == "public"
    assert "TCP 443 (HTTPS)" in inv.loc["142.250.183.14", "services"]
    assert inv.loc["192.168.1.10", "role"] == "client" and inv.loc["192.168.1.10", "scope"] == "private"
    assert "ICMP echo" in inv.loc["192.168.1.1", "services"]


def test_dns_matching_and_response_time():
    recs = [dict(ts=0.0, src="10.0.0.2", dst="8.8.8.8", sport=4000, dport=53, proto="UDP", app="DNS",
                 dns_id=7, dns_qr=0, dns_qname="example.com."),
            dict(ts=0.03, src="8.8.8.8", dst="10.0.0.2", sport=53, dport=4000, proto="UDP", app="DNS",
                 dns_id=7, dns_qr=1, dns_qname="example.com."),
            dict(ts=1.0, src="10.0.0.2", dst="8.8.8.8", sport=4001, dport=53, proto="UDP", app="DNS",
                 dns_id=8, dns_qr=0, dns_qname="lost.example")]
    d = dns_summary(to_frame(recs))
    assert d["queries"] == 2 and d["answered"] == 1 and d["unanswered"] == 1
    assert d["response_ms_median"] == pytest.approx(30.0)
    names = {r["name"]: r for r in d["top_domains"]}
    assert names["lost.example"]["unanswered"] == 1 and names["example.com"]["queries"] == 1


def test_ip_scope():
    assert ip_scope("192.168.1.5") == "private" and ip_scope("8.8.8.8") == "public"
    assert ip_scope("127.0.0.1") == "loopback" and ip_scope("224.0.0.251") == "multicast"
    assert ip_scope("n3") == "simulated"


def test_health_penalties():
    m = pd.DataFrame({"t": [0, 2, 4, 6], "latency_ms": [20, 40, 80, 200], "loss_pct": [0, 0, 2.5, 10]})
    s = pd.DataFrame({"is_anomaly": [False, False, False, True]})
    h = window_health(m, s, {"latency_ms": 20})
    assert list(h["health"]) == [100.0, pytest.approx(100 - 40 / 3, abs=0.1), 40.0, 0.0]
    summ = health_summary(h)
    assert summ["worst"] == 0.0 and summ["worst_t"] == 6 and summ["grade"] == "Poor"


def test_health_on_demo_and_normal_runs(db, demo):
    from netmind.capture.synthetic import generate_scenario
    from netmind.pipeline import analyze_packets, get_state
    rid = analyze_packets(demo[0], "demo", "synthetic", db, train_until=60, save_model=False)
    st = get_state(db, rid)
    assert 60 < st["health"]["score"] < 95 and 70 <= st["health"]["worst_t"] < 100  # congestion
    assert st["connections"]["likely_scanners"] == ["192.168.1.66"]
    assert st["dns"]["queries"] > 100
    assert "health" in db.load("metrics", rid).columns
    assert len(db.load("hosts", rid)) == st["summary"]["hosts"]
    recs, _ = generate_scenario(events=[])
    rid2 = analyze_packets(to_frame(recs), "normal", "synthetic", db, train_until=60, save_model=False)
    assert get_state(db, rid2)["health"]["grade"] == "Good"


def test_copilot_answers_insight_questions(db, demo):
    from netmind.copilot import Copilot
    from netmind.pipeline import analyze_packets, get_state
    rid = analyze_packets(demo[0], "demo", "synthetic", db, train_until=60, save_model=False)
    st = get_state(db, rid)
    c = Copilot(backend="offline")
    conn = c.ask("Which hosts failed to connect?", st)["answer"]
    assert "192.168.1.66" in conn and "refused" in conn
    assert "Health score" in c.ask("How healthy is my network?", st)["answer"]
    assert "DNS" in c.ask("Are DNS lookups slow?", st)["answer"]
    prompt = c.ask("Why is the network slow?", st)["prompt"]
    assert "Health score" in prompt and "TCP connections" in prompt and "DNS:" in prompt
