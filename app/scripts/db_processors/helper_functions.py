import logging
from sqlalchemy import select
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.logger import logger
from typing import List

def _generate_historical_month_ends(acc_start_date: date, today: date) -> List[date]:
    """Generate a list of month-end dates from account start date to today."""
    try:
        if isinstance(acc_start_date, str):
            acc_start_date = datetime.strptime(acc_start_date, "%Y-%m-%d").date()
        elif not isinstance(acc_start_date, date):
            raise ValueError(f"acc_start_date must be a datetime.date or string, got {type(acc_start_date)}")

        if isinstance(today, str):
            today = datetime.strptime(today, "%Y-%m-%d").date()
        elif not isinstance(today, date):
            raise ValueError(f"today must be a datetime.date or string, got {type(today)}")

        historical_dates = []
        current_date = acc_start_date.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        last_month_end = today.replace(day=1) - timedelta(days=1)
        
        while current_date <= last_month_end:
            historical_dates.append(current_date)
            current_date = (current_date.replace(day=1) + relativedelta(months=2)) - timedelta(days=1)
        return historical_dates
    except ValueError as e:
        logger.error(f"Invalid date format or value in generating historical month ends: {e}")
        return []
    except Exception as e:
        logger.error(f"Error generating historical month ends: {e}")
        return []

async def _get_existing_snapshot_dates(db: AsyncSession, account_id: str) -> list:
    """Fetch existing portfolio snapshot dates for an account."""
    try:
        result = await db.execute(
            select(AccountActualPortfolio.snapshot_date)
            .where(AccountActualPortfolio.owner_id == account_id)
            .where(AccountActualPortfolio.owner_type == 'single')
            .distinct()
        )
        existing_dates = [row[0] for row in result.all()]
        return existing_dates
    except Exception as e:
        logger.error(f"Error fetching existing snapshot dates for account {account_id}: {e}")
        return []
