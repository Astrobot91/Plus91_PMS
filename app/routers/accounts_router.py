from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.accounts.account import (
    ViewAccountsResponse, AccountUpdateRequest, BulkAccountResponse
)
from app.schemas.accounts.joint_account import (
    JointAccountCreateRequest,
    JointAccountResponse,
    JointAccountUpdateRequest
)
from app.schemas.accounts.account_allocation import (
    AccountAllocationsSheetResponse,
)
from app.services.accounts.account_allocation_service import AccountAllocationService
from app.services.accounts.joint_account_service import JointAccountService
from app.services.accounts.account_service import AccountService
from app.models.portfolio import Basket
from app.logger import logger
from typing import List, Dict, Any

account_router = APIRouter(prefix="/accounts", tags=["Accounts"])
joint_account_router = APIRouter(prefix="/joint-accounts", tags=["Joint Accounts"])
account_allocations_router = APIRouter(prefix="/account-allocations", tags=["Account Allocations"])


@account_router.get("/list", response_model=ViewAccountsResponse)
async def get_view_accounts(db: AsyncSession = Depends(get_db)):
    """
    Retrieves a unified list of single and joint accounts with bracket, portfolio,
    and performance data, returned in a standardized format.
    """
    try:
        data = await AccountService.get_all_accounts_view(db)
        return ViewAccountsResponse(
            status="success",
            data=data
        )
    except Exception as e:
        logger.error(f"Error while fetching all accounts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve accounts."
        )

@account_router.post("/update", response_model=BulkAccountResponse)
async def update_accounts(
    updates: List[AccountUpdateRequest],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update accounts for partial success:
    * single: update pf/cash/invested + optional TWRR
    * joint: only TWRR fields
    * Then recalc any linked joint for single changes
    """
    try:
        return await AccountService.bulk_update_accounts(db, updates)
    except Exception as e:
        logger.error(f"Error updating accounts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update acc    ounts."
        )

@joint_account_router.post("/", response_model=JointAccountResponse)
async def create_joint_account(
    payload: JointAccountCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to create a new JointAccount.
    """
    logger.info("Endpoint '/joint-accounts' [POST] called with data: %s", payload.model_dump())
    try:
        result = await JointAccountService.create_joint_account(db, payload)
        if not result:
            logger.error("Unable to create joint account.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to create joint account."
            )
        logger.info("Endpoint '/joint-accounts' [POST] completed successfully: %s", result)
        return result
    except ValueError as ve:
        logger.error("Validation error in '/joint-accounts' [POST]: %s", str(ve))
        raise HTTPException(
            status_code=400,
            detail=str(ve)
        )
    except Exception as e:
        logger.critical("Critical error in '/joint-accounts' [POST]: %s", str(e), exc_info=True, stack_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create joint account due to server error"
        )

@joint_account_router.put("/{joint_account_id}", response_model=JointAccountResponse)
async def update_joint_account(
    joint_account_id: str,
    payload: JointAccountUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to update an existing JointAccount.
    """
    logger.info(
        "Endpoint '/joint-accounts/%s' [PUT] called with data: %s",
        joint_account_id, payload.model_dump()
    )
    try:
        result = await JointAccountService.update_joint_account(db, joint_account_id, payload)
        if not result:
            logger.error("Joint account '%s' not found or could not be updated.", joint_account_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Joint account {joint_account_id} not found."
            )
        logger.info("Endpoint '/joint-accounts/%s' [PUT] completed successfully: %s", joint_account_id, result)
        return result
    except ValueError as ve:
        logger.error("Validation error in '/joint-accounts/%s' [PUT]: %s", joint_account_id, str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.critical("Critical error in '/joint-accounts/%s' [PUT]: %s", joint_account_id, str(e), exc_info=True, stack_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update joint account due to server error"
        )

@joint_account_router.delete("/{joint_account_id}", response_model=JointAccountResponse)
async def delete_joint_account(
    joint_account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to delete the specified JointAccount.
    """
    logger.info("Endpoint '/joint-accounts/%s' [DELETE] called", joint_account_id)
    try:
        result = await JointAccountService.delete_joint_account(db, joint_account_id)
        if not result:
            logger.warning("Joint account '%s' not found. Cannot delete.", joint_account_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Joint account {joint_account_id} not found."
            )
        logger.info("Endpoint '/joint-accounts/%s' [DELETE] completed successfully: %s", joint_account_id, result)
        return result
    except ValueError as ve:
        logger.error("Validation error in '/joint-accounts/%s' [DELETE]: %s", joint_account_id, str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.critical("Critical error in '/joint-accounts/%s' [DELETE]: %s", joint_account_id, str(e), exc_info=True, stack_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete joint account due to server error"
        )
    

async def get_basket_names(db: AsyncSession) -> List[str]:
    """Get all basket names for dynamic model creation."""
    result = await db.execute(select(Basket.basket_name).order_by(Basket.basket_id))
    return [r[0] for r in result.fetchall()]

@account_allocations_router.get(
    "/sheet-data",
    response_model=AccountAllocationsSheetResponse,
    summary="Get Account Allocations for Google Sheets",
    description="Returns account allocation data formatted for Google Sheets integration",
)
async def get_sheet_allocations(db: AsyncSession = Depends(get_db)):
    """Get account allocations data formatted for Google Sheets."""
    try:
        logger.debug("Fetching sheet allocations data")
        data = await AccountAllocationService.get_accounts_basket_allocations(db)
        logger.debug(f"Successfully retrieved sheet data: {len(data['data'])} rows")
        return AccountAllocationsSheetResponse(
            data=data["data"],
            baskets=data["baskets"]
        )
    except Exception as e:
        logger.error(f"Error fetching sheet allocations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch sheet allocations data."
        )

@account_allocations_router.post(
    "/sheet-update",
    summary="Update Account Allocations from Google Sheets",
    description="Process and update account allocations from Google Sheets data",
)
async def update_from_sheet(
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """Update account allocations from Google Sheets data."""
    try:
        logger.debug("Received data object for update")
        return await AccountAllocationService.update_account_allocations_from_sheet_json(
            db, request_data.get("data")
        )
    except Exception as e:
        logger.error(f"Error updating allocations from sheet: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update account allocations from sheet data."
        )
