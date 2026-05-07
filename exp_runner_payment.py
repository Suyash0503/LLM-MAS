import subprocess
import json
import requests
import time
import os
import shutil

# -------------------------
# CONFIG
# -------------------------
BASELINE_HOST = "localhost:50051"
AGENT_URL = "http://localhost:8001/payment/charge"


# -------------------------
# CALL BASELINE (gRPC)
# -------------------------
def call_baseline():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROTO_PATH = os.path.join(BASE_DIR, "src/paymentservice/proto")

    grpcurl_path = shutil.which("grpcurl")
    if not grpcurl_path:
        return {"error": "grpcurl not found in PATH"}


    cmd = [
        grpcurl_path,
        "-plaintext",
        "-import-path", PROTO_PATH,
        "-proto", "demo.proto",
        "-d",
        json.dumps({
            "amount": {
                "currency_code": "USD",
                "units": 10,
                "nanos": 0
            },
            "credit_card": {
                "credit_card_number": "4111111111111111",
                "credit_card_cvv": 123,
                "credit_card_expiration_year": 2030,
                "credit_card_expiration_month": 12
            }
        }),
        BASELINE_HOST,
        "hipstershop.PaymentService/Charge"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    return json.loads(result.stdout)


# -------------------------
# CALL AGENT (REST)
# -------------------------
def call_agent():
    payload = {
        "query": "charge card",
        "currency_code": "USD",
        "units": 10,
        "nanos": 0,
        "credit_card_number": "4111111111111111",
        "credit_card_cvv": 123,
        "credit_card_expiration_year": 2030,
        "credit_card_expiration_month": 12
    }

    try:
        res = requests.post(AGENT_URL, json=payload, timeout=20)
        return res.json()
    except Exception as e:
        return {"error": str(e)}
    
# -------------------------
# DB functions
# -------------------------
    
def clear_agent_db():
    try:
        res = requests.post("http://localhost:8001/clear_payments")
        print("DB Cleared:", res.json())
    except Exception as e:
        print("DB clear failed:", e)
    
def get_agent_db_count():
    try:
        res = requests.get("http://localhost:8001/payment/transactions/count")
        return res.json()
    except:
        return {}


# -------------------------
# NORMALIZE RESPONSE
# -------------------------
def normalize_baseline(resp):
    if "error" in resp:
        return {"success": False, "error": resp["error"]}
    return {"success": True}


def normalize_agent(resp):
    data = resp.get("data", {})
    if not data.get("success"):
        return {"success": False, "error": data.get("error")}
    return {"success": True}


# -------------------------
# COMPARE
# -------------------------
def compare(baseline, agent):
    if baseline["success"] != agent["success"]:
        return False

    if not baseline["success"]:
        return baseline["error"] == agent["error"]

    return True


# -------------------------
# RUN EXPERIMENT
# -------------------------
def run_test(n=5):
    success_count = 0

    for i in range(n):
        print(f"\n--- Test {i+1} ---")

        clear_agent_db()

        baseline_raw = call_baseline()
        agent_raw = call_agent()

        print("Baseline:", baseline_raw)
        print("Agent:", agent_raw)

        baseline = normalize_baseline(baseline_raw)
        agent = normalize_agent(agent_raw)

        is_match = compare(baseline, agent)

        print("Match:", is_match)

        # DB validation logic 
        db = get_agent_db_count()
        print("DB Count:", db)

        if agent["success"]:
            if db.get("count", 0) == 1:
                print("DB OK (transaction stored)")
            else:
                print("DB ERROR (missing insert)")
        else:
            if db.get("count", 0) == 0:
                print("DB OK (no insert)")
            else:
                print("DB ERROR (unexpected insert)")

        if is_match:
            success_count += 1

        time.sleep(1)

    print("\n====================")
    print(f"Consistency: {success_count}/{n} = {(success_count/n)*100:.2f}%")
    print("====================")


if __name__ == "__main__":
    run_test(10)