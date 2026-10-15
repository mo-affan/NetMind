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


def test_ns2_overall_uses_documented_definitions(db):
    from netmind.capture.ns2 import packet_table
    rid = analyze_ns2(str(NS2_SAMPLE), db=db)
    o = db.run(rid)["summary"]["overall"]
    pk = packet_table(str(NS2_SAMPLE))
    got, drop = (pk["fate"] == "delivered").sum(), (pk["fate"] == "dropped").sum()
    assert o["sent"] == len(pk) and o["delivered"] == got and o["dropped"] == drop
    assert o["loss_pct"] == round(100 * drop / (got + drop), 2)
    assert o["retransmissions"] > 0
    assert {f["type"] for f in db.run(rid)["summary"]["ns2_flows"]} == {"tcp", "cbr"}


def test_ns2_cli_needs_no_ns2_install(tmp_path):
    """`python -m netmind ns2 <trace>` only reads the file: run it from a folder with a copy
    of the trace and no `ns` executable on PATH."""
    import os
    import shutil
    import subprocess
    import sys
    from conftest import ROOT
    trace = tmp_path / "lab_run.tr"
    shutil.copy(NS2_SAMPLE, trace)
    path = [os.path.dirname(sys.executable)]
    if os.name == "nt":  # Windows needs its system folders on PATH to load DLLs
        root = os.environ.get("SystemRoot", r"C:\Windows")
        path += [os.path.join(root, "System32"), root]
    env = {**os.environ, "PATH": os.pathsep.join(path), "PYTHONPATH": str(ROOT)}
    out = subprocess.run([sys.executable, "-m", "netmind", "--db", str(tmp_path / "x.db"),
                          "ns2", str(trace)], capture_output=True, text=True, cwd=tmp_path, env=env)
    assert out.returncode == 0, out.stderr
    assert "Network congestion" in out.stdout and "Link failure and rerouting" in out.stdout
    assert shutil.which("ns", path=env["PATH"]) is None
