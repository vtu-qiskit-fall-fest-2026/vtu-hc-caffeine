"""Tick-driven event simulator for link generation, memory expiry, and swapping."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import math
import random
from ..controllers.base import Controller, Decision
from ..controllers.static import StaticController
from ..controllers.greedy import GreedyController
from ..controllers.adaptive import QNetOpsController
from .memory import MemorySlot
from .network import Network
from .physics import decay_fidelity, project_path_fidelity, swap_fidelity

CONTROLLERS = [StaticController(), GreedyController(), QNetOpsController()]


class _FixedPathController(Controller):
    """Internal controller used to forecast one candidate route repeatedly."""
    name = "Candidate route forecast"

    def __init__(self, link_ids):
        self.link_ids = tuple(link_ids)

    def choose(self, network, source, target, now_s, config):
        links = {edge.link_id: edge for edge in network.links}
        path = [links[link_id] for link_id in self.link_ids]
        return Decision("CONNECT", path, 1.0, 0.0, "fixed route forecast")

@dataclass
class RequestResult:
    policy: str
    delivered: bool
    fidelity: float
    latency_s: float
    path: str
    action: str
    reason: str
    generation_attempts: int
    wasted_attempts: int
    memory_utilization: float
    predicted_failure_risk: float | None = None
    decision_candidates: list[dict] | None = None

def _release_path(network, slots):
    for node_id, slot_id in slots:
        network.nodes[node_id].memory.release(slot_id)

def run_request(controller, config, rng: random.Random, source="A", target="B") -> RequestResult:
    network = Network.demo(config.memory_slots_per_node, config.noise_scale, config.traffic_load,
                           config.link_fidelity_calibration, config.degraded_link_id,
                           config.failure_severity)
    decision = controller.choose(network, source, target, 0.0, config)
    path = decision.path
    # Orient each undirected edge from the source toward the destination.
    node, ordered_nodes = source, [source]
    for edge in path:
        node = network.other(edge, node); ordered_nodes.append(node)
    label = " → ".join(ordered_nodes)
    if not path:
        return RequestResult(controller.name, False, .25, 0, label, "REROUTE", decision.reason, 0, 0, 0)
    if decision.action == "REROUTE":
        return RequestResult(controller.name, False, .25, 0, label, "REROUTE", decision.reason, 0, 0, 0)

    # Each element stores (generation timestamp, initial Werner fidelity, slot handles).
    active = [None] * len(path)
    handles = [None] * len(path)
    attempts = wasted = 0
    fidelity = .25
    memory_area = ticks = 0
    tick_s = .001
    now = 0.0
    max_ticks = max(1, math.ceil(config.request_deadline_s / tick_s))
    swap_attempts = 0
    action = decision.action
    delivered = False
    for _ in range(max_ticks):
        # Expire old entanglement before attempting swaps; stale memory is purged.
        for i, state in enumerate(active):
            if state is not None:
                current = decay_fidelity(state[1], now-state[0], config.coherence_time_s)
                if current < config.purge_fidelity:
                    wasted += 1
                    _release_path(network, handles[i] or [])
                    active[i] = handles[i] = None
                    action = "RETRY"

        # Generate all missing elementary pairs in parallel.
        for i, edge in enumerate(path):
            if active[i] is not None: continue
            attempts += 1
            p = controller.edge_probability(edge, config)
            if rng.random() < p:
                pair_f = max(.25, min(.999, edge.base_fidelity - edge.noise*rng.random()))
                slot_handles = []
                slot_id = f"{i}:{attempts}"
                required_nodes = {edge.u, edge.v}
                if all(len(network.nodes[n].memory.slots) < network.nodes[n].memory.capacity for n in required_nodes):
                    for n in required_nodes:
                        slot = MemorySlot(f"{slot_id}@{n}", edge.link_id, now, pair_f, config.coherence_time_s)
                        network.nodes[n].memory.allocate(slot); slot_handles.append((n, slot.slot_id))
                    active[i], handles[i] = (now, pair_f), slot_handles
                else:
                    wasted += 1
            else:
                wasted += 1

        memory_area += sum(len(n.memory.slots) / n.memory.capacity for n in network.nodes.values()) / len(network.nodes)
        ticks += 1
        now += tick_s
        if all(state is not None for state in active):
            pair_fidelities = [decay_fidelity(state[1], now-state[0], config.coherence_time_s) for state in active]
            result_f = pair_fidelities[0]
            swaps_ok = True
            for next_f in pair_fidelities[1:]:
                if rng.random() >= config.swap_success_probability:
                    swaps_ok = False; wasted += 1; break
                result_f = swap_fidelity(result_f, next_f)
            _release_path(network, [h for group in handles if group for h in group])
            active, handles = [None]*len(path), [None]*len(path)
            if swaps_ok and result_f >= config.target_fidelity:
                fidelity = result_f
                delivered = True
                action = "CONNECT"
                break
            if swaps_ok: fidelity = max(fidelity, result_f)
            swap_attempts += 1
            action = "RETRY" if swap_attempts < config.max_retries else "RETRACT"
            if swap_attempts >= config.max_retries:
                break

    return RequestResult(controller.name, delivered, fidelity, now, label, "CONNECT" if delivered else action,
                         decision.reason, attempts, wasted, memory_area/max(1,ticks))

def run_benchmark(config, requests: int | None = None) -> list[dict]:
    """Compare policies on shared, overlapping requests and persistent memories."""
    count = requests or config.request_count
    rows = []
    for controller in CONTROLLERS:
        policy_rows = run_traffic_scenario(controller, config, count)
        rows.extend(policy_rows)
    return rows


def _mean_interarrival_s(traffic_load: float) -> float:
    """Map the UI load control to request pressure, independently of link noise."""
    return 0.002 + 0.020 * (1.0 - min(1.0, max(0.0, traffic_load)))


def _release_request(network: Network, request):
    for pair in request["pairs"]:
        if pair is not None:
            for node_id, slot_id in pair[2]:
                network.nodes[node_id].memory.release(slot_id)
    request["pairs"] = [None] * len(request["pairs"])
    for attempt in request.get("pending_attempts", []):
        if not attempt["cancelled"]:
            for node_id, slot_id in attempt["handles"]:
                network.nodes[node_id].memory.release(slot_id)
            attempt["handles"] = []
            attempt["cancelled"] = True
    request["pending_attempts"] = []
    request["inflight_indices"].clear()


def _adopt_repaired_route(network: Network, request, updated, now_s: float):
    """Change route while retaining live pairs and attempts on shared links."""
    old_path = request["path"]
    old_label = request["path_label"]
    old_pairs = {edge.link_id: pair for edge, pair in zip(old_path, request["pairs"])}
    new_path = updated.path
    new_ids = {edge.link_id for edge in new_path}
    old_ids = {edge.link_id for edge in old_path}
    kept = old_ids & new_ids
    pairs_by_id = old_pairs
    for edge, pair in zip(old_path, request["pairs"]):
        if pair is not None and edge.link_id not in kept:
            request["wasted"] += 1
            for node_id, slot_id in pair[2]:
                network.nodes[node_id].memory.release(slot_id)
    request["pairs"] = [pairs_by_id.get(edge.link_id) for edge in new_path]

    # Keep in-flight heralding on links that remain in the route. Cancel only
    # the work tied to removed links and remap retained attempts to new indices.
    new_index = {edge.link_id: index for index, edge in enumerate(new_path)}
    retained_attempts = []
    request["inflight_indices"].clear()
    for attempt in request["pending_attempts"]:
        old_edge = old_path[attempt["edge_index"]]
        if old_edge.link_id not in new_index:
            if not attempt["cancelled"]:
                for node_id, slot_id in attempt["handles"]:
                    network.nodes[node_id].memory.release(slot_id)
                attempt["handles"] = []
                attempt["cancelled"] = True
            continue
        attempt["edge_index"] = new_index[old_edge.link_id]
        request["inflight_indices"].add(attempt["edge_index"])
        retained_attempts.append(attempt)
    request["pending_attempts"] = retained_attempts

    nodes = ["A"]
    for edge in new_path:
        nodes.append(network.other(edge, nodes[-1]))
    request["path"] = new_path
    request["path_label"] = " → ".join(nodes)
    request["swap_ready_s"] = None
    request["decision"] = updated
    request["reroutes"] += 1
    request["action"] = "REROUTE"
    preserved = sum(request["pairs"][i] is not None for i, edge in enumerate(new_path)
                    if edge.link_id in kept)
    request["preserved_pairs"] += preserved
    request["repair_events"] += 1
    request["log_event"](
        "route_repaired",
        f"Repaired {old_label} → {request['path_label']}; preserved {preserved} valid entangled segment(s)",
    )


def _refresh_weakest_pair(network: Network, request, now_s: float, config, tick_s: float) -> bool:
    """Refresh one aging segment only when a fresh pair can rescue fidelity."""
    pairs = request["pairs"]
    if not pairs or any(pair is None for pair in pairs):
        return False
    wait_for_swap = (max(tick_s, .001 + sum(edge.length_km for edge in request["path"])
                         / config.propagation_speed_km_s) if len(pairs) > 1 else 0.0)
    remaining = request["deadline_s"] - now_s
    current_now = [decay_fidelity(pair[1], now_s - pair[0], config.coherence_time_s)
                   for pair in pairs]
    current_future = [decay_fidelity(value, wait_for_swap, config.coherence_time_s)
                      for value in current_now]
    current_projection = project_path_fidelity(current_future, [0.0] * len(current_future),
                                               config.coherence_time_s, config.swap_success_probability)
    if current_projection >= config.target_fidelity:
        return False

    best = None
    for index, (edge, pair) in enumerate(zip(request["path"], pairs)):
        generation = max(tick_s, 2 * edge.length_km / config.propagation_speed_km_s)
        if generation + wait_for_swap >= remaining:
            continue
        refreshed = list(current_now)
        # Use a conservative expected fresh-link fidelity, then age every
        # segment through the additional generation and swap wait.
        fresh = max(.25, edge.base_fidelity - edge.noise * .5)
        delay = generation + wait_for_swap
        refreshed[index] = decay_fidelity(fresh, delay, config.coherence_time_s)
        projected = project_path_fidelity(
            [decay_fidelity(value, delay, config.coherence_time_s)
             if i != index else value for i, value in enumerate(refreshed)],
            [0.0] * len(refreshed), config.coherence_time_s, config.swap_success_probability,
        )
        if projected >= config.target_fidelity and projected - current_projection >= .01:
            candidate = (projected, index, generation)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        return False

    projected, index, generation = best
    edge, pair = request["path"][index], pairs[index]
    age_ms = max(0.0, now_s - pair[0]) * 1000
    for node_id, slot_id in pair[2]:
        network.nodes[node_id].memory.release(slot_id)
    pairs[index] = None
    request["swap_ready_s"] = None
    request["action"] = "RETRY"
    request["log_event"](
        "pair_refresh",
        f"Refreshing {edge.link_id} ({age_ms:.1f} ms old): projected end-to-end fidelity improves to {projected:.3f}; other segments retained",
        edge=edge.link_id, fidelity=projected,
    )
    return True


def run_traffic_scenario(controller, config, requests: int | None = None) -> list[dict]:
    """Run one persistent network under overlapping, deadline-bound requests.

    Link attempts contend for shared edge capacity (one attempt per millisecond),
    and generated pairs reserve node memories until a swap, expiry, or timeout.
    The adaptive scheduler uses earliest deadline/most-complete-first arbitration;
    baselines retain first-come-first-served arbitration.
    """
    count = requests or config.request_count
    network = Network.demo(config.memory_slots_per_node, config.noise_scale, 0.0,
                           config.link_fidelity_calibration, config.degraded_link_id,
                           config.failure_severity)
    arrivals_rng = random.Random(config.seed + 91_117)
    event_rng = random.Random(config.seed + 203_807)
    mean_interval = _mean_interarrival_s(config.traffic_load)
    arrival_times = [0.0]
    for _ in range(1, count):
        arrival_times.append(arrival_times[-1] + arrivals_rng.expovariate(1.0 / mean_interval))

    active = []
    completed = []
    pending_attempts = []
    link_busy_until = {edge.link_id: 0.0 for edge in network.links}
    tick_s = .001
    now = 0.0
    next_arrival = 0
    slot_counter = 0

    def adaptive_priority(request):
        missing = [edge for index, edge in enumerate(request["path"])
                   if request["pairs"][index] is None]
        generation = max((max(tick_s, 2*edge.length_km/config.propagation_speed_km_s)
                          / max(controller.edge_probability(edge, config), 1e-9)
                          for edge in missing), default=0.0)
        swap = (0.0 if len(request["path"]) <= 1 else
                .001 + sum(edge.length_km for edge in request["path"])
                / config.propagation_speed_km_s)
        remaining = generation + swap
        slack = max(0.0, request["deadline_s"] - now - remaining)
        urgency = 1.0 - min(1.0, max(0.0, request["deadline_s"] - now - remaining)
                             / max(config.request_deadline_s, tick_s))
        complete = sum(pair is not None for pair in request["pairs"]) / max(1, len(request["pairs"]))
        success_probability = config.swap_success_probability ** max(0, len(request["path"]) - 1)
        expected_fidelities = []
        for edge, pair in zip(request["path"], request["pairs"]):
            if pair is None:
                expected_fidelities.append(max(.25, edge.base_fidelity - edge.noise * .5))
                success_probability *= controller.edge_probability(edge, config)
            else:
                expected_fidelities.append(decay_fidelity(pair[1], now-pair[0], config.coherence_time_s))
        quality = project_path_fidelity(expected_fidelities, [0.0] * len(expected_fidelities),
                                        config.coherence_time_s, config.swap_success_probability)
        nodes = ["A"]
        for edge in request["path"]:
            nodes.append(network.other(edge, nodes[-1]))
        free_ratio = min((max(0, network.nodes[node].memory.capacity
                              - len(network.nodes[node].memory.slots))
                          / network.nodes[node].memory.capacity for node in set(nodes)), default=0.0)
        quality_score = min(1.0, quality / max(config.target_fidelity, .25))
        score = (.36 * urgency + .22 * complete + .20 * quality_score
                 + .12 * success_probability + .10 * free_ratio)
        return (-score, slack, remaining, request["arrival_s"], request["request_id"])

    while next_arrival < count or active:
        while next_arrival < count and arrival_times[next_arrival] <= now + 1e-12:
            decision = controller.choose(network, "A", "B", now, config)
            path = decision.path
            nodes = ["A"]
            for edge in path:
                nodes.append(network.other(edge, nodes[-1]))
            request = {
                "request_id": next_arrival + 1, "arrival_s": now,
                "deadline_s": now + config.request_deadline_s,
                "path": path, "path_label": " → ".join(nodes) if path else "unavailable",
                "decision": decision, "pairs": [None] * len(path), "attempts": 0,
                "pending_attempts": [], "inflight_indices": set(), "swap_ready_s": None,
                "wasted": 0, "blocked_ticks": 0, "swap_attempts": 0,
                "reroutes": 0, "last_reroute_check": 0,
                "link_failures": {},
                "repair_events": 0, "preserved_pairs": 0,
                "memory_area": 0.0, "samples": 0, "peak_concurrent": 0,
                "done": False, "delivered": False, "fidelity": .25,
                "action": decision.action,
                "events": [],
            }
            def log_event(kind, message, *, event_time=None, edge=None, fidelity=None,
                          predicted_risk=None,
                          _request=request):
                if len(_request["events"]) >= 80:
                    if kind not in {"delivered", "deadline", "reroute_failed", "swap_rejected"}:
                        return
                    _request["events"].pop()
                if event_time is None:
                    event_time = now
                if event_time < _request["arrival_s"]:
                    event_time = _request["arrival_s"]
                stored_pairs = []
                for pair_index, pair in enumerate(_request["pairs"]):
                    if pair is None:
                        continue
                    pair_edge = _request["path"][pair_index]
                    stored_pairs.append({
                        "link": pair_edge.link_id,
                        "age_ms": round(max(0.0, event_time-pair[0])*1000, 3),
                        "fidelity": round(decay_fidelity(pair[1], max(0.0, event_time-pair[0]),
                                                         config.coherence_time_s), 4),
                    })
                _request["events"].append({
                    "time_ms": round((event_time-_request["arrival_s"])*1000, 3),
                    "kind": kind, "message": message, "action": _request["action"],
                    "path": _request["path_label"], "edge": edge,
                    "fidelity": round(float(fidelity), 4) if fidelity is not None else None,
                    "predicted_failure_risk": (round(float(predicted_risk), 4)
                                               if predicted_risk is not None else None),
                    "active_pairs": sum(pair is not None for pair in _request["pairs"]),
                    "stored_pairs": stored_pairs,
                    "memory_slots_by_node": {node_id: len(node.memory.slots)
                                              for node_id, node in network.nodes.items()},
                })
            request["log_event"] = log_event
            log_event("arrival", f"Request arrived; deadline in {config.request_deadline_s*1000:.0f} ms")
            if config.degraded_link_id and config.failure_severity > 0:
                log_event("fault_injected",
                          f"Controlled link fault on {config.degraded_link_id}: success probability reduced by {config.failure_severity:.0%}",
                          edge=config.degraded_link_id)
            log_event("route", f"{decision.action}: {decision.reason}",
                      predicted_risk=decision.predicted_risk)
            next_arrival += 1
            if not path or decision.action == "REROUTE":
                request["done"] = True
                request["action"] = "REROUTE"
                request["latency_s"] = 0.0
                request["reason"] = decision.reason
                completed.append(request)
            else:
                active.append(request)

        # Expired pairs are freed before new attempts compete for memory.
        for request in active:
            for i, pair in enumerate(request["pairs"]):
                if pair is not None and decay_fidelity(pair[1], now-pair[0], config.coherence_time_s) < config.purge_fidelity:
                    request["wasted"] += 1
                    for node_id, slot_id in pair[2]:
                        network.nodes[node_id].memory.release(slot_id)
                    request["pairs"][i] = None
                    request["swap_ready_s"] = None
                    request["action"] = "RETRY"
                    request["log_event"]("memory_expired", f"Pair on {request['path'][i].link_id} fell below purge fidelity", edge=request["path"][i].link_id)

        # Complete photon/heralding attempts only after their propagation delay.
        still_pending = []
        for attempt in pending_attempts:
            if now + 1e-12 < attempt["ready_s"]:
                still_pending.append(attempt)
                continue
            request = attempt["request"]
            if attempt in request["pending_attempts"]:
                request["pending_attempts"].remove(attempt)
            request["inflight_indices"].discard(attempt["edge_index"])
            if attempt["cancelled"] or request["done"] or now >= request["deadline_s"]:
                for node_id, slot_id in attempt["handles"]:
                    network.nodes[node_id].memory.release(slot_id)
                attempt["handles"] = []
                continue
            if attempt["success"]:
                request["link_failures"][request["path"][attempt["edge_index"]].link_id] = 0
                request["pairs"][attempt["edge_index"]] = (
                    attempt["ready_s"], attempt["fidelity"], attempt["handles"]
                )
                request["log_event"]("pair_ready", f"Elementary pair ready on {request['path'][attempt['edge_index']].link_id}", event_time=now, edge=request["path"][attempt["edge_index"]].link_id, fidelity=attempt["fidelity"])
            else:
                for node_id, slot_id in attempt["handles"]:
                    network.nodes[node_id].memory.release(slot_id)
                request["wasted"] += 1
                failed_edge = request["path"][attempt["edge_index"]]
                failures = request["link_failures"].get(failed_edge.link_id, 0) + 1
                request["link_failures"][failed_edge.link_id] = failures
                request["log_event"]("generation_failed", f"Heralded generation failed on {failed_edge.link_id} (consecutive failure {failures})", event_time=now, edge=failed_edge.link_id)
                if (controller.name == "Q-NetOps adaptive" and failures >= 2
                        and request["reroutes"] < 2):
                    # Re-plan around the failed section. A new graph reuses the
                    # live memory banks but omits only this link from routing.
                    recovery_graph = Network(network.nodes,
                                             [edge for edge in network.links
                                              if edge.link_id != failed_edge.link_id])
                    updated = controller.choose(recovery_graph, "A", "B", now, config)
                    old_ids = tuple(edge.link_id for edge in request["path"])
                    new_ids = tuple(edge.link_id for edge in updated.path)
                    if new_ids and new_ids != old_ids:
                        _adopt_repaired_route(network, request, updated, now)
        pending_attempts = still_pending

        # An elementary link can run one attempt per tick; competing sessions
        # share that channel and each successful pair consumes two memory slots.
        for edge in network.links:
            if now + 1e-12 < link_busy_until[edge.link_id]:
                continue
            contenders = [r for r in active if not r["done"] and now < r["deadline_s"]
                          and any(e.link_id == edge.link_id for e in r["path"])
                          and r["pairs"][next(i for i, e in enumerate(r["path"])
                                               if e.link_id == edge.link_id)] is None
                          and next(i for i, e in enumerate(r["path"])
                                   if e.link_id == edge.link_id) not in r["inflight_indices"]]
            if not contenders:
                continue
            if controller.name == "Q-NetOps adaptive":
                contenders.sort(key=adaptive_priority)
            else:
                contenders.sort(key=lambda r: (r["arrival_s"], r["request_id"]))
            chosen = None
            edge_index = 0
            for contender in contenders:
                idx = next(i for i, e in enumerate(contender["path"]) if e.link_id == edge.link_id)
                if all(len(network.nodes[node].memory.slots) < network.nodes[node].memory.capacity
                       for node in (edge.u, edge.v)):
                    chosen, edge_index = contender, idx
                    break
                contender["blocked_ticks"] += 1
                if contender["blocked_ticks"] % 3 == 1:
                    contender["log_event"]("memory_blocked", f"{edge.link_id} attempt deferred: endpoint memory is full", edge=edge.link_id)
            if chosen is None:
                continue
            chosen["attempts"] += 1
            probability = controller.edge_probability(edge, config)
            generation_delay = max(tick_s, 2*edge.length_km/config.propagation_speed_km_s)
            ready_s = now + generation_delay
            fidelity = max(.25, min(.999, edge.base_fidelity-edge.noise*event_rng.random()))
            handles = []
            slot_counter += 1
            pair_id = f"req{chosen['request_id']}:{edge.link_id}:{slot_counter}"
            for node_id in (edge.u, edge.v):
                slot = MemorySlot(f"{pair_id}@{node_id}", edge.link_id, ready_s,
                                  fidelity, config.coherence_time_s)
                network.nodes[node_id].memory.allocate(slot)
                handles.append((node_id, slot.slot_id))
            attempt = {"request": chosen, "edge_index": edge_index, "ready_s": ready_s,
                       "success": event_rng.random() < probability, "fidelity": fidelity,
                       "handles": handles, "cancelled": False}
            pending_attempts.append(attempt)
            chosen["pending_attempts"].append(attempt)
            chosen["inflight_indices"].add(edge_index)
            link_busy_until[edge.link_id] = ready_s
            chosen["log_event"]("attempt_started", f"Generation attempt started on {edge.link_id}", edge=edge.link_id)

        utilization = sum(node.memory.utilization for node in network.nodes.values()) / len(network.nodes)
        for request in active:
            if request["done"]:
                continue

            # If shared memory has stalled a session, re-evaluate its route once
            # per additional three blocked ticks using the live network state.
            if (controller.name == "Q-NetOps adaptive" and request["reroutes"] < 2
                    and request["blocked_ticks"]-request["last_reroute_check"] >= 3):
                request["last_reroute_check"] = request["blocked_ticks"]
                updated = controller.choose(network, "A", "B", now, config)
                old_ids = tuple(edge.link_id for edge in request["path"])
                new_ids = tuple(edge.link_id for edge in updated.path)
                if new_ids and new_ids != old_ids:
                    _adopt_repaired_route(network, request, updated, now)
                    request["log_event"]("reroute", f"Replanned from {' → '.join(old_ids)} to {' → '.join(new_ids)} after memory stalls")
                elif not new_ids and updated.action == "REROUTE":
                    _release_request(network, request)
                    request["done"] = True
                    request["action"] = "REROUTE"
                    request["latency_s"] = now-request["arrival_s"]
                    request["reason"] = updated.reason
                    request["log_event"]("reroute_failed", updated.reason)

            request["memory_area"] += utilization
            request["samples"] += 1
            request["peak_concurrent"] = max(request["peak_concurrent"], len(active))

            if _refresh_weakest_pair(network, request, now, config, tick_s):
                continue

            if all(pair is not None for pair in request["pairs"]):
                if request["swap_ready_s"] is None:
                    if len(request["path"]) > 1:
                        propagation = sum(edge.length_km for edge in request["path"]) / config.propagation_speed_km_s
                        request["swap_ready_s"] = now + max(tick_s, .001 + propagation)
                    else:
                        request["swap_ready_s"] = now
                    request["action"] = "WAIT"
                    oldest_age_ms = max((now-pair[0])*1000 for pair in request["pairs"])
                    projected_now = project_path_fidelity(pair_fidelities_for_log := [
                        decay_fidelity(pair[1], now-pair[0], config.coherence_time_s)
                        for pair in request["pairs"]
                    ], [0.0] * len(request["pairs"]), config.coherence_time_s,
                        config.swap_success_probability)
                    request["log_event"]("swap_scheduled", f"All pairs ready; oldest segment age {oldest_age_ms:.1f} ms, projected fidelity {projected_now:.3f}; swap scheduled at {request['swap_ready_s']*1000:.2f} ms", fidelity=projected_now)
                if now + 1e-12 >= request["swap_ready_s"]:
                    pair_fidelities = [decay_fidelity(pair[1], now-pair[0], config.coherence_time_s)
                                       for pair in request["pairs"]]
                    result_f = pair_fidelities[0]
                    swaps_ok = True
                    for next_fidelity in pair_fidelities[1:]:
                        if event_rng.random() >= config.swap_success_probability:
                            swaps_ok = False
                            request["wasted"] += 1
                            break
                        result_f = swap_fidelity(result_f, next_fidelity)
                    _release_request(network, request)
                    request["swap_ready_s"] = None
                    if swaps_ok and result_f >= config.target_fidelity:
                        request["fidelity"] = result_f
                        request["delivered"] = request["done"] = True
                        request["action"] = "CONNECT"
                        request["log_event"]("delivered", f"Delivered at fidelity {result_f:.3f} (target {config.target_fidelity:.2f})", event_time=now+tick_s, fidelity=result_f)
                    else:
                        request["fidelity"] = max(request["fidelity"], result_f)
                        request["swap_attempts"] += 1
                        request["action"] = ("RETRACT" if request["swap_attempts"] >= config.max_retries
                                              else "RETRY")
                        request["log_event"]("swap_rejected", f"Swap failed or fidelity {result_f:.3f} missed target", event_time=now+tick_s, fidelity=result_f)
                        if request["swap_attempts"] >= config.max_retries:
                            request["done"] = True

            if not request["done"] and now + tick_s >= request["deadline_s"]:
                request["wasted"] += sum(pair is not None for pair in request["pairs"])
                _release_request(network, request)
                request["done"] = True
                request["action"] = "RETRACT"
                request["log_event"]("deadline", "Deadline reached; remaining pairs released", event_time=now+tick_s, fidelity=request["fidelity"])
            if request["done"]:
                request["latency_s"] = now + tick_s - request["arrival_s"]
                request["reason"] = request["decision"].reason
                request["memory_utilization"] = request["memory_area"] / max(1, request["samples"])
                completed.append(request)

        active = [request for request in active if not request["done"]]
        now += tick_s

    rows = []
    for request in sorted(completed, key=lambda item: item["request_id"]):
        rows.append(asdict(RequestResult(
            policy=controller.name, delivered=request["delivered"],
            fidelity=request["fidelity"], latency_s=request.get("latency_s", 0.0),
            path=request["path_label"], action=request["action"],
            reason=request.get("reason", request["decision"].reason),
            generation_attempts=request["attempts"], wasted_attempts=request["wasted"],
            memory_utilization=request.get("memory_utilization", 0.0),
            predicted_failure_risk=request["decision"].predicted_risk,
            decision_candidates=request["decision"].candidate_evaluations,
        )))
        rows[-1]["actual_failure"] = not request["delivered"]
        rows[-1]["target_fidelity"] = config.target_fidelity
        rows[-1]["request_id"] = request["request_id"]
        rows[-1]["arrival_s"] = request["arrival_s"]
        rows[-1]["memory_blocked_ticks"] = request["blocked_ticks"]
        rows[-1]["peak_concurrent_requests"] = request["peak_concurrent"]
        rows[-1]["reroutes"] = request["reroutes"]
        rows[-1]["local_repairs"] = request["repair_events"]
        rows[-1]["preserved_segments"] = request["preserved_pairs"]
        rows[-1]["events"] = request["events"]
    return rows


def forecast_path_quality(network: Network, path, config, repetitions: int = 64) -> dict:
    """Monte Carlo forecast using the same shared-network event engine as evaluation."""
    controller = _FixedPathController(edge.link_id for edge in path)
    results = [run_traffic_scenario(
        controller, replace(config, seed=config.seed + 1_009_001 + i), requests=1
    )[0] for i in range(repetitions)]
    successes = [result for result in results if result["delivered"]]
    denominator = max(1, len(successes))
    return {
        "delivery_rate": len(successes) / max(1, repetitions),
        "mean_success_latency_s": (sum(result["latency_s"] for result in successes) / denominator
                                   if successes else config.request_deadline_s),
        "mean_success_fidelity": (sum(result["fidelity"] for result in successes) / denominator
                                  if successes else 0.0),
        "mean_fidelity": sum(result["fidelity"] for result in results) / max(1, repetitions),
        "mean_wasted_attempts": sum(result["wasted_attempts"] for result in results) / max(1, repetitions),
    }
