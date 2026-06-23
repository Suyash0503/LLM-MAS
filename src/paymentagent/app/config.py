import os
from dotenv import load_dotenv
 
load_dotenv()
 
# Agent HTTP server
AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
 
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.2:1b ")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "payment_agent")