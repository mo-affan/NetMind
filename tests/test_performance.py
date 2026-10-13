import math

from netmind.capture.records import to_frame
from netmind.performance import jitter_ms, retransmissions, rtt_samples, window_metrics


def _handshake(t, rtt, c="10.0.0.1", s="10.0.0.2", sport=5000):
    return [dict(ts=t, src=c, dst=s, sport=sport, dport=80, proto="TCP", tcp_flags="S", seq=100),
            dict(ts=t + rtt, src=s, dst=c, sport=80, dport=sport, proto="TCP", tcp_flags="SA",
                 seq=900, ack=101)]


def test_rtt_from_handshake_ping_dns():
    recs = _handshake(0.0, 0.050)
    recs += [dict(ts=1.0, src="10.0.0.1", dst="10.0.0.254", proto="ICMP", icmp_type=8, icmp_id=1, icmp_seq=1),
             dict(ts=1.004, src="10.0.0.254", dst="10.0.0.1", proto="ICMP", icmp_type=0, icmp_id=1, icmp_seq=1),
             dict(ts=2.0, src="10.0.0.1", dst="8.8.8.8", sport=6000, dport=53, proto="UDP", dns_id=7, dns_qr=0),
             dict(ts=2.03, src="8.8.8.8", dst="10.0.0.1", sport=53, dport=6000, proto="UDP", dns_id=7, dns_qr=1)]
    r = rtt_samples(to_frame(recs)).set_index("kind")["rtt_ms"]
    assert math.isclose(r["tcp_handshake"], 50, abs_tol=0.01)
    assert math.isclose(r["icmp_echo"], 4, abs_tol=0.01)
    assert math.isclose(r["dns"], 30, abs_tol=0.01)


def test_syn_ack_must_match_sequence_number():
    recs = _handshake(0.0, 0.05)
    recs[1]["ack"] = 555  # not seq+1: not a reply to this SYN
    assert rtt_samples(to_frame(recs)).empty


def test_retransmission_detected():
    seg = dict(src="10.0.0.2", dst="10.0.0.1", sport=80, dport=5000, proto="TCP", tcp_flags="A",
               seq=1000, payload_len=1400)
    df = to_frame([{**seg, "ts": 0.0}, {**seg, "ts": 0.3}, {**seg, "ts": 0.4, "seq": 2400}])
    assert len(retransmissions(df)) == 1


def test_jitter():
    assert jitter_ms([20, 25, 22]) == 4.0
    assert jitter_ms([20]) == 0.0


def test_congestion_window_has_higher_latency_and_loss(demo):
    df, events = demo
    m = window_metrics(df, 10)
    cong_start, cong_end, _ = events[0]
    cong = m[(m["t"] >= cong_start) & (m["t"] < cong_end)]
    normal = m[m["t"] < cong_start]
    assert cong["latency_ms"].mean() > 3 * normal["latency_ms"].mean()
    assert cong["loss_pct"].mean() > 2 and normal["loss_pct"].max() == 0
    assert normal["jitter_ms"].mean() < cong["jitter_ms"].mean()
