import pytest

from netmind.capture.records import COLUMNS, guess_app, to_frame


def test_records_have_all_columns(demo):
    df, _ = demo
    assert list(df.columns) == COLUMNS
    assert df["ts"].is_monotonic_increasing
    assert set(df["proto"]) == {"TCP", "UDP", "ICMP"}


def test_guess_app():
    assert guess_app("UDP", 50000, 53) == "DNS"
    assert guess_app("TCP", 443, 50000) == "HTTPS"
    assert guess_app("TCP", 50000, 80) == "HTTP"
    assert guess_app("ICMP", 0, 0) == ""


def test_pcap_roundtrip(tmp_path, demo):
    pytest.importorskip("scapy")
    from netmind.capture.sniffer import read_pcap
    from netmind.capture.synthetic import generate_scenario, to_pcap
    recs, _ = generate_scenario(duration=20)
    path = tmp_path / "demo.pcap"
    to_pcap(recs, str(path))
    back = read_pcap(str(path))
    orig = to_frame(recs)
    assert len(back) == len(orig)
    cols = ["src", "dst", "sport", "dport", "proto", "tcp_flags", "seq", "ack", "icmp_type",
            "icmp_seq", "dns_id", "dns_qr"]
    assert (back[cols].reset_index(drop=True) == orig[cols].reset_index(drop=True)).all().all()
    tcp = orig["proto"] == "TCP"
    assert (back.loc[tcp, "length"].to_numpy() == orig.loc[tcp, "length"].to_numpy()).all()
    assert abs(back["ts"].iloc[-1] - orig["ts"].iloc[-1]) < 1e-3
