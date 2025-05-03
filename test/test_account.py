#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the project root to the path so imports work properly
sys.path.append('/home/admin/Plus91Backoffice/Plus91_Backend')

from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.accounts import SingleAccount, AccountBracketBasketAllocation
from app.scripts.db_processors.ideal_pf_processor import IdealPfProcessor
from app.logger import logger

async def test_single_account():
    """Test the ideal portfolio processor with a single account (ACC_000319)."""
    print("Starting test for account ACC_000319")
    try:
        async with AsyncSessionLocal() as db:
            # Get the account
            account_id = "ACC_000319"
            print(f"Looking up account: {account_id}")
            account_query = select(SingleAccount).where(
                SingleAccount.single_account_id == account_id
            )
            account_result = await db.execute(account_query)
            account = account_result.scalar_one_or_none()

            if not account:
                print(f"Account {account_id} not found")
                return

            # Print current values
            print(f"Account ID: {account.single_account_id}")
            print(f"Account name: {account.account_name}")
            print(f"Current bracket_id: {account.bracket_id}")
            print(f"Current portfolio_id: {account.portfolio_id}")
            print(f"Current cash_value: {account.cash_value}")
            print(f"Current pf_value: {account.pf_value}")
            print(f"Current total_holdings: {account.total_holdings}")

            # Check if account has custom allocations
            print("Checking for custom allocations...")
            query = select(AccountBracketBasketAllocation).where(
                AccountBracketBasketAllocation.owner_id == account_id,
                AccountBracketBasketAllocation.owner_type == "single",
                AccountBracketBasketAllocation.is_custom == True
            )
            result = await db.execute(query)
            custom_allocations = result.scalars().all()
            print(f"Has custom allocations: {len(custom_allocations) > 0}")
            
            if custom_allocations:
                print("Custom allocations:")
                for alloc in custom_allocations:
                    print(f"- Basket ID: {alloc.basket_id}, Allocation: {alloc.allocation_pct}%")

            # Create processor
            print("Creating IdealPfProcessor...")
            processor = IdealPfProcessor(db)
            
            # Test with this single account
            print("Processing account ideal portfolio...")
            await processor.process_account_ideal_portfolio(
                account_id,
                "single",
                account.total_holdings or 0
            )
            
            # Get updated account details
            print("Getting updated account details...")
            account_query = select(SingleAccount).where(
                SingleAccount.single_account_id == account_id
            )
            account_result = await db.execute(account_query)
            updated_account = account_result.scalar_one_or_none()
            
            # Print updated values
            print("\nAfter processing:")
            print(f"Account ID: {updated_account.single_account_id}")
            print(f"Current bracket_id: {updated_account.bracket_id}")
            print(f"Current portfolio_id: {updated_account.portfolio_id}")
            
            # Check if portfolio_id changed for a custom allocation account
            if len(custom_allocations) > 0 and account.portfolio_id != updated_account.portfolio_id:
                print("WARNING: portfolio_id changed for a custom allocation account!")
            else:
                print("SUCCESS: portfolio_id handling is working correctly")
                
    except Exception as e:
        print(f"Error testing account: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    print("Starting script")
    asyncio.run(test_single_account())
    print("Script completed")