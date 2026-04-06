from fastapi import FastAPI
from app.router import router

app = FastAPI(title="Product Catalog Agent")
app.include_router(router)