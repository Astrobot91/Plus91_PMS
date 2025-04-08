from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.accounts.accounts_data_service import AccountTimePeriodsService
from app.schemas.accounts.account_time_periods import AccountTimePeriodsResponse
from app.services.accounts.accounts_data_service import AccountCashflowProgressionService
from app.schemas.accounts.account_cashflow_progression import AccountCashflowProgressionResponse
from typing import List, Optional

accounts_data_router = APIRouter(prefix="/accounts-data", tags=["Accounts Data"])

@accounts_data_router.get("/time-periods/{owner_id}", response_model=List[AccountTimePeriodsResponse])
async def get_time_periods(
    owner_id: str,
    owner_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Fetch time periods for a given owner_id and optional owner_type."""
    try:
        time_periods = await AccountTimePeriodsService.get_time_periods_by_owner_id(
            db, owner_id, owner_type
        )
        if not time_periods:
            raise HTTPException(
                status_code=404,
                detail="No time periods found for this owner_id"
            )
        return time_periods
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve time periods due to server error"
        )

@accounts_data_router.get("/cashflow-progression/{owner_id}", response_model=List[AccountCashflowProgressionResponse])
async def get_cashflow_progression(
    owner_id: str,
    owner_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
    ):
    """
    Fetch cashflow progression data for a given owner_id and optional owner_type.
    
    Args:
        owner_id (str): The ID of the account owner.
        owner_type (Optional[str]): The type of owner ("single" or "joint"), if specified.
        db (AsyncSession): The database session, injected via dependency.
    
    Returns:
        List[AccountCashflowProgressionResponse]: A list of cashflow progression records.
    
    Raises:
        HTTPException: If no data is found (404), input is invalid (400), or a server error occurs (500).
    """
    try:
        cashflow_progression = await AccountCashflowProgressionService.get_cashflow_progression_by_owner_id(
            db, owner_id, owner_type
        )
        if not cashflow_progression:
            raise HTTPException(
                status_code=404,
                detail=f"No cashflow progression found for owner_id: {owner_id}"
            )
        
        return cashflow_progression
    
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cashflow progression due to an internal server error"
        )

