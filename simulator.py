"""Small reproducible simulator for fidelity-aware repeater routing."""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import random
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Link:
    u: str
    v: str
    distance_km: float
    base_success: float
    channel_fidelity: float
    swap_success: float = 0.88


@dataclass
class Trial:
    policy: str
    delivered: bool
    fidelity: float
    latency_s: float
    attempts: int
    path: str
    action: str


NODES = ["A", "R1", "R2", "R3", "B"]
LINKS = [
    Link("A", "R1", 42, .78, .985), Link("R1", "R2", 34, .82, .990),
    Link("R2", "R3", 48, .72, .978), Link("R3", "B", 39, .80, .986),
    Link("A", "R2", 79, .52, .955), Link("R1", "R3", 76, .55, .960),
    Link("R2", "B", 82, .48, .950), Link("A", "B", 163, .18, .900),
]


def adjacency(links: List[Link]) -> Dict[str, List[Tuple[str, Link]]]:
    graph: Dict[str, List[Tuple[str, Link]]] = {n: [] for n in NODES}
    for edge in links:
        graph[edge.u].append((edge.v, edge))
        graph[edge.v].append((edge.u, edge))
    return graph


def shortest_path(links: List[Link], source: str, target: str) -> List[Link]:
    graph = adjacency(links)
    queue = [(0.0, source, [])]
    best = {}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node in best and best[node] <= cost:
            continue
        best[node] = cost
        if node == target:
            return path
        for nxt, edge in graph[node]:
            weight = edge.distance_km
            heapq.heappush(queue, (cost + weight, nxt, path + [edge]))
    return []


def candidate_paths(links: List[Link], source: str, target: str, max_hops: int = 4) -> List[List[Link]]:
    graph = adjacency(links)
    found: List[List[Link]] = []
    def walk(node: str, seen: set[str], path: List[Link]) -> None:
        if node == target:
            found.append(path)
            return
        if len(path) >= max_hops:
            return
        for nxt, edge in graph[node]:
            if nxt not in seen:
                walk(nxt, seen | {nxt}, path + [edge])
    walk(source, {source}, [])
    return found


def predicted_score(path: List[Link], noise: float, memory_tau: float, fidelity_floor: float) -> float:
    # Geometric waiting estimate for parallel elementary-link generation.
    success = 1.0
    times = []
    q = 1 - noise
    for edge in path:
        p = max(.02, min(.98, edge.base_success * q))
        success *= p * edge.swap_success
        times.append(1.0 / p)
    wait = max(times, default=0) + .45 * max(0, len(path) - 1)
    decay = math.exp(-wait / max(1e-6, memory_tau))
    f = .5 + (min((e.channel_fidelity for e in path), default=1) - .5) * decay
    f = .5 + (f - .5) * (1 - noise * .8) ** len(path)
    if f < fidelity_floor:
        return -1.0
    return success * (f - .5) / max(.01, wait)


def run_trial(policy: str, rng: random.Random, noise: float, memory_tau: float,
              fidelity_floor: float, attempt_budget: int, load: float) -> Trial:
    links = [Link(e.u, e.v, e.distance_km, e.base_success * (1 - .55 * load),
                  e.channel_fidelity - .025 * load, e.swap_success) for e in LINKS]
    if policy == "Adaptive":
        ranked = sorted(candidate_paths(links, "A", "B"),
                        key=lambda p: predicted_score(p, noise, memory_tau, fidelity_floor), reverse=True)
        path = ranked[0] if ranked else []
    else:
        path = shortest_path(links, "A", "B")
    if not path:
        return Trial(policy, False, 0, 0, 0, "unavailable", "Reroute")

    path_names = [path[0].u] + [e.v if e.u == path[i-1].v else e.u for i, e in enumerate(path)]
    label = " → ".join(path_names)
    attempts = 0
    elapsed = 0.0
    best_fidelity = .5
    action = "Connect"
    # Adaptive prediction changes the attempt budget when a route is marginal.
    budget = attempt_budget
    if policy == "Adaptive":
        score = predicted_score(path, noise, memory_tau, fidelity_floor)
        if score < 0:
            return Trial(policy, False, 0, 0, 0, label, "Reroute")
        budget = max(2, int(attempt_budget * (1 + min(.5, score * 2))))

    for attempt in range(1, budget + 1):
        attempts += len(path)
        probabilities = [max(.01, min(.99, e.base_success * (1 - noise) * rng.uniform(.82, 1.08))) for e in path]
        elapsed += max(1 / p for p in probabilities) + .35 * (len(path) - 1)
        if any(rng.random() > p for p in probabilities):
            action = "Retry" if attempt < budget else "Reroute"
            continue
        # Sequential swaps; quality decays while stored and compounds across hops.
        ages = [rng.expovariate(1 / max(.2, memory_tau * .45)) for _ in path]
        edge_f = [max(.51, e.channel_fidelity - noise * rng.uniform(.4, 1.2)) for e in path]
        visibility = 1.0
        for f, age in zip(edge_f, ages):
            # For Werner states, visibility (2F-1) multiplies across a swap.
            visibility *= (2 * f - 1) * math.exp(-age / memory_tau)
        # Each intermediate swap attenuates the composed visibility.
        fidelity = .5 + .5 * visibility * math.prod(e.swap_success for e in path[:-1])
        best_fidelity = max(best_fidelity, fidelity)
        if fidelity >= fidelity_floor:
            return Trial(policy, True, fidelity, elapsed, attempts, label, "Connect")
        action = "Wait" if elapsed < memory_tau else "Reroute"
    return Trial(policy, False, best_fidelity, elapsed, attempts, label, action)


def simulate(trials: int = 250, seed: int = 7, noise: float = .08,
             memory_tau: float = 12.0, fidelity_floor: float = .78,
             attempt_budget: int = 5, load: float = .1) -> List[Trial]:
    results: List[Trial] = []
    # Separate deterministic streams make policy results stable across UI reruns.
    for name, offset in (("Adaptive", 0), ("Shortest path", 100000)):
        rng = random.Random(seed + offset)
        results.extend(run_trial(name, rng, noise, memory_tau, fidelity_floor,
                                 attempt_budget, load) for _ in range(trials))
    return results
