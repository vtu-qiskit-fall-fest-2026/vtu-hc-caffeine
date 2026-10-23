"""Reproducible multi-seed comparison of Q-NetOps policies and baselines."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import SimulationConfig
from q_netops.engine.simulator import run_benchmark


SCENARIOS = {
    "Nominal operation": {"noise": 0.8, "load": 0.10, "memory": 10},
    "Photon-loss spike": {"noise": 2.5, "load": 0.15, "memory": 10},
    "Memory squeeze": {"noise": 1.2, "load": 0.35, "memory": 2},
    "Traffic burst": {"noise": 1.0, "load": 0.75, "memory": 4},
}


def run_sweep(requests: int, seeds: int, first_seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = []
    for scenario, settings in SCENARIOS.items():
        for seed in range(first_seed, first_seed + seeds):
            config = SimulationConfig(
                request_count=requests,
                seed=seed,
                noise_scale=settings["noise"],
                traffic_load=settings["load"],
                memory_slots_per_node=settings["memory"],
                target_fidelity=0.70,
            )
            results = run_benchmark(config, requests=requests)
            for row in results:
                row["scenario"] = scenario
                row["seed"] = seed
            raw.extend(results)
            print(f"completed {scenario} · seed {seed}", flush=True)

    trials = pd.DataFrame(raw)
    trials["delivered_fidelity"] = trials.fidelity.where(trials.delivered)
    by_seed = trials.groupby(["scenario", "seed", "policy"], as_index=False).agg(
        success_rate=("delivered", "mean"),
        mean_fidelity=("fidelity", "mean"),
        mean_delivered_fidelity=("delivered_fidelity", "mean"),
        mean_latency_s=("latency_s", "mean"),
        mean_wasted_attempts=("wasted_attempts", "mean"),
        mean_memory_utilization=("memory_utilization", "mean"),
    )
    summary = by_seed.groupby(["scenario", "policy"], as_index=False).agg(
        seeds=("seed", "nunique"),
        success_rate=("success_rate", "mean"),
        success_rate_sd=("success_rate", "std"),
        mean_fidelity=("mean_fidelity", "mean"),
        mean_delivered_fidelity=("mean_delivered_fidelity", "mean"),
        mean_latency_s=("mean_latency_s", "mean"),
        mean_wasted_attempts=("mean_wasted_attempts", "mean"),
        mean_memory_utilization=("mean_memory_utilization", "mean"),
    )
    summary["success_rate_ci95"] = 1.96 * summary.success_rate_sd.fillna(0) / summary.seeds.pow(0.5)
    summary["success_ci_low"] = (summary.success_rate - summary.success_rate_ci95).clip(0, 1)
    summary["success_ci_high"] = (summary.success_rate + summary.success_rate_ci95).clip(0, 1)
    return trials, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=100, help="requests per policy per seed")
    parser.add_argument("--seeds", type=int, default=10, help="independent scenario seeds")
    parser.add_argument("--first-seed", type=int, default=21)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks"))
    args = parser.parse_args()
    if args.requests < 1 or args.seeds < 2:
        parser.error("Use at least 1 request and 2 seeds to compute seed-to-seed uncertainty.")

    trials, summary = run_sweep(args.requests, args.seeds, args.first_seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trials.to_csv(args.output_dir / "robustness_trials.csv", index=False)
    summary.to_csv(args.output_dir / "robustness_summary.csv", index=False)
    display = summary[["scenario", "policy", "success_rate", "success_ci_low", "success_ci_high",
                       "mean_delivered_fidelity", "mean_latency_s", "mean_wasted_attempts"]].copy()
    print("\nSummary (means across independent seeds):")
    print(display.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nWrote {len(trials):,} trial rows and {len(summary)} summary rows to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
