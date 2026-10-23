"""Lightweight undirected repeater graph; no graph-library runtime required."""
from __future__ import annotations
from dataclasses import dataclass, field
from .memory import MemoryBank

@dataclass(frozen=True)
class FiberLink:
    link_id: str
    u: str
    v: str
    length_km: float
    base_fidelity: float = .92
    noise: float = 0.0
    demand_penalty: float = 0.0

@dataclass
class RepeaterNode:
    node_id: str
    memory: MemoryBank

@dataclass
class Network:
    nodes: dict[str, RepeaterNode]
    links: list[FiberLink]
    adjacency: dict[str, list[FiberLink]] = field(init=False)

    def __post_init__(self):
        self.adjacency = {node: [] for node in self.nodes}
        for link in self.links:
            if link.u not in self.nodes or link.v not in self.nodes:
                raise ValueError(f"Unknown endpoint on {link.link_id}")
            self.adjacency[link.u].append(link); self.adjacency[link.v].append(link)

    def other(self, link: FiberLink, node: str) -> str:
        if node == link.u: return link.v
        if node == link.v: return link.u
        raise ValueError(f"Node {node} is not on link {link.link_id}")

    @classmethod
    def demo(cls, memory_capacity: int = 10, noise_scale: float = 1.0,
             traffic_load: float = 0.0,
             link_fidelity_calibration: float | None = None,
             degraded_link_id: str | None = None,
             failure_severity: float = 0.0) -> "Network":
        ids = ["A", "R1", "R2", "R3", "B"]
        nodes = {n: RepeaterNode(n, MemoryBank(memory_capacity)) for n in ids}
        links = [
            FiberLink("L1", "A", "R1", 22, .97), FiberLink("L2", "R1", "R2", 24, .96),
            FiberLink("L3", "R2", "R3", 22, .97), FiberLink("L4", "R3", "B", 23, .96),
            FiberLink("L5", "A", "R2", 49, .94, .02), FiberLink("L6", "R1", "R3", 47, .93, .03),
            FiberLink("L7", "R2", "B", 49, .94, .02), FiberLink("L8", "A", "B", 111, .90, .08),
        ]
        # Traffic pressure is modeled through overlapping sessions and shared
        # memory/link scheduling in run_traffic_scenario, not as fake edge loss.
        links = [FiberLink(e.link_id, e.u, e.v, e.length_km,
                          link_fidelity_calibration if link_fidelity_calibration is not None else e.base_fidelity,
                          min(.95, e.noise*noise_scale),
                          min(1.0, max(0.0, failure_severity)) if e.link_id == degraded_link_id else 0.0)
                 for e in links]
        return cls(nodes, links)
