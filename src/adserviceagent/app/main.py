from fastapi import FastAPI
from app.router import router

app = FastAPI(
    title="Ad Service Agent",
    version="1.0.0"
)

app.include_router(router)