import os
from dotenv import load_dotenv

ADSERVICE_HOST = os.getenv("ADSERVICE_HOST", "localhost")
ADSERVICE_PORT = int(os.getenv("ADSERVICE_PORT", "9555"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:latest")
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"