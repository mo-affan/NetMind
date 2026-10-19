"""NS2 trace parsing. Uses tests/data/sample_ns2.tr, a SYNTHETIC trace in ns-2 wired trace
format (made by tests/make_ns2_sample.py), plus small hand-written traces. NS2 is not needed."""
import subprocess
import sys

import pytest
from conftest import NS2_SAMPLE, ROOT

from netmind.capture.ns2 import (flow_summary, packet_table, path_changes, read_link_events,
                                 read_trace, trace_links, trace_metrics, trace_records)

S = str(NS2_SAMPLE)


def write(tmp_path, lines, name="t.tr"):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n")
    return str(p)


# ---- format handling ----------------------------------------------------------------
def test_ignores_acks_routing_and_junk(tmp_path):
    path = write(tmp_path, [
        "+ 0.1 0 2 tcp 1040 ------- 1 0.0 3.0 0 0",
        "r 0.2 3 2 ack 40 ------- 1 3.0 0.0 0 1",
        "r 0.3 2 4 rtProtoDV 7 ------- 0 2.1 4.1 -1 2",
        "v 0.4 eval {set sim_annotation {hello}}",
        "this line is not a trace event",
        "+ 0.5 0 2 tcp notanumber ------- 1 0.0 3.0 0 3",
    ])
    ev = read_trace(path)
    assert len(ev) == 3  # tcp, ack, rtProtoDV (junk and malformed skipped)
    assert list(packet_table(ev)["type"]) == ["tcp"]


def test_sample_contains_expected_event_kinds():
    ev = read_trace(S)
    assert {"+", "-", "r", "d"} == set(ev["ev"])
    assert {"tcp", "cbr", "ack", "rtProtoDV"} <= set(ev["type"])
    recs = trace_records(ev)
    assert set(recs["proto"]) == {"TCP", "UDP"}
    assert set(recs["src"]) == {"n0", "n1"} and set(recs["dst"]) == {"n3"}


def test_link_status_lines_are_read_when_present(tmp_path):
    path = write(tmp_path, ["v 7 link-down 7 2 3", "v 8.5 link-up 8.5 3 2",
                            "+ 0.1 0 2 tcp 1040 ------- 1 0.0 3.0 0 0"])
    le = read_link_events(path)
    assert le.to_dict("records") == [{"t": 7.0, "status": "down", "link": "n2-n3"},
                                     {"t": 8.5, "status": "up", "link": "n2-n3"}]
    assert read_link_events(S).empty


# ---- definitions ---------------------------------------------------------------------
def test_definitions_delivered_dropped_in_flight_retransmission(tmp_path):
    path = write(tmp_path, [
        # pkt 0: delivered, one-way delay 50 ms
        "+ 1.000 0 2 tcp 1040 ------- 1 0.0 3.0 0 0", "r 1.020 0 2 tcp 1040 ------- 1 0.0 3.0 0 0",
        "+ 1.020 2 3 tcp 1040 ------- 1 0.0 3.0 0 0", "r 1.050 2 3 tcp 1040 ------- 1 0.0 3.0 0 0",
        # pkt 1: dropped at n2's queue for n2-n3
        "+ 1.100 0 2 tcp 1040 ------- 1 0.0 3.0 1 1", "r 1.120 0 2 tcp 1040 ------- 1 0.0 3.0 1 1",
        "+ 1.120 2 3 tcp 1040 ------- 1 0.0 3.0 1 1", "d 1.120 2 3 tcp 1040 ------- 1 0.0 3.0 1 1",
        # pkt 2: retransmission of seq 1, delivered, delay 70 ms
        "+ 1.300 0 2 tcp 1040 ------- 1 0.0 3.0 1 2", "r 1.330 0 2 tcp 1040 ------- 1 0.0 3.0 1 2",
        "+ 1.330 2 3 tcp 1040 ------- 1 0.0 3.0 1 2", "r 1.370 2 3 tcp 1040 ------- 1 0.0 3.0 1 2",
        # pkt 3: still in flight when the trace ends
        "+ 1.900 0 2 tcp 1040 ------- 1 0.0 3.0 2 3",
    ])
    pk = packet_table(path).set_index("pkt")
    assert list(pk["fate"]) == ["delivered", "dropped", "delivered", "in_flight"]
    assert pk.loc[0, "delay_ms"] == pytest.approx(50) and pk.loc[2, "delay_ms"] == pytest.approx(70)
    assert list(pk["retransmission"]) == [False, False, True, False]
    assert pk.loc[1, "drop_link"] == "n2-n3"
    m = trace_metrics(path, window=1.0).set_index("t").loc[1.0]
    # loss excludes the in-flight packet: 1 dropped / (2 delivered + 1 dropped)
    assert m["packets"] == 4 and m["in_flight"] == 1
    assert m["loss_pct"] == pytest.approx(33.33, abs=0.01)
    assert m["latency_ms"] == pytest.approx(60) and m["retransmissions"] == 1
    assert m["throughput_mbps"] == pytest.approx(2 * 1040 * 8 / 1e6, abs=1e-4)
    assert m["jitter_ms"] == pytest.approx(20)


