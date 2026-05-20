import os

FAULT_MODE = os.getenv("FAULT_MODE", "none")
CATALOG_STOCK = int(os.getenv("CATALOG_STOCK", "5"))
ACTUAL_STOCK = int(os.getenv("ACTUAL_STOCK", "0"))
ORDER_QUANTITY = int(os.getenv("ORDER_QUANTITY", "1"))