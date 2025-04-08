# app/scripts/fetch_accounts.py

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.services.accounts.account_service import AccountService

async def run_fetch_accounts():
    """
    Execute the get_single_accounts_with_broker_codes function and print results.
    """
    async with AsyncSessionLocal() as db:
        try:
            accounts_data = await AccountService.get_single_accounts_with_broker_info(db)
            for account in accounts_data:
                print(f"Account ID: {account['account_id']}, Broker Code: {account['broker_code']}, Broker Name: {account['broker_name']}, Start Date: {account['acc_start_date']}")
                print(f"Account ID: {account['account_id']}, Broker Code: {account['broker_code']}, Broker Name: {account['broker_name']}, Start Date: {type(account['acc_start_date'])}")
            print(f"Total accounts retrieved: {len(accounts_data)}")
        except Exception as e:
            print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_fetch_accounts())