# Routing and shortest paths

## Routing basics
Routers forward packets hop by hop using a routing table: for each destination network, the next hop and the cost. Routing protocols build these tables automatically. The cost (metric) can be hop count, delay or a configured weight.

## Dijkstra's algorithm
Dijkstra finds the lowest-cost path from one node to all others in a graph with non-negative weights. It starts with distance 0 at the source, repeatedly picks the unvisited node with the smallest known distance, marks it final, and updates its neighbours' distances. NetMind runs Dijkstra on its topology graph with measured latency (or hop count) as edge weight.

## Link State routing (OSPF)
In link state routing every router floods the state of its links to all routers, so each router knows the whole topology. Each router then runs Dijkstra (shortest path first) itself. It converges quickly and avoids loops, at the cost of more memory and processing. OSPF is the common link state protocol.

## Distance Vector routing (RIP)
In distance vector routing each router only knows its neighbours. Periodically it sends its distance table to them, and each router updates its table with the Bellman-Ford rule: cost to D = minimum over neighbours N of (cost to N + N's cost to D). It is simple but converges slowly, and after a link failure it can suffer the count-to-infinity problem; split horizon and poison reverse reduce this. RIP uses hop count with a maximum of 15.

## Link failure and rerouting
When a link fails, routers detect it, recompute routes and send traffic over another path. During convergence some packets may be lost. After rerouting, latency usually increases because the backup path is longer. In NS2, rtmodel events take a link down and up, and with rtproto DV the routes are recomputed by distance vector.
