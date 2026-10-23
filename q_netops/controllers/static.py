import heapq
from itertools import count
from .base import Controller, Decision
from ..engine.physics import project_path_fidelity

class StaticController(Controller):
    name = "Static Dijkstra"
    def choose(self, network, source, target, now_s, config):
        order = count()
        queue = [(0.0, next(order), source, [])]; best = {}; path = []
        while queue:
            cost, _, node, candidate = heapq.heappop(queue)
            if node in best and best[node] <= cost: continue
            best[node] = cost
            if node == target: path = candidate; break
            for edge in network.adjacency[node]:
                nxt = network.other(edge, node)
                heapq.heappush(queue, (cost+edge.length_km, next(order), nxt, candidate+[edge]))
        latency = max(config.static_timeout_s, self.latency(path, config))
        fidelity = project_path_fidelity([e.base_fidelity for e in path], [latency]*len(path), config.coherence_time_s) if path else .25
        # Classical baseline: commit to the shortest-distance path without a
        # fidelity gate. End-to-end qualification is measured after simulation.
        return Decision("CONNECT", path, fidelity, latency,
                       "Shortest-distance path; baseline does not gate on fidelity")
