from conftest import NS2_SAMPLE

from netmind.capture.ns2 import path_changes, read_trace, trace_links, trace_metrics, trace_records


def test_ignores_acks_and_routing_packets():
    ev = read_trace(str(NS2_SAMPLE))
    assert {"ack", "rtProtoDV"} <= set(ev["type"])
    recs = trace_records(ev)
    assert set(recs["proto"]) == {"TCP", "UDP"}
    assert set(recs["src"]) == {"n0", "n1"} and set(recs["dst"]) == {"n3"}


def test_congestion_shows_loss_and_delay():
    m = trace_metrics(str(NS2_SAMPLE), window=1.0)
    normal = m[m["t"] < 3]
    burst = m[(m["t"] >= 3) & (m["t"] < 6)]
    assert normal["loss_pct"].max() == 0
    assert burst["loss_pct"].min() > 20
    assert burst["latency_ms"].mean() > 2 * normal["latency_ms"].mean()


def test_link_failure_reroutes_via_n4():
    pc = path_changes(str(NS2_SAMPLE))
    tcp = pc[pc["fid"] == 1]["path"].tolist()
    assert tcp == ["n0-n2-n3", "n0-n2-n4-n3", "n0-n2-n3"]
    t_switch = pc[pc["path"] == "n0-n2-n4-n3"]["t"].iloc[0]
    assert 7.0 <= t_switch < 7.1
    links = trace_links(str(NS2_SAMPLE)).set_index(["a", "b"])
    assert links.loc[("n2", "n3"), "drops"] > 0 and links.loc[("n2", "n4"), "packets"] > 0
