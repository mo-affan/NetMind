"""M5 Topology and Routing.

The topology is a graph of the hosts seen communicating in the traffic: each IP
address is a node, and two nodes are linked when they exchanged packets. It is a
logical model of the network as seen from the capture point, not a map of
physical cables.

Each edge carries:
  latency  measured median RTT between the two hosts (ms), or a default if unmeasured
  hops     1 (every observed link counts as one hop)
  packets, bytes  traffic on the link

Routing:
  shortest_path()          Dijkstra on latency or hop count
  link_state_tables()      Link State (as in OSPF): each router knows the whole graph
                           and runs Dijkstra itself
  distance_vector_tables() Distance Vector (as in RIP): routers only exchange distance
                           tables with neighbours and update them with Bellman-Ford,
                           round by round until nothing changes
"""
from __future__ import annotations

import math

import networkx as nx
import pandas as pd

DEFAULT_LATENCY_MS = 1.0


def build_graph(df: pd.DataFrame, rtt: pd.DataFrame | None = None) -> nx.Graph:
    """Undirected graph of hosts and the links between them."""
    G = nx.Graph()
    if df.empty:
        return G
    a = df["src"].where(df["src"] < df["dst"], df["dst"])
    b = df["dst"].where(df["src"] < df["dst"], df["src"])
    pairs = df.assign(a=a, b=b).groupby(["a", "b"]).agg(packets=("ts", "size"),
                                                        bytes=("length", "sum")).reset_index()
    lat = {}
    if rtt is not None and not rtt.empty:
        ra = rtt["client"].where(rtt["client"] < rtt["server"], rtt["server"])
        rb = rtt["server"].where(rtt["client"] < rtt["server"], rtt["client"])
        lat = rtt.assign(a=ra, b=rb).groupby(["a", "b"])["rtt_ms"].median().to_dict()
    sent = df.groupby("src")["length"].sum().to_dict()
    recv = df.groupby("dst")["length"].sum().to_dict()
    for host in pd.unique(pd.concat([df["src"], df["dst"]])):
        G.add_node(host, bytes_sent=int(sent.get(host, 0)), bytes_received=int(recv.get(host, 0)),
                   kind=_kind(host))
    for row in pairs.itertuples(index=False):
        measured = lat.get((row.a, row.b))
        G.add_edge(row.a, row.b, packets=int(row.packets), bytes=int(row.bytes), hops=1,
                   latency=round(float(measured), 3) if measured is not None else DEFAULT_LATENCY_MS,
                   measured=measured is not None)
    return G


def _kind(host: str) -> str:
    """Labels a host gateway, local, external or NS2 node."""
    if host.endswith(".1"):
        return "gateway"
    if host.startswith(("10.", "192.168.", "172.")):
        return "local"
    if host.startswith("n") and host[1:].isdigit():
        return "ns2-node"
    return "remote"


def shortest_path(G: nx.Graph, source: str, target: str, weight: str = "latency") -> dict:
    """Dijkstra shortest path: the node list and its total cost."""
    path = nx.dijkstra_path(G, source, target, weight=weight)
    cost = nx.dijkstra_path_length(G, source, target, weight=weight)
    return {"path": path, "cost": round(float(cost), 3), "weight": weight}


def link_state_tables(G: nx.Graph, weight: str = "latency") -> dict[str, dict[str, dict]]:
    """Routing table per node: {node: {destination: {next_hop, cost}}} using Dijkstra."""
    tables = {}
    for src in G.nodes:
        dist, paths = nx.single_source_dijkstra(G, src, weight=weight)
        tables[src] = {dst: {"next_hop": p[1] if len(p) > 1 else dst, "cost": round(dist[dst], 3)}
                       for dst, p in paths.items() if dst != src}
    return tables


def distance_vector_tables(G: nx.Graph, weight: str = "latency", max_rounds: int = 50
                           ) -> tuple[dict[str, dict[str, dict]], int]:
    """Simulate Distance Vector routing (Bellman-Ford).

    Every round, each node sends its distance table to its neighbours, and each node
    updates: cost(dst) = min over neighbours n of cost(link to n) + n's cost(dst).
    Returns (tables, rounds needed to converge).
    """
    nodes = list(G.nodes)
    table = {u: {u: (0.0, u)} for u in nodes}
    for rnd in range(1, max_rounds + 1):
        changed = False
        snapshot = {u: dict(t) for u, t in table.items()}  # what each node advertised
        for u in nodes:
            for n in G.neighbors(u):
                link = G[u][n].get(weight, 1.0)
                for dst, (c, _) in snapshot[n].items():
                    new = link + c
                    if new + 1e-9 < table[u].get(dst, (math.inf, None))[0]:
                        table[u][dst] = (new, n)
                        changed = True
        if not changed:
            break
    out = {u: {d: {"next_hop": nh, "cost": round(c, 3)} for d, (c, nh) in t.items() if d != u}
           for u, t in table.items()}
    return out, rnd


def edges_frame(G: nx.Graph) -> pd.DataFrame:
    """Graph links as a table for storage."""
    return pd.DataFrame([{"a": a, "b": b, **d} for a, b, d in G.edges(data=True)])


def nodes_frame(G: nx.Graph) -> pd.DataFrame:
    """Graph nodes as a table for storage."""
    return pd.DataFrame([{"node": n, "degree": G.degree(n), **d} for n, d in G.nodes(data=True)])


def graph_from_frames(nodes: pd.DataFrame, links: pd.DataFrame) -> nx.Graph:
    """Rebuild a graph from the nodes/links tables stored in the database."""
    G = nx.Graph()
    for r in nodes.to_dict("records"):
        n = r.pop("node")
        r.pop("degree", None)
        G.add_node(n, **r)
    for r in links.to_dict("records"):
        G.add_edge(r.pop("a"), r.pop("b"), **r)
    return G
