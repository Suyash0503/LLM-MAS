import os
from dotenv import load_dotenv

load_dotenv()

PRODUCT_CATALOG_HOST = os.getenv("PRODUCT_CATALOG_HOST", "127.0.0.1")
PRODUCT_CATALOG_PORT = os.getenv("PRODUCT_CATALOG_PORT", "3550")

AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))

QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3")