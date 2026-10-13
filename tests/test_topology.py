import networkx as nx
import pytest

from netmind.performance import rtt_samples
from netmind.topology import (build_graph, distance_vector_tables, link_state_tables,
                              shortest_path)


@pytest.fixture
def textbook():
    G = nx.Graph()
    G.add_weighted_edges_from([("A", "B", 2), ("A", "C", 5), ("B", "C", 1), ("B", "D", 4),
                               ("C", "D", 1), ("D", "E", 3)], weight="latency")
    return G


def test_dijkstra(textbook):
    sp = shortest_path(textbook, "A", "E")
    assert sp["path"] == ["A", "B", "C", "D", "E"] and sp["cost"] == 7


def test_link_state_equals_distance_vector(textbook):
    ls = link_state_tables(textbook)
    dv, rounds = distance_vector_tables(textbook)
    for u in ls:
        for d in ls[u]:
            assert ls[u][d]["cost"] == dv[u][d]["cost"]
    assert ls["A"]["E"]["next_hop"] == "B"
    assert 1 < rounds < 10


def test_distance_vector_reroutes_after_link_failure(textbook):
    textbook.remove_edge("C", "D")
    dv, _ = distance_vector_tables(textbook)
    assert dv["A"]["E"]["cost"] == 9 and dv["A"]["E"]["next_hop"] == "B"


def test_graph_from_traffic(demo):
    df, _ = demo
    G = build_graph(df, rtt_samples(df))
    assert G.number_of_nodes() == 9
    gw = G["192.168.1.10"]["192.168.1.1"]
    assert gw["measured"] and 1 < gw["latency"] < 10
    assert G.nodes["192.168.1.1"]["kind"] == "gateway"
