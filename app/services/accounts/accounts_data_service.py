from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.accounts.account_time_periods import AccountTimePeriods
from app.models.accounts.account_cashflow_progression import AccountCashflowProgression
from typing import List, Optional
from app.logger import logger, log_function_call 

class AccountTimePeriodsService:
    @staticmethod
    @log_function_call
    async def get_time_periods_by_owner_id(
        db: AsyncSession,
        owner_id: str,
        owner_type: Optional[str] = None
    ) -> List[AccountTimePeriods]:
        query = select(AccountTimePeriods).where(AccountTimePeriods.owner_id == owner_id)
        
        if owner_type:
            query = query.where(AccountTimePeriods.owner_type == owner_type)
        
        result = await db.execute(query)
        return result.scalars().all()
    
class AccountCashflowProgressionService:
    @staticmethod
    async def get_cashflow_progression_by_owner_id(
        db: AsyncSession,
        owner_id: str,
        owner_type: Optional[str] = None
    ) -> List[AccountCashflowProgression]:
        """
        Retrieve cashflow progression records for a given owner_id and optional owner_type.
        
        Args:
            db (AsyncSession): The asynchronous database session.
            owner_id (str): The ID of the account owner.
            owner_type (Optional[str]): The type of owner ("single" or "joint"), if specified.
        
        Returns:
            List[AccountCashflowProgression]: A list of matching cashflow progression records.
        """
        query = select(AccountCashflowProgression).where(AccountCashflowProgression.owner_id == owner_id)
        
        if owner_type:
            query = query.where(AccountCashflowProgression.owner_type == owner_type)
        
        result = await db.execute(query)
        return result.scalars().all()