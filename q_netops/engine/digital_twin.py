"""Read-only, deterministic decision model for the synthetic network.

The twin snapshots live memory occupancy before it scores candidate actions.
It does not run the event engine or mutate the live network. Risk values are
simulation estimates derived from configured link success, memory headroom,
and coherence-time constraints; they are not real-world predictions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math

from .network import FiberLink, Network
from .physics import project_path_fidelity


@dataclass(frozen=True)
class NetworkSnapshot:
    captured_at_s: float
    available_slots: dict[str, int]
    capacities: dict[str, int]
    links: tuple[dict, ...]

    @classmethod
    def capture(cls, network: Network, now_s: float) -> "NetworkSnapshot":
        # Copy first so callers can prove candidate evaluation never operates
        # on the mutable live MemoryBank instances.
        frozen = deepcopy(network)
        return cls(
            captured_at_s=now_s,
            available_slots={node_id: max(0, node.memory.capacity - len(node.memory.slots))
                             for node_id, node in frozen.nodes.items()},
            capacities={node_id: node.memory.capacity for node_id, node in frozen.nodes.items()},
            links=tuple({"id": edge.link_id, "u": edge.u, "v": edge.v,
                         "length_km": edge.length_km, "noise": edge.noise,
                         "demand_penalty": edge.demand_penalty}
                        for edge in frozen.links),
        )


def score_route(snapshot: NetworkSnapshot, path: list[FiberLink], source: str,
                config, edge_probability, latency_s: float,
                forecast: dict | None = None) -> dict:
    """Evaluate one route and return named, auditable metrics and constraints."""
    nodes = [source]
    for edge in path:
        nodes.append(edge.v if edge.u == nodes[-1] else edge.u)
    slots_needed = {node: 1 for node in nodes}
    for node in nodes[1:-1]:
        slots_needed[node] = slots_needed.get(node, 0) + 1
    free_ratios = []
    enough_memory = True
    for node_id, needed in slots_needed.items():
        capacity = snapshot.capacities[node_id]
        free = snapshot.available_slots[node_id]
        free_ratios.append(max(0.0, free / max(1, capacity)))
        enough_memory &= free >= needed
    memory_headroom = min(free_ratios, default=0.0)

    link_probabilities = [max(0.0, min(1.0, edge_probability(edge, config))) for edge in path]
    swap_probability = max(0.0, min(1.0, config.swap_success_probability)) ** max(0, len(path) - 1)
    route_reliability = swap_probability
    for probability in link_probabilities:
        route_reliability *= probability

    link_fidelities = [max(.25, min(1.0, edge.base_fidelity - edge.noise * .5)) for edge in path]
    projected_fidelity = (project_path_fidelity(
        link_fidelities, [latency_s] * len(path), config.coherence_time_s,
        config.swap_success_probability,
    ) if path else .25)
    recovery_risk = max((edge.demand_penalty for edge in path), default=1.0)
    generation_risk = 1.0 - math.prod(link_probabilities)
    memory_risk = 1.0 - memory_headroom
    lifetime_risk = min(1.0, max(0.0, latency_s / max(config.coherence_time_s, 1e-9)))
    swap_risk = 1.0 - swap_probability
    single_attempt_failure_risk = 1.0 - route_reliability
    component_risk = 1.0 - (1.0 - generation_risk) * (1.0 - swap_risk) \
        * (1.0 - .35 * memory_risk) \
        * (1.0 - .20 * recovery_risk) * (1.0 - .15 * lifetime_risk)

    weights = (
        config.route_weight_reliability, config.route_weight_fidelity,
        config.route_weight_latency, config.route_weight_resources,
        config.route_weight_recovery,
    )
    weight_total = sum(max(0.0, value) for value in weights) or 1.0
    normalized = [max(0.0, value) / weight_total for value in weights]
    reliability_score = route_reliability
    fidelity_score = min(1.0, projected_fidelity / max(config.target_fidelity, .25))
    latency_score = 1.0 / (1.0 + latency_s / max(config.request_deadline_s, 1e-9))
    resource_score = memory_headroom
    recovery_score = 1.0 - recovery_risk
    objective_score = sum(w * x for w, x in zip(
        normalized, (reliability_score, fidelity_score, latency_score,
                     resource_score, recovery_score)))

    forecast = forecast or {}
    rollout_delivery = forecast.get("delivery_rate")
    # Compare like with like: the request-level estimate includes the retry,
    # expiry, swapping, and scheduling rules represented in each rollout.
    modeled_risk = (1.0 - max(0.0, min(1.0, rollout_delivery))
                    if rollout_delivery is not None else component_risk)
    constraints = {
        "fidelity": projected_fidelity >= config.target_fidelity,
        "deadline": latency_s <= config.request_deadline_s,
        "memory": enough_memory,
        "lifetime": latency_s <= config.coherence_time_s,
    }
    return {
        "route": " → ".join(nodes), "links": [edge.link_id for edge in path],
        "feasible": all(constraints.values()), "constraints": constraints,
        "projected_fidelity": projected_fidelity,
        "route_reliability": route_reliability, "estimated_latency_s": latency_s,
        "memory_headroom": memory_headroom, "memory_slots_needed": slots_needed,
        "modeled_failure_risk": modeled_risk,
        "single_attempt_failure_risk": single_attempt_failure_risk,
        "risk_components": {"link_generation": generation_risk,
                             "swapping": swap_risk,
                             "memory_pressure": memory_risk,
                             "coherence_lifetime": lifetime_risk,
                             "recovery_exposure": recovery_risk},
        "objective_score": objective_score,
        "forecast_delivery_rate": rollout_delivery,
        "forecast_mean_success_fidelity": forecast.get("mean_success_fidelity"),
        "forecast_mean_success_latency_s": forecast.get("mean_success_latency_s"),
        "explanation": (
            f"Score {objective_score:.3f}; single-attempt link/swap success {route_reliability:.1%}; "
            f"projected fidelity {projected_fidelity:.3f}; memory headroom {memory_headroom:.0%}; "
            f"modeled failure risk {modeled_risk:.1%}."
        ),
    }
