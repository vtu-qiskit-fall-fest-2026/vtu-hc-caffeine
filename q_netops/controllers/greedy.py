from .base import Controller, Decision
from ..engine.physics import project_path_fidelity

class GreedyController(Controller):
    name = "Greedy link quality"
    def choose(self, network, source, target, now_s, config):
        candidates = self.paths(network, source, target)
        def score(path):
            return sum(self.edge_probability(e, config)*e.base_fidelity for e in path)/max(1,len(path))
        path = max(candidates, key=score, default=[])
        latency = self.latency(path, config)
        f = project_path_fidelity([e.base_fidelity for e in path], [latency]*len(path), config.coherence_time_s) if path else .25
        return Decision("CONNECT", path, f, latency,
                        "Highest average immediate link probability × fidelity")
