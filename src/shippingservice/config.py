import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI     = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "shipping_agent_db")

LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.1")
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://localhost:11434/v1")