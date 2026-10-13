import pytest
from conftest import NS2_SAMPLE

from netmind.pipeline import analyze_ns2, analyze_packets, get_state


def test_pipeline_saves_everything(db, demo):
    df, _ = demo
    rid = analyze_packets(df, "demo", "demo", db, train_until=60, save_model=False)
    for t in ("metrics", "anomalies", "incidents", "nodes", "links", "flows", "protocols", "rtt"):
        assert not db.load(t, rid).empty, t
    st = get_state(db, rid)
    assert len(st["incidents"]) == 3 and st["baseline"]["latency_ms"] > 0


def test_ns2_run_has_congestion_and_reroute(db):
    rid = analyze_ns2(str(NS2_SAMPLE), db=db)
    st = get_state(db, rid)
    assert [i["type"] for i in st["incidents"]] == ["congestion", "reroute"]
    assert any(r["path"] == "n0-n2-n4-n3" for r in st["routes"])


def test_packet_and_ns2_runs_share_one_database(db, demo):
    df, _ = demo
    a = analyze_packets(df, "demo", "demo", db, train_until=60, save_model=False)
    b = analyze_ns2(str(NS2_SAMPLE), db=db)
    assert set(db.runs()["id"]) == {a, b}
    assert "dropped" in db.load("metrics", b).columns
    assert "retransmissions" in db.load("metrics", a).columns


def test_api(tmp_path, monkeypatch, demo):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import netmind.api as api
    from netmind.storage import NetMindDB
    d = NetMindDB(tmp_path / "api.db")
    rid = analyze_packets(demo[0], "demo", "demo", d, train_until=60, save_model=False)
    monkeypatch.setattr(api, "_db", d)
    c = TestClient(api.app)
    assert c.get("/runs").json()[0]["id"] == rid
    assert len(c.get(f"/runs/{rid}/metrics").json()) > 50
    assert len(c.get(f"/runs/{rid}/incidents").json()) == 3
    path = c.get(f"/runs/{rid}/path", params={"src": "192.168.1.10", "dst": "8.8.8.8"}).json()
    assert path["path"][0] == "192.168.1.10"
    r = c.get(f"/runs/{rid}/routing", params={"node": "192.168.1.10"}).json()
    assert r["link_state"].keys() == r["distance_vector"].keys()
    ans = c.post("/ask", json={"question": "any attack?", "run_id": rid, "backend": "offline"}).json()
    assert "port scan" in ans["answer"]
    assert c.get("/runs/999").status_code == 404
