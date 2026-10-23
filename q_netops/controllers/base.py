from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from ..engine.network import FiberLink, Network

@dataclass
class Decision:
    action: str
    path: list[FiberLink]
    projected_fidelity: float
    estimated_latency_s: float
    reason: str
    candidate_evaluations: list[dict] = field(default_factory=list)
    predicted_risk: float | None = None

class Controller(ABC):
    name = "Controller"
    @abstractmethod
    def choose(self, network: Network, source: str, target: str, now_s: float, config) -> Decision: ...

    def paths(self, network: Network, source: str, target: str, max_hops: int = 5):
        paths = []
        def visit(node, seen, path):
            if node == target: paths.append(path); return
            if len(path) >= max_hops: return
            for edge in network.adjacency[node]:
                nxt = network.other(edge, node)
                if nxt not in seen: visit(nxt, seen | {nxt}, path + [edge])
        visit(source, {source}, [])
        return paths

    def edge_probability(self, edge, config):
        from ..engine.physics import link_success_probability
        p = link_success_probability(edge.length_km, config.alpha_db_per_km, config.source_efficiency)
        return max(1e-9, p * (1-edge.noise) * (1-edge.demand_penalty))

    def latency(self, path, config):
        return sum(2*edge.length_km/config.propagation_speed_km_s for edge in path) + max(0,len(path)-1)*.001
