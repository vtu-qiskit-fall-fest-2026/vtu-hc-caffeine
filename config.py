"""Central assumptions for the Q-NetOps simulator (all times are seconds)."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SimulationConfig:
    alpha_db_per_km: float = 0.2
    source_efficiency: float = 0.8
    coherence_time_s: float = 0.050
    purge_fidelity: float = 0.50
    target_fidelity: float = 0.70
    swap_success_probability: float = 0.50
    memory_slots_per_node: int = 10
    request_count: int = 250
    max_retries: int = 12
    request_deadline_s: float = 0.100
    static_timeout_s: float = 0.010
    propagation_speed_km_s: float = 200_000.0
    seed: int = 7
    noise_scale: float = 1.0
    traffic_load: float = 0.0
    # Optional elementary-link calibration inferred from published BBM92 QBER.
    # This is experiment-derived calibration, not live repeater telemetry.
    link_fidelity_calibration: float | None = None
    # Optional controlled stressor applied equally to every policy run.
    degraded_link_id: str | None = None
    failure_severity: float = 0.0
    # Explainable, adjustable weights for the route-level controller objective.
    route_weight_reliability: float = 0.30
    route_weight_fidelity: float = 0.28
    route_weight_latency: float = 0.16
    route_weight_resources: float = 0.14
    route_weight_recovery: float = 0.12
