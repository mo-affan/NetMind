"""Command line: help, version, demo (fresh and rerun), report, ask, routes, NS2, errors."""
import importlib.util

import pytest
from conftest import NS2_SAMPLE, run_cli

from netmind.storage import NetMindDB


def test_help_and_version(tmp_path):
    r = run_cli("--help", db_path=tmp_path / "x.db")
    assert r.returncode == 0
    for cmd in ("demo", "pcap", "ns2", "report", "ask", "routes", "dashboard", "api"):
        assert cmd in r.stdout
    v = run_cli("--version", db_path=tmp_path / "x.db")
    assert v.returncode == 0 and v.stdout.startswith("netmind ")


def test_demo_on_clean_database_then_rerun(tmp_path):
    dbp = tmp_path / "fresh.db"
    assert not dbp.exists()
    r = run_cli("demo", "--save-pcap", "", db_path=dbp, cwd=tmp_path)  # any working folder
    assert r.returncode == 0, r.stderr
    assert "SYNTHETIC" in r.stdout and "synthetic traffic" in r.stdout
    for incident in ("Network congestion", "Possible port scan", "Traffic flood"):
        assert incident in r.stdout
    assert dbp.exists()
    r2 = run_cli("demo", "--save-pcap", "", db_path=dbp)
    assert r2.returncode == 0, r2.stderr
    d = NetMindDB(dbp)
    runs = d.runs()
    assert len(runs) == 2 and set(runs["source"]) == {"synthetic"}
    # same seed -> same analysis both times
    assert len(d.load("incidents", 1)) == len(d.load("incidents", 2)) == 3
    d.close()


def test_report_ask_runs_routes(tmp_path):
    dbp = tmp_path / "r.db"
    assert run_cli("demo", "--save-pcap", "", db_path=dbp).returncode == 0
    rep = run_cli("report", db_path=dbp)
    assert rep.returncode == 0 and "Incidents:" in rep.stdout
    ask = run_cli("ask", "Is anyone attacking my network?", db_path=dbp)
    assert ask.returncode == 0 and "port scan" in ask.stdout and "backend: offline" in ask.stdout
    runs = run_cli("runs", db_path=dbp)
    assert runs.returncode == 0 and "Synthetic demo" in runs.stdout
    rt = run_cli("routes", "--from", "192.168.1.10", "--to", "8.8.8.8", db_path=dbp)
    assert rt.returncode == 0 and "Dijkstra" in rt.stdout and "Distance Vector converged" in rt.stdout


def test_ns2_command(tmp_path):
    r = run_cli("ns2", NS2_SAMPLE, db_path=tmp_path / "n.db")
    assert r.returncode == 0, r.stderr
    assert "Network congestion" in r.stdout and "n0-n2-n4-n3" in r.stdout


def test_empty_database_messages(tmp_path):
    dbp = tmp_path / "empty.db"
    for args in (["report"], ["runs"], ["ask", "hello?"]):
        r = run_cli(*args, db_path=dbp)
        assert r.returncode == 0 and "No runs yet" in r.stdout
    r = run_cli("routes", db_path=dbp)
    assert r.returncode == 1 and "no runs yet" in r.stderr


def test_clear_errors_without_tracebacks(tmp_path):
    dbp = tmp_path / "e.db"
    r = run_cli("ns2", tmp_path / "missing.tr", db_path=dbp)
    assert r.returncode == 1 and "not found" in r.stderr and "Traceback" not in r.stderr
    bad = tmp_path / "bad.tr"
    bad.write_text("this is not an ns2 trace\n")
    r = run_cli("ns2", bad, db_path=dbp)
    assert r.returncode == 1 and "no NS2 packet events" in r.stderr and "Traceback" not in r.stderr
    assert run_cli("demo", "--save-pcap", "", db_path=dbp).returncode == 0
    r = run_cli("routes", "--from", "nosuchhost", db_path=dbp)
    assert r.returncode == 1 and "not in run" in r.stderr


@pytest.mark.parametrize("cmd,module", [("dashboard", "streamlit"), ("api", "fastapi")])
def test_missing_optional_package_message(tmp_path, cmd, module):
    if importlib.util.find_spec(module) is not None:
        pytest.skip(f"{module} is installed; the missing-package message cannot be shown")
    r = run_cli(cmd, db_path=tmp_path / "m.db")
    assert r.returncode == 1 and f"pip install {module}" in r.stderr


def test_short_demo_reports_insufficient_data(tmp_path):
    r = run_cli("demo", "--duration", "8", "--save-pcap", "", db_path=tmp_path / "s.db")
    assert r.returncode == 0, r.stderr
    assert "anomaly detection skipped" in r.stdout
