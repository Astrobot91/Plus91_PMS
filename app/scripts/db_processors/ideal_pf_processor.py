import asyncio
import pandas as pd
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select, delete, func, update, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.portfolio import (
    Bracket,
    Basket,
    BasketStockMapping,
    PfBracketBasketAllocation,
)
from app.models.accounts import (
    AccountIdealPortfolio,
    AccountActualPortfolio,
    SingleAccount,
    JointAccount,
    JointAccountMapping,
    AccountBracketBasketAllocation
)
from app.models.clients.client_details import Client
from app.logger import logger
from app.database import AsyncSessionLocal


class IdealPfProcessor:
    """Process and update ideal portfolios for accounts based on brackets and baskets.
    
    This processor maintains monthly snapshots of ideal portfolios for each account based on
    their total holdings and bracket-based allocations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the processor with database session.
        
        Args:
            db (AsyncSession): SQLAlchemy async database session
        """
        self.db = db
        self.exceptions_df = self._load_exceptions()
        self.client_broker_cache = {} 

    def _load_exceptions(self) -> pd.DataFrame:
        """Load exceptions from the Excel file.
        
        Returns:
            pd.DataFrame: DataFrame containing exceptions
        """
        try:
            file_path = '/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_reco_exceptions.xlsx'
            if os.path.exists(file_path):
                # Specifically load data from the 'exception sheet' 
                df = pd.read_excel(file_path, sheet_name='exception sheet')
                logger.info(f"Loaded {len(df)} exceptions from {file_path}, sheet 'exception sheet'")
                return df
            else:
                logger.warning(f"Exceptions file not found: {file_path}")
                return pd.DataFrame(columns=['trading_symbol', 'quantity', 'broker_code'])
        except Exception as e:
            logger.error(f"Error loading exceptions: {e}")
            return pd.DataFrame(columns=['trading_symbol', 'quantity', 'broker_code'])

    async def _get_bracket_for_amount(self, amount: float) -> Optional[Dict]:
        """Get the appropriate bracket based on investment amount.

        Args:
            amount (float): The investment amount to find bracket for

        Returns:
            Optional[Dict]: Bracket details if found, None otherwise
        """
        try:
            query = select(Bracket).where(
                Bracket.bracket_min <= amount,
                Bracket.bracket_max >= amount
            )
            result = await self.db.execute(query)
            bracket = result.scalar_one_or_none()

            if not bracket:
                logger.warning(f"No bracket found for amount {amount}")
                return None

            return {
                "bracket_id": bracket.bracket_id,
                "bracket_name": bracket.bracket_name
            }
        except Exception as e:
            logger.error(f"Error finding bracket for amount {amount}: {e}")
            await self.db.rollback()
            return None

    async def _get_basket_allocations(self, bracket_id: int) -> Optional[List[Dict]]:
        """Get basket allocations for a given bracket.

        Args:
            bracket_id (int): ID of the bracket

        Returns:
            Optional[List[Dict]]: List of basket allocations if found, None otherwise
        """
        query = select(
            PfBracketBasketAllocation,
            Basket.basket_name
        ).join(
            Basket,
            PfBracketBasketAllocation.basket_id == Basket.basket_id
        ).where(
            PfBracketBasketAllocation.bracket_id == bracket_id
        )
        result = await self.db.execute(query)
        allocations = result.all()

        if not allocations:
            logger.warning(f"No basket allocations found for bracket {bracket_id}")
            return None

        return [{
            "basket_id": alloc[0].basket_id,
            "basket_name": alloc[1],
            "allocation_pct": alloc[0].allocation_pct
        } for alloc in allocations]

    async def _get_basket_stocks(self, basket_id: int) -> Optional[List[Dict]]:
        """Get stock mappings for a basket with their multipliers.

        Args:
            basket_id (int): ID of the basket

        Returns:
            Optional[List[Dict]]: List of stock mappings if found, None otherwise
        """
        query = select(BasketStockMapping).where(
            BasketStockMapping.basket_id == basket_id
        )
        result = await self.db.execute(query)
        stocks = result.scalars().all()

        if not stocks:
            logger.warning(f"No stock mappings found for basket {basket_id}")
            return None

        total_multiplier = sum(stock.multiplier for stock in stocks)
        return [{
            "trading_symbol": stock.trading_symbol,
            "multiplier": stock.multiplier,
            "weight": stock.multiplier / total_multiplier
        } for stock in stocks]

    async def _get_last_snapshot_date(self, owner_id: str, owner_type: str) -> Optional[date]:
        """Get the most recent snapshot date for an account.

        Args:
            owner_id (str): Account ID
            owner_type (str): Account type (single/joint)

        Returns:
            Optional[date]: Latest snapshot date if exists, None otherwise
        """
        query = select(func.max(AccountIdealPortfolio.snapshot_date)).where(
            AccountIdealPortfolio.owner_id == owner_id,
            AccountIdealPortfolio.owner_type == owner_type
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _delete_current_month_portfolio(
        self,
        owner_id: str,
        owner_type: str,
        snapshot_date: date
    ) -> None:
        """Delete ideal portfolio records for current month.

        Args:
            owner_id (str): Account ID
            owner_type (str): Account type (single/joint)
            snapshot_date (date): Current snapshot date
        """
        current_month_start = snapshot_date.replace(day=1)
        await self.db.execute(
            delete(AccountIdealPortfolio).where(
                AccountIdealPortfolio.owner_id == owner_id,
                AccountIdealPortfolio.owner_type == owner_type,
                AccountIdealPortfolio.snapshot_date >= current_month_start
            )
        )

    async def _update_account_bracket(
        self,
        account_id: str, 
        account_type: str,
        bracket_id: int
    ) -> None:
        """Update bracket_id in the appropriate account table."""
        try:
            # Check if account has custom allocations
            has_custom = await self._has_custom_allocations(account_id, account_type)
            if account_type == "single":
                if has_custom:
                    # Only update bracket_id for custom accounts, preserve portfolio_id
                    await self.db.execute(
                        update(SingleAccount)
                        .where(SingleAccount.single_account_id == account_id)
                        .values(bracket_id=bracket_id)
                    )
                    logger.info(f"Updated bracket only for custom portfolio single account {account_id}")
                else:
                    # Update both bracket_id and portfolio_id for standard accounts
                    await self.db.execute(
                        update(SingleAccount)
                        .where(SingleAccount.single_account_id == account_id)
                        .values(bracket_id=bracket_id, portfolio_id=1)  # Set to Standard Portfolio
                    )
                    logger.info(f"Updated bracket and set standard portfolio for single account {account_id}")
            else:
                if has_custom:
                    # Only update bracket_id for custom accounts, preserve portfolio_id
                    await self.db.execute(
                        update(JointAccount)
                        .where(JointAccount.joint_account_id == account_id)
                        .values(bracket_id=bracket_id)
                    )
                    logger.info(f"Updated bracket only for custom portfolio joint account {account_id}")
                else:
                    # Update both bracket_id and portfolio_id for standard accounts
                    await self.db.execute(
                        update(JointAccount)
                        .where(JointAccount.joint_account_id == account_id)
                        .values(bracket_id=bracket_id, portfolio_id=1)  # Set to Standard Portfolio
                    )
                    logger.info(f"Updated bracket and set standard portfolio for joint account {account_id}")
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating bracket for {account_type} account {account_id}: {e}")
            await self.db.rollback()
            raise

    async def _get_standard_allocations(self, bracket_id: int) -> List[Dict]:
        """Get standard basket allocations for a bracket from pf_bracket_basket_allocation."""
        try:
            query = select(PfBracketBasketAllocation).where(
                PfBracketBasketAllocation.bracket_id == bracket_id,
                PfBracketBasketAllocation.portfolio_id == 1  # Standard portfolio
            )
            result = await self.db.execute(query)
            allocations = result.scalars().all()
            return [{
                "bracket_id": alloc.bracket_id,
                "basket_id": alloc.basket_id,
                "allocation_pct": alloc.allocation_pct
            } for alloc in allocations]
        except Exception as e:
            logger.error(f"Error getting standard allocations for bracket {bracket_id}: {e}")
            return []

    async def _update_account_allocations(
        self,
        owner_id: str,
        owner_type: str,
        bracket_id: int,
        is_custom: bool = False
    ) -> None:
        """Update or insert account basket allocations."""
        try:
            # Delete existing non-custom allocations for this account
            if not is_custom:
                await self.db.execute(
                    delete(AccountBracketBasketAllocation).where(
                        AccountBracketBasketAllocation.owner_id == owner_id,
                        AccountBracketBasketAllocation.owner_type == owner_type,
                        AccountBracketBasketAllocation.is_custom == False
                    )
                )
                
                # Get standard allocations from pf_bracket_basket_allocation
                standard_allocations = await self._get_standard_allocations(bracket_id)
                
                # Insert new allocations
                for alloc in standard_allocations:
                    new_allocation = AccountBracketBasketAllocation(
                        owner_id=owner_id,
                        owner_type=owner_type,
                        bracket_id=bracket_id,
                        basket_id=alloc["basket_id"],
                        allocation_pct=alloc["allocation_pct"],
                        is_custom=False
                    )
                    self.db.add(new_allocation)
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating allocations for {owner_type} account {owner_id}: {e}")
            await self.db.rollback()
            raise

    async def _get_account_allocations(
        self,
        owner_id: str,
        owner_type: str,
        bracket_id: int
    ) -> Optional[List[Dict]]:
        """Get basket allocations for an account, either custom or standard."""
        try:
            # First check if account has custom allocations
            custom_query = select(AccountBracketBasketAllocation).where(
                AccountBracketBasketAllocation.owner_id == owner_id,
                AccountBracketBasketAllocation.owner_type == owner_type,
                AccountBracketBasketAllocation.bracket_id == bracket_id,
                AccountBracketBasketAllocation.is_custom == True
            )
            custom_result = await self.db.execute(custom_query)
            custom_allocations = custom_result.scalars().all()
            
            # If custom allocations exist, use only those and don't mix with standard ones
            if custom_allocations:
                logger.info(f"Found custom allocations for {owner_type} account {owner_id}, using only those")
                allocations = custom_allocations
            else:
                # Check for any allocations (should be only standard ones if any)
                query = select(AccountBracketBasketAllocation).where(
                    AccountBracketBasketAllocation.owner_id == owner_id,
                    AccountBracketBasketAllocation.owner_type == owner_type,
                    AccountBracketBasketAllocation.bracket_id == bracket_id
                )
                result = await self.db.execute(query)
                allocations = result.scalars().all()
                
                if not allocations:
                    # No allocations found at all, insert standard ones
                    logger.info(f"No allocations found for {owner_type} account {owner_id}, adding standard allocations")
                    await self._update_account_allocations(owner_id, owner_type, bracket_id, False)
                    result = await self.db.execute(query)
                    allocations = result.scalars().all()

            # Get basket names
            basket_names = {}
            for alloc in allocations:
                basket_query = select(Basket.basket_name).where(Basket.basket_id == alloc.basket_id)
                basket_result = await self.db.execute(basket_query)
                basket_name = basket_result.scalar_one_or_none()
                if basket_name:
                    basket_names[alloc.basket_id] = basket_name

            return [{
                "basket_id": alloc.basket_id,
                "basket_name": basket_names.get(alloc.basket_id, "Unknown"),
                "allocation_pct": alloc.allocation_pct,
                "is_custom": alloc.is_custom
            } for alloc in allocations]

        except Exception as e:
            logger.error(f"Error getting allocations for {owner_type} account {owner_id}: {e}")
            return None

    async def _calculate_total_holdings(
        self,
        account_id: str,
        account_type: str,
        cash_value: float
    ) -> float:
        """Calculate total holdings based on cash value and actual portfolio holdings,
        applying exceptions from the plus91_reco_exceptions.xlsx file.
        
        Args:
            account_id (str): Account ID
            account_type (str): Account type (single/joint)
            cash_value (float): Cash value of the account
            
        Returns:
            float: Total holdings value
        """
        try:
            # Get the latest snapshot date for this account
            latest_date_query = select(func.max(AccountActualPortfolio.snapshot_date)).where(
                AccountActualPortfolio.owner_id == account_id,
                AccountActualPortfolio.owner_type == account_type
            )
            latest_date_result = await self.db.execute(latest_date_query)
            latest_date = latest_date_result.scalar_one_or_none()
            if account_id == 'ACC_000352':
                print("LATEST DATE: ",  latest_date)

            if not latest_date:
                logger.warning(f"No actual portfolio found for {account_type} account {account_id}")
                return cash_value  # Return only cash value if no portfolio found
            
            # Get actual portfolio holdings for latest date
            portfolio_query = select(AccountActualPortfolio).where(
                AccountActualPortfolio.owner_id == account_id,
                AccountActualPortfolio.owner_type == account_type,
                AccountActualPortfolio.snapshot_date == latest_date
            )
            portfolio_result = await self.db.execute(portfolio_query)
            portfolio_holdings = portfolio_result.scalars().all()
            
            if not portfolio_holdings:
                logger.warning(f"No holdings found for {account_type} account {account_id}")
                return cash_value
            
            # Get broker code for this account
            broker_code = await self._get_broker_code_for_account(account_id)
            
            # Convert portfolio holdings to a DataFrame for easier processing
            holdings_df = pd.DataFrame([
                {
                    'trading_symbol': h.trading_symbol,
                    'quantity': h.quantity,
                    'market_value': h.market_value
                } for h in portfolio_holdings
            ])
            
            # Apply exceptions from the Excel file
            filtered_holdings_df = self._apply_exceptions(holdings_df, broker_code)
            
            # Sum up market value of filtered holdings
            holdings_value = filtered_holdings_df['market_value'].sum() if not filtered_holdings_df.empty else 0
            
            # Total holdings = cash + filtered holdings value
            total_holdings = cash_value + holdings_value
            print("CASH VALUE: ", cash_value)
            print("TOTAL HOLDINGS: ", total_holdings)
            logger.info(
                f"Calculated total holdings for {account_type} account {account_id}: "
                f"Cash: {cash_value}, Holdings: {holdings_value}, Total: {total_holdings}"
            )
            
            return total_holdings
            
        except Exception as e:
            logger.error(f"Error calculating total holdings for {account_type} account {account_id}: {e}")
            return cash_value  # Return just cash value in case of error
            
    def _apply_exceptions(self, holdings_df: pd.DataFrame, broker_code: Optional[str]) -> pd.DataFrame:
        """Apply exceptions from the Excel file to filter holdings.
        
        Args:
            holdings_df (pd.DataFrame): DataFrame with holdings
            broker_code (Optional[str]): Broker code for the account
            
        Returns:
            pd.DataFrame: Filtered holdings
        """
        if holdings_df.empty:
            return holdings_df
            
        if self.exceptions_df.empty:
            # If no exceptions are defined, keep all holdings
            return holdings_df
        
        # Make a copy to avoid modifying the original
        result_df = holdings_df.copy()
        
        # Check if this appears to be a misuse of the exceptions mechanism
        # by looking if more than 90% of the holdings are in the exceptions list
        if not broker_code:
            return result_df
            
        holdings_symbols = set(result_df['trading_symbol'].unique())
        exception_symbols = set(
            self.exceptions_df[self.exceptions_df['broker_code'] == broker_code]['trading_symbol'].unique()
        )
        
        # Calculate the percentage of holdings that have exceptions
        overlap_count = len(holdings_symbols.intersection(exception_symbols))
        
        if len(holdings_symbols) > 0 and (overlap_count / len(holdings_symbols)) > 0.9:
            # If more than 90% of holdings have exceptions, this is likely an error in the exceptions data
            # Log a warning and return the original holdings without filtering
            logger.warning(
                f"More than 90% of holdings for broker {broker_code} have exceptions. "
                f"This may indicate a problem with the exceptions data. No filtering applied."
            )
            return result_df
        
        # List to keep track of indices to drop
        indices_to_drop = []
        
        # Process each holding
        for idx, holding in result_df.iterrows():
            trading_symbol = holding['trading_symbol']
            
            # Filter exceptions that match this trading symbol
            exceptions = self.exceptions_df[self.exceptions_df['trading_symbol'] == trading_symbol]
            
            if exceptions.empty:
                continue
                
            # Further filter by broker_code if provided
            if broker_code:
                broker_exceptions = exceptions[exceptions['broker_code'] == broker_code]
                if not broker_exceptions.empty:
                    exceptions = broker_exceptions
            
            # If we have exceptions for this symbol, check quantities
            for _, exception in exceptions.iterrows():
                exception_quantity = exception['quantity']
                
                if exception_quantity >= holding['quantity']:
                    # If exception quantity is greater than or equal to holding quantity,
                    # this entire holding should be excluded
                    indices_to_drop.append(idx)
                    break
                else:
                    # Reduce the quantity and market value proportionally
                    new_quantity = holding['quantity'] - exception_quantity
                    ratio = new_quantity / holding['quantity']
                    new_market_value = holding['market_value'] * ratio
                    
                    # Update the holding
                    result_df.at[idx, 'quantity'] = new_quantity
                    result_df.at[idx, 'market_value'] = new_market_value
        
        # Drop the indices marked for exclusion
        result_df = result_df.drop(indices_to_drop)
        
        return result_df

    async def process_account_ideal_portfolio(
        self,
        account_id: str,
        account_type: str,
        total_holdings: float,
        snapshot_date: Optional[date] = None,
        update_brackets: bool = False
    ) -> None:
        """Process and update ideal portfolio for a single account.
        
        Args:
            account_id (str): Account ID
            account_type (str): Account type (single/joint)
            total_holdings (float): Total holdings value
            snapshot_date (Optional[date]): Date to process for, defaults to today
            update_brackets (bool): If True, update bracket_id based on total_holdings,
                                    if False, use the existing bracket_id (default: False)
        """
        if not snapshot_date:
            snapshot_date = datetime.now().date()

        try:
            # Get account details including existing bracket_id
            if account_type == "single":
                account_query = select(SingleAccount).where(
                    SingleAccount.single_account_id == account_id
                )
                result = await self.db.execute(account_query)
                account = result.scalar_one_or_none()
                if not account:
                    logger.warning(f"Single account {account_id} not found")
                    return
                cash_value = account.cash_value or 0
                existing_bracket_id = account.bracket_id
            else:
                account_query = select(JointAccount).where(
                    JointAccount.joint_account_id == account_id
                )
                result = await self.db.execute(account_query)
                account = result.scalar_one_or_none()
                if not account:
                    logger.warning(f"Joint account {account_id} not found")
                    return
                cash_value = account.cash_value or 0
                existing_bracket_id = account.bracket_id
            
            # Calculate actual total holdings based on cash value and filtered holdings
            total_holdings = await self._calculate_total_holdings(account_id, account_type, cash_value)
            logger.info(f"Using calculated total holdings of {total_holdings} for {account_type} account {account_id}")

            # Determine which bracket_id to use
            if update_brackets:
                # Get appropriate bracket based on total holdings
                bracket = await self._get_bracket_for_amount(total_holdings)
                if not bracket:
                    return
                bracket_id = bracket["bracket_id"]
                # Update bracket_id in account table
                await self._update_account_bracket(account_id, account_type, bracket_id)
                logger.info(f"Updated bracket_id to {bracket_id} for {account_type} account {account_id}")
            else:
                # Use the existing bracket_id without updating
                if existing_bracket_id is None:
                    logger.warning(f"No existing bracket_id found for {account_type} account {account_id}")
                    # Fallback to determining bracket based on total holdings
                    bracket = await self._get_bracket_for_amount(total_holdings)
                    if not bracket:
                        return
                    bracket_id = bracket["bracket_id"]
                    logger.info(f"Using fallback bracket_id {bracket_id} for {account_type} account {account_id}")
                else:
                    bracket_id = existing_bracket_id
                    logger.info(f"Using existing bracket_id {bracket_id} for {account_type} account {account_id}")

            # Get basket allocations for account (either custom or standard)
            basket_allocations = await self._get_account_allocations(account_id, account_type, bracket_id)

            if not basket_allocations:
                return

            # Calculate total allocation percentage and check if over 100%
            total_allocation_pct = sum(basket["allocation_pct"] for basket in basket_allocations)
            
            # If total allocation exceeds 100%, adjust the leveraged baskets
            if total_allocation_pct > 100:
                logger.info(f"Total allocation for {account_id} is {total_allocation_pct}%, adjusting leveraged baskets")
                
                # Identify leveraged baskets
                leveraged_baskets = [basket for basket in basket_allocations if "(Leveraged)" in basket["basket_name"]]
                non_leveraged_baskets = [basket for basket in basket_allocations if "(Leveraged)" not in basket["basket_name"]]
                
                # Calculate the excess allocation that needs to be removed
                excess_allocation = total_allocation_pct - 100
                
                if leveraged_baskets:
                    # Get total allocation % of leveraged baskets
                    total_leveraged_pct = sum(basket["allocation_pct"] for basket in leveraged_baskets)
                    
                    # Adjust each leveraged basket proportionally
                    for basket in leveraged_baskets:
                        # Calculate reduction proportionally to its size relative to other leveraged baskets
                        reduction = excess_allocation * (basket["allocation_pct"] / total_leveraged_pct)
                        basket["allocation_pct"] -= reduction
                        logger.info(f"Reduced allocation for '{basket['basket_name']}' by {reduction:.2f}% to {basket['allocation_pct']:.2f}%")
                    
                    # Verify the total is now 100%
                    new_total = sum(basket["allocation_pct"] for basket in basket_allocations)
                    logger.info(f"Adjusted total allocation for {account_id} from {total_allocation_pct:.2f}% to {new_total:.2f}%")
                else:
                    logger.warning(f"Total allocation exceeds 100%, but no leveraged baskets found for {account_id}")

            # Get last snapshot date and check if we should update 
            last_snapshot = await self._get_last_snapshot_date(account_id, account_type)
            if last_snapshot and last_snapshot.month != snapshot_date.month:
                # Don't overwrite previous month's portfolio
                logger.info(f"Not overwriting previous month's portfolio for {account_id} from {last_snapshot}")
                return

            # Delete existing portfolio entries for current month
            await self._delete_current_month_portfolio(account_id, account_type, snapshot_date)
            
            # Create a set to track processed stock-basket combinations to avoid duplicates
            # Key format: f"{trading_symbol}:{basket_name}"
            processed_entries = set()

            # Process each basket allocation separately
            for basket_alloc in basket_allocations:
                # Calculate the actual investment amount for this basket
                basket_amount = total_holdings * (basket_alloc["allocation_pct"] / 100)
                
                stocks = await self._get_basket_stocks(basket_alloc["basket_id"])
                
                if not stocks:
                    continue

                basket_name = basket_alloc["basket_name"]
                
                # Process stocks within each basket
                for stock in stocks:
                    trading_symbol = stock["trading_symbol"]
                    
                    # Check if this stock-basket combination has already been processed
                    entry_key = f"{trading_symbol}:{basket_name}"
                    if entry_key in processed_entries:
                        logger.info(f"Skipping duplicate entry for {account_id}: {trading_symbol} in {basket_name}")
                        continue
                    
                    # Add to the set of processed entries
                    processed_entries.add(entry_key)
                    
                    weight = stock["weight"]
                    stock_investment = weight * basket_amount
                    
                    portfolio_entry = AccountIdealPortfolio(
                        owner_id=account_id,
                        owner_type=account_type,
                        snapshot_date=snapshot_date,
                        basket=basket_name,
                        trading_symbol=trading_symbol,
                        allocation_pct=weight * basket_alloc["allocation_pct"], 
                        investment_amount=stock_investment
                    )
                    self.db.add(portfolio_entry)

            await self.db.commit()
            logger.info(
                f"Updated ideal portfolio for {account_type} account {account_id} "
                f"on {snapshot_date} with total holdings {total_holdings}"
            )

        except Exception as e:
            logger.error(
                f"Error processing ideal portfolio for {account_type} account {account_id}: {e}"
            )
            await self.db.rollback()
            raise

    async def process_accounts_ideal_portfolios(
        self,
        accounts: List[Dict],
        snapshot_date: Optional[date] = None,
        update_brackets: bool = False
    ) -> None:
        """Process ideal portfolios for multiple accounts.

        Args:
            accounts (List[Dict]): List of account details with holdings
            snapshot_date (Optional[date]): Date to process for, defaults to today
            update_brackets (bool): If True, update brackets based on total holdings,
                                    if False, use existing bracket_id (default: False)
        """
        for account in accounts:
            # if account.get("account_id") == "ACC_000352":
                account_id = account.get("account_id")
                account_type = account.get("account_type", "single")
                
                # Don't require total_holdings since it will be recalculated
                if not account_id:
                    logger.warning(f"Missing account_id in account data: {account}")
                    continue

                await self.process_account_ideal_portfolio(
                    account_id,
                    account_type, 
                    account.get("total_holdings", 0),  # This is just a placeholder and will be recalculated
                    snapshot_date,
                    update_brackets
                )

    async def _has_custom_allocations(
        self,
        owner_id: str,
        owner_type: str
    ) -> bool:
        """Check if an account has custom basket allocations.
        
        Args:
            owner_id (str): Account ID
            owner_type (str): Account type (single/joint)
            
        Returns:
            bool: True if account has custom allocations, False otherwise
        """
        try:
            query = select(AccountBracketBasketAllocation).where(
                AccountBracketBasketAllocation.owner_id == owner_id,
                AccountBracketBasketAllocation.owner_type == owner_type,
                AccountBracketBasketAllocation.is_custom == True
            )
            result = await self.db.execute(query)
            custom_allocations = result.scalars().all()
            
            return len(custom_allocations) > 0
            
        except Exception as e:
            logger.error(f"Error checking custom allocations for {owner_type} account {owner_id}: {e}")
            return False

    async def _get_broker_code_for_account(self, account_id: str) -> Optional[str]:
        """Get broker code for an account.
        
        Args:
            account_id (str): Account ID
            
        Returns:
            Optional[str]: Broker code if found, None otherwise
        """
        # Check if we already have this in cache
        if account_id in self.client_broker_cache:
            return self.client_broker_cache[account_id]
            
        try:
            # Query for the broker code from client_details
            query = select(Client.broker_code).where(Client.account_id == account_id)
            result = await self.db.execute(query)
            broker_code = result.scalar_one_or_none()
            
            if broker_code:
                # Cache the result for future use
                self.client_broker_cache[account_id] = broker_code
                return broker_code
            else:
                logger.warning(f"No broker code found for account {account_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting broker code for account {account_id}: {e}")
            return None

async def update_all_account_allocations(db: AsyncSession) -> None:
    """Update all non-custom account allocations with the latest standard allocations."""
    try:
        logger.info("Starting update of account allocations from standard portfolio")
        
        # Get all single accounts that are not part of joint accounts
        single_accounts_result = await db.execute(
            select(SingleAccount)
            .outerjoin(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
            .where(JointAccountMapping.joint_account_mapping_id.is_(None))
        )
        standalone_single_accounts = single_accounts_result.scalars().all()
        
        # Get all joint accounts
        joint_query = select(JointAccount)
        joint_result = await db.execute(joint_query)
        joint_accounts = joint_result.scalars().all()
        
        # Create processor instance for helper methods
        processor = IdealPfProcessor(db)
        
        # Process single accounts
        for account in standalone_single_accounts:

            account_id = account.single_account_id
            cash_value = account.cash_value or 0
            
            # Calculate total holdings using the new method
            total_holdings = await processor._calculate_total_holdings(account_id, "single", cash_value)
            
            # Determine bracket based on holdings
            bracket = await processor._get_bracket_for_amount(total_holdings)
            if not bracket:
                logger.warning(f"No bracket found for single account {account_id} with holdings {total_holdings}")
                continue
                
            # Update bracket_id in account table
            await processor._update_account_bracket(account_id, "single", bracket["bracket_id"])
            
            # Update standard allocations for this account
            await processor._update_account_allocations(account_id, "single", bracket["bracket_id"], False)
            
        # Process joint accounts
        for account in joint_accounts:
            account_id = account.joint_account_id
            cash_value = account.cash_value or 0
            
            # Calculate total holdings using the new method
            total_holdings = await processor._calculate_total_holdings(account_id, "joint", cash_value)
            
            # Determine bracket based on holdings
            bracket = await processor._get_bracket_for_amount(total_holdings)
            if not bracket:
                logger.warning(f"No bracket found for joint account {account_id} with holdings {total_holdings}")
                continue
                
            # Update bracket_id in account table
            await processor._update_account_bracket(account_id, "joint", bracket["bracket_id"])
            
            # Update standard allocations for this account
            await processor._update_account_allocations(account_id, "joint", bracket["bracket_id"], False)
            
        logger.info("Completed updating account allocations from standard portfolio")
        
    except Exception as e:
        logger.error(f"Error updating account allocations: {e}")
        await db.rollback()
        raise

async def main(update_brackets: bool = False):
    """Main function to process ideal portfolios for all accounts.
    
    Args:
        update_brackets (bool): If True, update brackets based on total holdings,
                               if False, use existing bracket_id (default: False)
    """
    try:
        async with AsyncSessionLocal() as db:
            # First update all account allocations from master template
            if update_brackets:
                # Only update allocations if we're updating brackets
                await update_all_account_allocations(db)
            
            processor = IdealPfProcessor(db)
            
            # Get all accounts with custom allocations to exclude them from processing
            custom_query = select(
                distinct(AccountBracketBasketAllocation.owner_id)
            ).where(
                AccountBracketBasketAllocation.is_custom == True
            )
            result = await db.execute(custom_query)
            custom_allocation_accounts = {row[0] for row in result.all()}
            logger.info(f"Found {len(custom_allocation_accounts)} accounts with custom allocations that will be skipped")
            
            # Get all single accounts that are not part of joint accounts
            single_accounts_result = await db.execute(
                select(SingleAccount)
                .outerjoin(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
                .where(JointAccountMapping.joint_account_mapping_id.is_(None))
            )
            standalone_single_accounts = single_accounts_result.scalars().all()
            
            # Format single accounts for processing
            single_accounts_to_process = []
            for acc in standalone_single_accounts:
                account_id = acc.single_account_id
                
                # Skip accounts with custom allocations
                if account_id in custom_allocation_accounts:
                    logger.info(f"Skipping single account {account_id} with custom allocations")
                    continue
                    
                cash_value = acc.cash_value or 0
                
                # Using placeholder total_holdings (will be recalculated inside process_account_ideal_portfolio)
                single_accounts_to_process.append({
                    "account_id": account_id,
                    "account_type": "single",
                    "total_holdings": 0  # This will be recalculated using our new method
                })
            
            # Get all joint accounts
            joint_query = select(JointAccount)
            joint_result = await db.execute(joint_query)
            joint_accounts = joint_result.scalars().all()
            
            # Format joint accounts for processing
            joint_accounts_to_process = []
            for acc in joint_accounts:
                account_id = acc.joint_account_id
                
                # Skip accounts with custom allocations
                if account_id in custom_allocation_accounts:
                    logger.info(f"Skipping joint account {account_id} with custom allocations")
                    continue
                
                # Using placeholder total_holdings (will be recalculated inside process_account_ideal_portfolio)
                joint_accounts_to_process.append({
                    "account_id": account_id,
                    "account_type": "joint",
                    "total_holdings": 0  # This will be recalculated using our new method
                })
            
            # Process both types of accounts
            all_accounts = single_accounts_to_process + joint_accounts_to_process
            
            await processor.process_accounts_ideal_portfolios(all_accounts, update_brackets=update_brackets)
            logger.info(f"Completed processing ideal portfolios (update_brackets={update_brackets})")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    # Check if update_brackets parameter is provided in command-line arguments
    update_brackets = False
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['true', 't', 'yes', 'y', '1']:
        update_brackets = True
    
    asyncio.run(main(update_brackets))
