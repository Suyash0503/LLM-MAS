from langchain_ollama import ChatOllama
from app.config import OLLAMA_MODEL, OLLAMA_BASE_URL
 
 
def get_ollama_llm() -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
    )