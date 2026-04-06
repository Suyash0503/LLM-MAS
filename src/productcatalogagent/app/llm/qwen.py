from langchain_ollama import ChatOllama
from app.config import QWEN_MODEL


def get_qwen_llm():
    return ChatOllama(
        model=QWEN_MODEL,
        temperature=0
    )