import logging 
from fastapi import FastAPI
from app.router import router as payment_router

logger = logging.getLogger("payment-agent")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
 
app = FastAPI(title="Payment Agent")


app.include_router(payment_router)