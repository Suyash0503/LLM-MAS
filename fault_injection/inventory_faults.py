from fault_injection.fault_config import FAULT_MODE, CATALOG_STOCK, ACTUAL_STOCK, ORDER_QUANTITY

action_log = []

def check_catalog_stock(product_id: str):
    action_log.append("check_catalog_stock")
    return {
        "product_id": product_id,
        "source": "product_catalog",
        "available_stock": CATALOG_STOCK
    }

def check_actual_inventory(product_id: str):
    action_log.append("check_actual_inventory")
    return {
        "product_id": product_id,
        "source": "warehouse_inventory",
        "actual_stock": ACTUAL_STOCK
    }

def reserve_inventory(product_id: str, quantity: int):
    action_log.append("reserve_inventory")

    if FAULT_MODE == "FM-1.3":
        action_log.append("reserve_inventory")  # injected repeated action

    if ACTUAL_STOCK < quantity:
        return {
            "status": "failed",
            "reason": "insufficient_actual_stock"
        }

    return {
        "status": "reserved",
        "quantity": quantity
    }

def communicate_inventory_result():
    catalog = check_catalog_stock("product-1")
    actual = check_actual_inventory("product-1")

    mismatch = catalog["available_stock"] != actual["actual_stock"]

    if FAULT_MODE == "FM-2.4":
        return {
            "fault_mode": FAULT_MODE,
            "message_to_checkout": "stock_available",
            "visible_stock": catalog["available_stock"],
            "mismatch_hidden": True
        }

    return {
        "fault_mode": FAULT_MODE,
        "message_to_checkout": "inventory_mismatch_detected" if mismatch else "stock_available",
        "catalog_stock": catalog["available_stock"],
        "actual_stock": actual["actual_stock"],
        "mismatch": mismatch
    }

def final_inventory_verification():
    action_log.append("final_inventory_verification")

    if FAULT_MODE == "FM-3.2":
        return {
            "verification_performed": False,
            "status": "skipped"
        }

    actual = check_actual_inventory("product-1")
    return {
        "verification_performed": True,
        "stock_ok": actual["actual_stock"] >= ORDER_QUANTITY
    }