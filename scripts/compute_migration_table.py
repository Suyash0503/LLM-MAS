import argparse
import json
import csv
from pathlib import Path

COST_PER_TOKEN = 1e-7


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main(results_dir, output):
    results_dir = Path(results_dir)
    files = sorted(results_dir.glob("step_*.json"))

    baseline = load_json(files[0])["summary"]
    baseline_p95 = baseline["p95_latency"]

    rows = []

    for i, file in enumerate(files):
        data = load_json(file)["summary"]

        tokens = data["total_tokens"]
        delta_latency = data["p95_latency"] - baseline_p95
        op_cost = tokens * COST_PER_TOKEN
        failure_rate = data["api_failure_rate_percent"]
        cons = data["consistency"]["qa_inconsistency_rate"]

        stopping = (
            delta_latency > 5 or
            failure_rate > 5 or
            cons > 2
        )

        rows.append({
            "iteration": i,
            "setup": data["name"],
            "N_tokens": tokens,
            "Delta_Cons_percent": round(cons, 3),
            "Delta_L_seconds": round(delta_latency, 3),
            "Delta_C_op_dollars": round(op_cost, 6),
            "API_failure_rate_percent": round(failure_rate, 3),
            "Stopping_criteria_met": "YES" if stopping else "NO",
            "Accepted": "NO" if stopping else "YES",
        })

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved table to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="results/final_migration_table.csv")
    args = parser.parse_args()

    main(args.results_dir, args.output)