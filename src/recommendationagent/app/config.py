import os
from dotenv import load_dotenv

load_dotenv()

RECOMMENDATION_HOST = os.getenv("RECOMMENDATION_HOST", "127.0.0.1")
RECOMMENDATION_PORT = os.getenv("RECOMMENDATION_PORT", "8080")

PRODUCT_CATALOG_HOST = os.getenv("PRODUCT_CATALOG_HOST", "127.0.0.1")
PRODUCT_CATALOG_PORT = os.getenv("PRODUCT_CATALOG_PORT", "3550")

AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8002"))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")