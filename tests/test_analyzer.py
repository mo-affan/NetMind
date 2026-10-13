from netmind.analyzer import flows, protocol_distribution, summary, top_talkers
from netmind.capture.records import to_frame


def test_protocol_distribution(demo):
    df, _ = demo
    p = protocol_distribution(df)
    assert {"ICMP", "HTTPS", "HTTP", "DNS", "TCP"} <= set(p["protocol"])
    assert abs(p["share_pct"].sum() - 100) < 0.5
    assert p["packets"].sum() == len(df)


def test_flows_merge_both_directions():
    df = to_frame([
        dict(ts=0, src="10.0.0.1", dst="10.0.0.2", sport=5000, dport=80, proto="TCP", length=60),
        dict(ts=1, src="10.0.0.2", dst="10.0.0.1", sport=80, dport=5000, proto="TCP", length=1500),
        dict(ts=2, src="10.0.0.1", dst="10.0.0.3", sport=5001, dport=53, proto="UDP", length=70),
    ])
    f = flows(df)
    assert len(f) == 2
    web = f[f["proto"] == "TCP"].iloc[0]
    assert web["packets"] == 2 and web["bytes"] == 1560 and web["duration_s"] == 1


def test_summary_and_talkers(demo):
    df, _ = demo
    s = summary(df)
    assert s["packets"] == len(df) and s["hosts"] == 9
    assert top_talkers(df, 3).iloc[0]["bytes"] >= top_talkers(df, 3).iloc[1]["bytes"]
