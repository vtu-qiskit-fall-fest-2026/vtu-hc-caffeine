"""CLI benchmark runner: python main.py --requests 500 --seed 17"""
import argparse
import pandas as pd
from config import SimulationConfig
from q_netops.engine.simulator import run_benchmark
from q_netops.metrics.evaluator import summarize

def main():
    parser = argparse.ArgumentParser(description="Benchmark Q-NetOps routing policies")
    parser.add_argument("--requests", type=int, default=250)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--target-fidelity", type=float, default=.70)
    parser.add_argument("--csv", default="q_netops_results.csv")
    args = parser.parse_args()
    config = SimulationConfig(request_count=args.requests, seed=args.seed,
                              target_fidelity=args.target_fidelity)
    results = run_benchmark(config)
    pd.DataFrame(results).to_csv(args.csv, index=False)
    print(summarize(results).to_string(index=False))
    print(f"\nRequest-level results written to {args.csv}")

if __name__ == "__main__":
    main()
