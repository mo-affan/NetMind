"""NetMind REST API (FastAPI).

Every module's results are available over HTTP, so the dashboard or any other
client can use them. Start it with:  python -m netmind api
Interactive docs: http://127.0.0.1:8000/docs

    GET  /health                    status, version, database path, number of runs
    GET  /runs                      saved runs
    GET  /runs/{id}                 summary, overall metrics, baseline
    GET  /runs/{id}/metrics         per-window performance metrics
    GET  /runs/{id}/anomalies       per-window anomaly scores
    GET  /runs/{id}/incidents       grouped incidents
    GET  /runs/{id}/protocols       protocol distribution
    GET  /runs/{id}/flows           top flows
    GET  /runs/{id}/hosts           host inventory: scope, role, services, traffic in/out
    GET  /runs/{id}/connections     every TCP connection attempt and its outcome
    GET  /runs/{id}/dns             most-queried domains with response times
    GET  /runs/{id}/insights        health score, connection and DNS summaries
    GET  /runs/{id}/topology        nodes and links
    GET  /runs/{id}/path?src=&dst=  Dijkstra shortest path
    GET  /runs/{id}/routing?node=   Link State and Distance Vector tables for a node
    POST /ask                       {"question": "...", "run_id": 1} -> Copilot answer
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from netmind.pipeline import get_state
from netmind.storage import DEFAULT_DB, NetMindDB

app = FastAPI(title="NetMind API", version="0.1.0",
              description="AI-Powered Network Intelligence and LLM Network Copilot")
_db: NetMindDB | None = None
_copilot = None


def db() -> NetMindDB:
    """Opens the database once and reuses it."""
    global _db
    if _db is None:
        _db = NetMindDB(os.environ.get("NETMIND_DB", str(DEFAULT_DB)))
    return _db


def _records(df):
    """DataFrame -> JSON-safe list of dicts (NaN -> null)."""
    return json.loads(df.to_json(orient="records")) if not df.empty else []


def _check(run_id: int):
    """Returns the run or a 404 error if it does not exist."""
    try:
        return db().run(run_id)
    except KeyError:
        raise HTTPException(404, f"run {run_id} not found")


@app.get("/")
def root():
    """GET /: API name and links."""
    return {"name": "NetMind API", "docs": "/docs", "health": "/health", "runs": len(db().runs())}


@app.get("/health")
def health():
    """GET /health: status, version and number of runs."""
    from netmind import __version__
    return {"status": "ok", "version": __version__, "database": str(db().path),
            "runs": int(len(db().runs())), "latest_run": db().latest_run_id()}


@app.get("/runs")
def runs():
    """GET /runs: every stored run."""
    return _records(db().runs())


@app.get("/runs/{run_id}")
def run(run_id: int):
    """GET /runs/{id}: one run and its summary."""
    return _check(run_id)


def _table(name: str):
    """Makes a GET endpoint for one stored table (metrics, flows, ...)"""
    def handler(run_id: int):
        """Returns that table's rows for the run."""
        _check(run_id)
        return _records(db().load(name, run_id))
    handler.__name__ = f"get_{name}"
    return handler


for _name in ("metrics", "anomalies", "protocols", "flows", "hosts", "connections", "dns"):
    app.get(f"/runs/{{run_id}}/{_name}")(_table(_name))


@app.get("/runs/{run_id}/insights")
def insights(run_id: int):
    """GET /runs/{id}/insights: health, connections and DNS."""
    _check(run_id)
    st = get_state(db(), run_id)
    return {k: st.get(k, {}) for k in ("health", "connections", "dns")}


@app.get("/runs/{run_id}/incidents")
def incidents(run_id: int):
    """GET /runs/{id}/incidents: the incidents found."""
    _check(run_id)
    return get_state(db(), run_id)["incidents"]


@app.get("/runs/{run_id}/topology")
def topology(run_id: int):
    """GET /runs/{id}/topology: nodes and links."""
    _check(run_id)
    return {"nodes": _records(db().load("nodes", run_id)),
            "links": _records(db().load("links", run_id))}


def _graph(run_id: int):
    """Rebuilds the topology graph of a run."""
    from netmind.topology import graph_from_frames
    _check(run_id)
    return graph_from_frames(db().load("nodes", run_id), db().load("links", run_id))


@app.get("/runs/{run_id}/path")
def path(run_id: int, src: str, dst: str, weight: str = "latency"):
    """GET /runs/{id}/path: Dijkstra shortest path between two hosts."""
    import networkx as nx
    from netmind.topology import shortest_path
    G = _graph(run_id)
    try:
        return shortest_path(G, src, dst, weight)
    except (nx.NodeNotFound, nx.NetworkXNoPath) as e:
        raise HTTPException(404, str(e))


@app.get("/runs/{run_id}/routing")
def routing(run_id: int, node: str, weight: str = "latency"):
    """GET /runs/{id}/routing: Link State and Distance Vector tables of a node."""
    from netmind.topology import distance_vector_tables, link_state_tables
    G = _graph(run_id)
    if node not in G:
        raise HTTPException(404, f"node {node} not in topology")
    dv, rounds = distance_vector_tables(G, weight)
    return {"node": node, "weight": weight, "link_state": link_state_tables(G, weight)[node],
            "distance_vector": dv[node], "dv_rounds": rounds}


class Question(BaseModel):
    """The body of POST /ask: question, run id, backend."""
    question: str
    run_id: int | None = None
    backend: str | None = None


@app.post("/ask")
def ask(q: Question):
    """POST /ask: the Copilot's answer about a run."""
    global _copilot
    from netmind.copilot import Copilot
    state = get_state(db(), q.run_id)
    if not state["run"]:
        raise HTTPException(404, "no runs yet: run `python -m netmind demo` first")
    if _copilot is None or (q.backend and q.backend != _copilot.backend):
        _copilot = Copilot(backend=q.backend)
    res = _copilot.ask(q.question, state)
    res.pop("prompt", None)
    return {"run_id": state["run"]["id"], **res}
