from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.accounts.account import (
    ViewAccountsResponse, AccountUpdateRequest, BulkAccountResponse
)
from app.schemas.accounts.joint_account import (
    JointAccountCreateRequest,
    JointAccountResponse,
    JointAccountDeleteRequest,
    JointAccountUpdateRequest
)
from app.services.accounts.joint_account_service import JointAccountService
from app.services.accounts.account_service import AccountService
from app.logger import logger
from typing import List

account_router = APIRouter(prefix="/accounts", tags=["Accounts"])
joint_account_router = APIRouter(prefix="/joint-accounts", tags=["Joint Accounts"])

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
    data_list: List[AccountUpdateRequest],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update accounts for partial success:
    * single: update pf/cash/invested + optional TWRR
    * joint: only TWRR fields
    * Then recalc any linked joint for single changes
    """
    try:
        resp = await AccountService.bulk_update_accounts(db, data_list)
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@joint_account_router.post("/", response_model=JointAccountResponse)
async def create_joint_account_endpoint(
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
async def update_joint_account_endpoint(
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Joint account '{joint_account_id}' not found or could not be updated."
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
async def delete_joint_account_endpoint(
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
                detail=f"Joint account '{joint_account_id}' not found."
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
    

