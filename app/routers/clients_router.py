from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.database import get_db
from app.schemas.clients.client_details import (
    ClientCreateRequest,
    BulkClientResponse,
    ClientListResponse
)
from app.services.clients.clients_service import ClientService
from app.services.clients.distributors_service import DistributorService
from app.services.clients.brokers_service import BrokerService

client_router = APIRouter(prefix="/clients", tags=["Clients"])
distributor_router = APIRouter(prefix="/distributors", tags=["Distributors"])
broker_router = APIRouter(prefix="/brokers", tags=["Brokers"])

@client_router.get("/list", response_model=List[ClientListResponse])
async def get_all_clients_endpoint(
    db: AsyncSession = Depends(get_db)
):
    """Fetch complete client data for sheet updates"""
    try:
        result = await ClientService.get_all_clients(db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve client list due to server error"
        )

@client_router.post("/add", response_model=BulkClientResponse)
async def add_clients(
    data_list: List[ClientCreateRequest],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk create clients with partial success. Each row that fails
    is skipped, others are committed.
    """
    try:
        result = await ClientService.bulk_create_clients(db, data_list)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@client_router.post("/update", response_model=BulkClientResponse)
async def update_clients(
    data_list: List[ClientCreateRequest],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update clients with partial success. Rows that fail
    don't block others from succeeding.
    """
    try:
        result = await ClientService.bulk_update_clients(db, data_list)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@client_router.post("/delete", response_model=BulkClientResponse)
async def delete_clients(
    client_ids: List[str],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk delete clients. If a row fails, it's skipped, others succeed.
    The returned BulkClientResponse indicates row-by-row results.
    """
    try:
        result = await ClientService.bulk_delete_clients(db, client_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@distributor_router.get("/", response_model=List[Dict[str, Any]])
async def read_distributors(db: AsyncSession = Depends(get_db)):
    """Get data for all the distributors in the DB."""
    return await DistributorService.get_distributors(db)

@distributor_router.post("/add", response_model=Dict[str, Any])
async def create_distributor(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    let_name = (payload.get("value") or "").strip()
    if not let_name:
        raise HTTPException(status_code=400, detail="Distributor name is required")
    try:
        return await DistributorService.add_distributor(db, let_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@distributor_router.put("/update", response_model=Dict[str, Any])
async def modify_distributor(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    old_value = (payload.get("old_value") or "").strip()
    new_value = (payload.get("new_value") or "").strip()
    if not old_value or not new_value:
        raise HTTPException(status_code=400, detail="Both old and new distributor names are required")
    try:
        return await DistributorService.update_distributor(db, old_value, new_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@distributor_router.delete("/delete", response_model=Dict[str, Any])
async def remove_distributor(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    name = (payload.get("value") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Distributor name is required")
    try:
        return await DistributorService.delete_distributor(db, name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@broker_router.get("/", response_model=List[Dict[str, Any]])
async def read_brokers(db: AsyncSession = Depends(get_db)):
    """Get data for all the brokers in the DB."""
    return await BrokerService.get_brokers(db)

@broker_router.post("/add", response_model=Dict[str, Any])
async def create_broker(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    broker_name = (payload.get("value") or "").strip()
    if not broker_name:
        raise HTTPException(status_code=400, detail="Broker name is required")
    try:
        return await BrokerService.add_broker(db, broker_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@broker_router.put("/update", response_model=Dict[str, Any])
async def modify_broker(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    old_value = (payload.get("old_value") or "").strip()
    new_value = (payload.get("new_value") or "").strip()
    if not old_value or not new_value:
        raise HTTPException(status_code=400, detail="Both old and new broker names are required")
    try:
        return await BrokerService.update_broker(db, old_value, new_value)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@broker_router.delete("/delete", response_model=Dict[str, Any])
async def remove_broker(payload: Dict[str, str], db: AsyncSession = Depends(get_db)):
    broker_name = (payload.get("value") or "").strip()
    if not broker_name:
        raise HTTPException(status_code=400, detail="Broker name is required")
    try:
        return await BrokerService.delete_broker(db, broker_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))