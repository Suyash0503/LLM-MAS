import argparse
import json
import os
import subprocess
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]

CHECKOUT_JSON = ROOT / "src" / "checkout-agent" / "checkout_request.json"

TOKEN_FILES = [
    ROOT / "src" / "productcatalogagent" / "token_log.txt",
    ROOT / "src" / "emailserviceagent" / "token_log.txt",
    ROOT / "src" / "adserviceagent" / "token_log.txt",
    ROOT / "src" / "paymentagent" / "token_log.txt",
    ROOT / "src" / "currencyagent" / "token_log.txt",
    ROOT / "src" / "recommendationagent" / "token_log.txt",
    ROOT / "src" / "shippingservice" / "token_log.txt",
    ROOT / "src" / "checkout-agent" / "token_log.txt",
    ROOT / "src" / "cart-agent" / "token_log.txt",
]

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "checkout_agent_db")

CHECKOUT_TARGET = os.getenv("CHECKOUT_TARGET", "localhost:5050")
CHECKOUT_METHOD = "hipstershop.CheckoutService/PlaceOrder"


def clear_token_logs():
    for f in TOKEN_FILES:
        if f.exists():
            f.unlink()


def read_tokens():
    total = 0
    for f in TOKEN_FILES:
        if f.exists():
            for line in f.read_text().splitlines():
                try:
                    total += int(line.strip())
                except:
                    pass
    return total


def grpc_checkout_once(trial_id: int):
    start = time.time()

    cmd = [
        "grpcurl",
        "-plaintext",
        "-d",
        "@",
        CHECKOUT_TARGET,
        CHECKOUT_METHOD,
    ]

    try:
        payload = CHECKOUT_JSON.read_text()

        proc = subprocess.run(
            cmd,
            input=payload,
            text=True,
            capture_output=True,
            timeout=900,
        )

        latency = time.time() - start

        if proc.returncode != 0:
            return {
                "trial": trial_id,
                "status": "FAILED",
                "latency": latency,
                "error": proc.stderr,
            }

        return {
            "trial": trial_id,
            "status": "SUCCESS",
            "latency": latency,
            "response": proc.stdout,
        }

    except Exception as e:
        latency = time.time() - start
        return {
            "trial": trial_id,
            "status": "FAILED",
            "latency": latency,
            "error": str(e),
        }


def get_consistency_metrics():
    if not MONGO_URI:
        return {
            "total_orders": 0,
            "failed_orders": 0,
            "success_orders": 0,
            "qa_inconsistency_rate": 0,
        }

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    orders = db["orders"]

    total_orders = orders.count_documents({})
    failed_orders = orders.count_documents({"status": "FAILED"})
    success_orders = orders.count_documents({"status": "SUCCESS"})

    qa_inconsistency_rate = 0
    if total_orders > 0:
        qa_inconsistency_rate = (failed_orders / total_orders) * 100

    return {
        "total_orders": total_orders,
        "failed_orders": failed_orders,
        "success_orders": success_orders,
        "qa_inconsistency_rate": qa_inconsistency_rate,
    }


def run_experiment(name, requests_count, concurrency, output):
    clear_token_logs()

    print(f"Running experiment: {name}")
    print(f"Requests={requests_count}, concurrency={concurrency}")

    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(grpc_checkout_once, i)
            for i in range(1, requests_count + 1)
        ]

        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"Trial {res['trial']} => {res['status']} latency={round(res['latency'], 3)}s")

    latencies = [r["latency"] for r in results]
    successes = [r for r in results if r["status"] == "SUCCESS"]
    failures = [r for r in results if r["status"] == "FAILED"]

    total_tokens = read_tokens()
    consistency = get_consistency_metrics()

    summary = {
        "name": name,
        "requests": requests_count,
        "concurrency": concurrency,
        "success_count": len(successes),
        "failure_count": len(failures),
        "api_failure_rate_percent": (len(failures) / requests_count) * 100,
        "avg_latency": statistics.mean(latencies) if latencies else 0,
        "median_latency": statistics.median(latencies) if latencies else 0,
        "p95_latency": statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 100 else max(latencies),
        "total_tokens": total_tokens,
        "avg_tokens_per_request": total_tokens / requests_count if requests_count else 0,
        "consistency": consistency,
    }

    final = {
        "summary": summary,
        "trials": results,
    }

    output_path = ROOT / output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(final, f, indent=2)

    print("\nFINAL SUMMARY")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    run_experiment(
        name=args.name,
        requests_count=args.requests,
        concurrency=args.concurrency,
        output=args.output,
    )