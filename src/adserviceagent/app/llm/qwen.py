from langchain_ollama import ChatOllama
from app.config import OLLAMA_MODEL, OLLAMA_BASE_URL




def get_qwen_llm():
    return ChatOllama(
        model = OLLAMA_MODEL,
        temperature=0
    )