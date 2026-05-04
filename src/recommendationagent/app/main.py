from fastapi import FastAPI
from app.router import router
 
app = FastAPI(title="Recommendation Agent")
app.include_router(router)