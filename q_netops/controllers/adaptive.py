from .base import Controller, Decision
from ..engine.digital_twin import NetworkSnapshot, score_route


class QNetOpsController(Controller):
    """Interpretable model-predictive controller, not presented as trained ML.

    Candidate routes are ranked by repeatable Monte Carlo rollouts of the same
    deadline, memory, swapping, and fidelity simulator used for evaluation.
    """
    name = "Q-NetOps adaptive"
    FORECAST_REPETITIONS = 64

    def __init__(self):
        self._forecast_cache = {}

    @staticmethod
    def _fingerprint(network, config):
        return (
            tuple((e.link_id, round(e.noise, 6), round(e.base_fidelity, 6),
                   round(e.length_km, 3), round(e.demand_penalty, 6)) for e in network.links),
            config.target_fidelity, config.purge_fidelity, config.coherence_time_s,
            config.request_deadline_s, config.max_retries,
            config.memory_slots_per_node, config.swap_success_probability,
            config.alpha_db_per_km, config.source_efficiency,
            config.propagation_speed_km_s,
            config.noise_scale, config.traffic_load, config.link_fidelity_calibration,
        )

    def choose(self, network, source, target, now_s, config):
        # Import lazily: simulator owns the execution loop and imports this class.
        from ..engine.simulator import forecast_path_quality

        candidates = self.paths(network, source, target)
        if not candidates:
            return Decision("REROUTE", [], .25, 0.0, "No path available")

        snapshot = NetworkSnapshot.capture(network, now_s)
        fingerprint = self._fingerprint(network, config)
        evaluations = []
        for path in candidates:
            key = (fingerprint, tuple(edge.link_id for edge in path))
            forecast = self._forecast_cache.get(key)
            if forecast is None:
                forecast = forecast_path_quality(
                    network, path, config, self.FORECAST_REPETITIONS
                )
                self._forecast_cache[key] = forecast
            latency = self.latency(path, config)
            evaluation = score_route(snapshot, path, source, config,
                                     self.edge_probability, latency, forecast)
            # Blend the named, deterministic objective with same-engine rollout
            # evidence. Neither term is represented as real-world telemetry.
            evaluation["objective_score"] = .60 * evaluation["objective_score"] + .40 * forecast["delivery_rate"]
            evaluations.append((evaluation, forecast, path))

        evaluations.sort(key=lambda item: (
            item[0]["feasible"], item[0]["objective_score"],
            item[1]["delivery_rate"], item[1]["mean_success_fidelity"],
            -item[1]["mean_success_latency_s"],
        ), reverse=True)
        selected, forecast, path = evaluations[0]
        feasible_now = selected["feasible"]
        headroom = selected["memory_headroom"]
        rate = forecast["delivery_rate"]
        fidelity = forecast["mean_success_fidelity"] or forecast["mean_fidelity"]
        latency = forecast["mean_success_latency_s"]
        if rate > 0 and feasible_now:
            action = "CONNECT"
            reason = (
                f"Digital-twin candidate evaluation: {selected['explanation']} "
                f"{self.FORECAST_REPETITIONS}-rollout delivery estimate {rate:.0%}; "
                f"mean successful latency {latency*1000:.1f} ms; mean fidelity {fidelity:.3f}."
            )
        elif rate > 0:
            action = "WAIT"
            failed = [name for name, ok in selected["constraints"].items() if not ok]
            action = "WAIT" if failed == ["memory"] else "REROUTE"
            reason = ("No route meets the current candidate constraints (" + ", ".join(failed)
                      + "); retain the request for the scheduler's next decision." if failed
                      else "The forecast route is viable but current resources are contested")
        elif fidelity >= config.purge_fidelity:
            action = "WAIT"
            reason = "Digital-twin rollouts found no qualified delivery in this window; preserve the request and retry"
        else:
            action = "REROUTE"
            reason = "Candidate route fidelity forecast falls below the purge threshold"
        return Decision(action, path, fidelity, latency, reason,
                        candidate_evaluations=[item[0] for item in evaluations],
                        predicted_risk=selected["modeled_failure_risk"])
