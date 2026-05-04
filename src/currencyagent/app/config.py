import os
from dotenv import load_dotenv
 
load_dotenv()
 
CURRENCY_HOST = os.getenv("CURRENCY_HOST", "127.0.0.1")
CURRENCY_PORT = os.getenv("CURRENCY_PORT", "7000")
 
# Agent HTTP server
AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8002"))
 
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.1")