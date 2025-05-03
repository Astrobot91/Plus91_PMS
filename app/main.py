from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers.clients_router import (
    client_router, distributor_router, broker_router
)
from app.routers.accounts_router import (
    account_router, joint_account_router, account_allocations_router
)
from app.routers.portfolios_router import portfolio_router
from app.routers.report_router import report_router
from app.routers.accounts_data_router import accounts_data_router
import uvicorn
import logging
from app.logger import logger


app = FastAPI(
    title="Plus91 Client Management System API",
    description="API for managing clients, brokers, distributors, and types.",
    version="1.0.0"
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        f"Incoming request: {request.method} {request.url} - Params: {request.query_params} - Body: {await request.body()}"
    )
    try:
        response = await call_next(request)
        logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url} - Error: {str(e)}", exc_info=True)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(broker_router)
app.include_router(distributor_router)
app.include_router(client_router)
app.include_router(joint_account_router)
app.include_router(account_router)
app.include_router(report_router)
app.include_router(accounts_data_router)
app.include_router(account_allocations_router)


@app.get("/", summary="Root Endpoint")
async def root():
    return {"message": "Plus91 Client Management System API is running."}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