def test_jitter_is_per_flow(tmp_path):
    # flow 1 has constant 10 ms delay, flow 2 constant 100 ms, interleaved in time:
    # mixing flows would report ~90 ms jitter; per flow it is 0.
    lines = []
    pid = 0
    for i in range(4):
        for fid, src, delay in ((1, 0, 0.010), (2, 1, 0.100)):
            t = 1 + i * 0.05 + fid * 0.001
            lines += [f"+ {t:.4f} {src} 3 cbr 500 ------- {fid} {src}.0 3.0 {i} {pid}",
                      f"r {t + delay:.4f} {src} 3 cbr 500 ------- {fid} {src}.0 3.0 {i} {pid}"]
            pid += 1
    m = trace_metrics(write(tmp_path, lines), window=1.0).set_index("t").loc[1.0]
    assert m["jitter_ms"] == pytest.approx(0, abs=1e-6)


# ---- scenario behaviour on the sample -------------------------------------------------
def test_congestion_shows_loss_and_delay():
    m = trace_metrics(S, window=1.0)
    normal = m[(m["t"] >= 0) & (m["t"] < 3)]
    burst = m[(m["t"] >= 3) & (m["t"] < 6)]
    assert normal["dropped"].sum() == 0
    assert burst["loss_pct"].min() > 10
    assert burst["latency_ms"].mean() > 2 * normal["latency_ms"].mean()


def test_link_failure_drops_retransmits_and_reroutes_via_n4():
    pc = path_changes(S)
    assert pc[pc["fid"] == 1]["path"].tolist() == ["n0-n2-n3", "n0-n2-n4-n3", "n0-n2-n3"]
    t_switch = pc[pc["path"] == "n0-n2-n4-n3"]["t"].iloc[0]
    assert 7.0 <= t_switch < 7.1
    fs = flow_summary(S).set_index("type")
    assert fs.loc["tcp", "retransmissions"] > 0 and fs.loc["tcp", "dropped"] > 0
    links = trace_links(S).set_index(["a", "b"])
    assert links.loc[("n2", "n3"), "drops"] > 0 and links.loc[("n2", "n4"), "packets"] > 0


# ---- the standard-library lab checker agrees with the pandas parser ---------------------
def test_check_trace_matches_parser():
    out = subprocess.run([sys.executable, "-I", str(ROOT / "ns2" / "check_trace.py"), S],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("[PASS]") == 5
    fs = flow_summary(S)
    for r in fs.itertuples():
        assert f"{r.sent:>6} {r.delivered:>6} {r.dropped:>5} {r.loss_pct:>6.2f}" in out.stdout


def test_parse_trace_cli_runs(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "ns2" / "parse_trace.py"), S,
                          "--out", str(tmp_path / "m.csv")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "n0-n2-n4-n3" in out.stdout and (tmp_path / "m.csv").exists()


def test_tcl_scenario_static_checks():
    sys.path.insert(0, str(ROOT / "tests"))
    from check_tcl_static import check
    assert check() == []


def test_compare_traces_cli_runs():
    out = subprocess.run([sys.executable, str(ROOT / "ns2" / "compare_traces.py"), S, S],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    for phase in ("normal", "UDP burst", "link down"):
        assert phase in out.stdout


def test_tcl_queue_option_keeps_droptail_default():
    src = (ROOT / "ns2" / "netmind_scenario.tcl").read_text()
    assert 'set qtype "DropTail"' in src and "$ns duplex-link $n2 $n3 1Mb 20ms $qtype" in src
    assert src.count("DropTail") >= 5  # access and backup links stay DropTail
