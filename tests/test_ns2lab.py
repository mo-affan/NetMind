"""Logic of the dashboard's NS2 lab page: it reuses ns2/check_trace.py and ns2/compare_traces.py."""
import subprocess
import sys

import pytest

from conftest import NS2_SAMPLE, ROOT
from netmind.dashboard import ns2lab


def test_parameters_come_from_the_tcl_file():
    p = ns2lab.scenario_parameters()
    assert p["routing"] == "Distance Vector" and p["queue_limit"] == 10 and p["tcp_window"] == 6
    links = {(l["a"], l["b"]): l for l in p["links"]}
    assert links[("n2", "n3")]["bandwidth"] == "1Mb" and links[("n2", "n3")]["queue"] == "$qtype"
    assert links[("n0", "n2")]["queue"] == "DropTail"
    assert ("n2", "n4", 3) in p["costs"]


def test_checks_match_the_lab_script():
    res = ns2lab.check(NS2_SAMPLE)
    assert res["passed"] == 5 and all(ok for _, ok in res["checks"])
    assert res["stats"]["drops_normal"] == 0 and res["stats"]["drops_burst"] > 0
    assert any(r["path"] == "n0-n2-n4-n3" for r in res["routes"])
    assert set(res["drops_per_link"]) <= {"n2-n3"}
    out = subprocess.run([sys.executable, str(ROOT / "ns2" / "check_trace.py"), str(NS2_SAMPLE)],
                         capture_output=True, text=True).stdout
    assert out.count("[PASS]") == 5
    assert f"during burst {res['stats']['delay_burst_ms']:.1f} ms" in out  # page and script agree


def test_phases_and_comparison():
    ph = ns2lab.phases(NS2_SAMPLE)
    assert list(ph["Phase"]) == ["normal", "UDP burst", "recovery", "link down", "link up"]
    burst = ph.set_index("Phase").loc["UDP burst"]
    assert burst["Drops"] > 0 and burst["Delay (ms)"] > ph.set_index("Phase").loc["normal", "Delay (ms)"]
    cmp = ns2lab.compare(NS2_SAMPLE, NS2_SAMPLE, "DropTail", "RED")
    assert (cmp["Delay change %"].fillna(0) == 0).all()  # same trace twice: no change
    assert "Delay (ms) RED" in cmp.columns


def test_rejects_a_file_that_is_not_a_trace(tmp_path):
    bad = tmp_path / "x.tr"
    bad.write_text("hello\n")
    with pytest.raises(ValueError):
        ns2lab.check(bad)
