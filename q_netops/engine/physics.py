"""Werner-state fidelity and link physics from the project specification."""
from __future__ import annotations
import math

def link_success_probability(length_km: float, alpha_db_per_km: float = 0.2,
                             source_efficiency: float = 0.8) -> float:
    """P0 * 10^(-alpha*L/10), clamped to a valid probability."""
    if length_km < 0:
        raise ValueError("Link length cannot be negative")
    return min(1.0, max(0.0, source_efficiency * 10 ** (-alpha_db_per_km * length_km / 10)))

def decay_fidelity(initial_fidelity: float, elapsed_s: float, coherence_time_s: float) -> float:
    """F(t)=0.25+(F0-0.25)exp(-t/Tcoh); 0.25 is the Werner random-state floor."""
    if coherence_time_s <= 0 or elapsed_s < 0:
        raise ValueError("Coherence time must be positive and elapsed time non-negative")
    initial_fidelity = min(1.0, max(0.25, initial_fidelity))
    return 0.25 + (initial_fidelity - 0.25) * math.exp(-elapsed_s / coherence_time_s)

def swap_fidelity(f1: float, f2: float) -> float:
    """Ideal conditional Werner fidelity after swapping two input pairs."""
    f1, f2 = min(1.0, max(.25, f1)), min(1.0, max(.25, f2))
    return f1 * f2 + ((1 - f1) * (1 - f2)) / 3

def project_path_fidelity(link_fidelities: list[float], holding_times_s: list[float],
                          coherence_time_s: float, swap_success_probability: float = .5) -> float:
    """Project the final pair through link decay and sequential swapping."""
    if not link_fidelities or len(link_fidelities) != len(holding_times_s):
        raise ValueError("Supply one non-empty holding time per link")
    states = [decay_fidelity(f, t, coherence_time_s)
              for f, t in zip(link_fidelities, holding_times_s)]
    result = states[0]
    for state in states[1:]:
        result = swap_fidelity(result, state)
    # Swap success affects delivery probability, not conditional output fidelity.
    return result
