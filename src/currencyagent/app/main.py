import logging 
from fastapi import FastAPI
from app.router import router as currency_router

logger = logging.getLogger("currency-agent")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
 
app = FastAPI(title="Currency Agent")


app.include_router(currency_router)