import json
import csv
import os
import subprocess
import sys

SCENARIO_FILE = "fault_injection/scenarios.json"
RESULT_FILE = "fault_injection/results.csv"

def run_scenario(scenario):
    env = os.environ.copy()
    env["FAULT_MODE"] = scenario["mast_mode"]
    env["CATALOG_STOCK"] = str(scenario["catalog_stock"])
    env["ACTUAL_STOCK"] = str(scenario["actual_stock"])
    env["ORDER_QUANTITY"] = str(scenario["order_quantity"])

    test_code = """
from fault_injection.inventory_faults import (
    communicate_inventory_result,
    reserve_inventory,
    final_inventory_verification,
    action_log
)

result = communicate_inventory_result()
fault_mode = result.get("fault_mode")

if result.get("message_to_checkout") == "inventory_mismatch_detected" and fault_mode not in ["FM-1.3", "FM-3.2"]:
    decision = "STOP_CHECKOUT"
else:
    reserve = reserve_inventory("product-1", 1)
    verify = final_inventory_verification()

    if verify.get("verification_performed") and not verify.get("stock_ok"):
        decision = "STOP_CHECKOUT"
    else:
        decision = "ORDER_CONFIRMED"

print({
    "inventory_result": result,
    "decision": decision,
    "action_log": action_log
})
"""

    completed = subprocess.run(
        [sys.executable, "-c", test_code],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.getcwd()
    )

    output = completed.stdout.strip()
    error = completed.stderr.strip()

    if error:
        print("ERROR in", scenario["id"])
        print(error)

    passed = "STOP_CHECKOUT" in output

    return {
        "scenario_id": scenario["id"],
        "mast_mode": scenario["mast_mode"],
        "business_exception": scenario["business_exception"],
        "catalog_stock": scenario["catalog_stock"],
        "actual_stock": scenario["actual_stock"],
        "expected_behavior": "STOP_CHECKOUT",
        "actual_output": output,
        "error": error,
        "pass": passed
    }

def main():
    with open(SCENARIO_FILE, "r") as f:
        scenarios = json.load(f)

    rows = []
    for scenario in scenarios:
        rows.append(run_scenario(scenario))

    with open(RESULT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Results saved to {RESULT_FILE}")

if __name__ == "__main__":
    main()