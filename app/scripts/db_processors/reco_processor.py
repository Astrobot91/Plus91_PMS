import asyncio
import pandas as pd
import numpy as np
import os
import json
import time
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Tuple, Optional, Any

from app.database import AsyncSessionLocal
from app.logger import logger
from app.models.stock_ltps import StockLTP
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.account_ideal_portfolio import AccountIdealPortfolio
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.models.clients.client_details import Client
from app.models.clients.broker_details import Broker


class RecoProcessor:
    def __init__(self):
        """Initialize the RecoProcessor."""
        logger.info("Initializing RecoProcessor")
        # Load exceptions
        self.exceptions_df = self._load_exceptions()

    def _load_exceptions(self) -> pd.DataFrame:
        """
        Load reco exceptions from the Excel file.
        
        Returns:
            pd.DataFrame: DataFrame with exceptions or empty DataFrame if file doesn't exist
        """
        try:
            exceptions_path = "data/cashflow_data/plus91_reco_exceptions.xlsx"
            if os.path.exists(exceptions_path):
                df = pd.read_excel(exceptions_path)
                if 'account_id' in df.columns and 'trading_symbol' in df.columns:
                    logger.info(f"Loaded {len(df)} reco exceptions from {exceptions_path}")
                    # Ensure quantity column exists, default to 0 if not
                    if 'quantity' not in df.columns:
                        df['quantity'] = 0
                    # Standardize column names to lowercase
                    df.columns = [col.lower() for col in df.columns]
                    return df
                else:
                    logger.warning(f"Exceptions file {exceptions_path} has invalid format, missing required columns")
            else:
                logger.info(f"Exceptions file {exceptions_path} not found")
            return pd.DataFrame(columns=['account_id', 'trading_symbol', 'quantity'])
        except Exception as e:
            logger.error(f"Error loading exceptions: {str(e)}")
            return pd.DataFrame(columns=['account_id', 'trading_symbol', 'quantity'])

    def _get_account_exceptions(self, account_id: str) -> pd.DataFrame:
        """
        Get exceptions for a specific account from the loaded exceptions.
        
        Args:
            account_id (str): The account ID to filter exceptions for
            
        Returns:
            pd.DataFrame: DataFrame with exceptions for the account
        """
        if self.exceptions_df.empty:
            return pd.DataFrame(columns=['account_id', 'trading_symbol', 'quantity'])
            
        # Filter exceptions by account_id
        account_exceptions = self.exceptions_df[self.exceptions_df['account_id'] == account_id]
        if not account_exceptions.empty:
            logger.info(f"Found {len(account_exceptions)} exceptions for account {account_id}")
        return account_exceptions
        
    def _filter_actual_portfolio(self, account_id: str, actual_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter actual portfolio based on exceptions for the account.
        
        Args:
            account_id (str): The account ID
            actual_df (pd.DataFrame): The actual portfolio DataFrame
            
        Returns:
            pd.DataFrame: Filtered actual portfolio DataFrame
        """
        if actual_df.empty:
            return actual_df
            
        # Get exceptions for this account
        exceptions = self._get_account_exceptions(account_id)
        if exceptions.empty:
            return actual_df
            
        # Create a copy to avoid modifying the original DataFrame
        filtered_df = actual_df.copy()
        
        # Apply exceptions
        for _, exception in exceptions.iterrows():
            symbol = exception['trading_symbol']
            exclude_qty = exception['quantity']
            
            # Find the symbol in the actual portfolio
            symbol_rows = filtered_df['trading_symbol'] == symbol
            if not any(symbol_rows):
                continue
                
            # Get the current quantity
            current_qty = filtered_df.loc[symbol_rows, 'quantity'].values[0]
            
            if current_qty <= exclude_qty:
                # Remove the entire row if quantity is less than or equal to exclude_qty
                filtered_df = filtered_df[~symbol_rows]
                logger.info(f"Removed {symbol} from portfolio for account {account_id} (excluded qty: {exclude_qty}, current qty: {current_qty})")
            else:
                # Reduce the quantity and market value proportionally
                new_qty = current_qty - exclude_qty
                ratio = new_qty / current_qty
                
                # Update quantity and market value
                filtered_df.loc[symbol_rows, 'quantity'] = new_qty
                filtered_df.loc[symbol_rows, 'market_value'] *= ratio
                
                logger.info(f"Adjusted quantity for {symbol} in account {account_id} from {current_qty} to {new_qty} (excluded: {exclude_qty})")
        
        return filtered_df

    async def get_ltps(self, db: AsyncSession) -> Dict[str, float]:
        """
        Retrieve last traded prices for all trading symbols from the stock_ltps table.
        
        Args:
            db (AsyncSession): The asynchronous database session

        Returns:
            Dict[str, float]: Dictionary mapping trading symbols to their LTPs
        """
        logger.info("Retrieving latest LTPs from stock_ltps table")
        try:
            query = select(StockLTP)
            result = await db.execute(query)
            ltps = result.scalars().all()
            
            ltp_dict = {ltp.trading_symbol: ltp.ltp for ltp in ltps}
            logger.info(f"Retrieved LTPs for {len(ltp_dict)} trading symbols")
            return ltp_dict
        except Exception as e:
            logger.error(f"Error retrieving LTPs: {str(e)}")
            raise

    async def get_latest_snapshot_date(self, db: AsyncSession, table_class, owner_id: str, owner_type: str) -> Optional[str]:
        """
        Get the latest snapshot date for a specific owner from a specific table.
        
        Args:
            db (AsyncSession): The asynchronous database session
            table_class: The SQLAlchemy model class (AccountActualPortfolio or AccountIdealPortfolio)
            owner_id (str): ID of the account owner
            owner_type (str): Type of the account owner ('single' or 'joint')
            
        Returns:
            Optional[str]: The latest snapshot date or None if no data exists
        """
        try:
            query = (
                select(func.max(table_class.snapshot_date))
                .where(
                    table_class.owner_id == owner_id,
                    table_class.owner_type == owner_type
                )
            )
            result = await db.execute(query)
            latest_date = result.scalar_one_or_none()
            return latest_date
        except Exception as e:
            logger.error(f"Error getting latest snapshot date for {owner_id}: {str(e)}")
            raise

    async def get_actual_portfolio(self, db: AsyncSession, owner_id: str, owner_type: str) -> pd.DataFrame:
        """
        Retrieve the latest actual portfolio for a specific owner.
        
        Args:
            db (AsyncSession): The asynchronous database session
            owner_id (str): ID of the account owner
            owner_type (str): Type of the account owner ('single' or 'joint')
            
        Returns:
            pd.DataFrame: DataFrame containing the actual portfolio data
        """
        logger.info(f"Retrieving actual portfolio for {owner_type} account {owner_id}")
        try:
            latest_date = await self.get_latest_snapshot_date(db, AccountActualPortfolio, owner_id, owner_type)
            if not latest_date:
                logger.warning(f"No actual portfolio data found for {owner_type} account {owner_id}")
                return pd.DataFrame()
                
            query = (
                select(AccountActualPortfolio)
                .where(
                    AccountActualPortfolio.owner_id == owner_id,
                    AccountActualPortfolio.owner_type == owner_type,
                    AccountActualPortfolio.snapshot_date == latest_date
                )
            )
            result = await db.execute(query)
            portfolios = result.scalars().all()
            
            if not portfolios:
                logger.warning(f"No actual portfolio data found for {owner_type} account {owner_id} on {latest_date}")
                return pd.DataFrame()
                
            data = [{
                'trading_symbol': portfolio.trading_symbol,
                'quantity': portfolio.quantity,
                'market_value': portfolio.market_value
            } for portfolio in portfolios]
            
            df = pd.DataFrame(data)
            df['quantity'] = np.floor(df['quantity']).astype(int)
            logger.info(f"Retrieved {len(df)} actual portfolio entries for {owner_type} account {owner_id}")

            # Load symbol renamer JSON
            try:
                with open("data/symbol_renamer.json", "r") as f:
                    symbol_renamer = json.load(f)
            except Exception as e:
                logger.error(f"Error loading symbol renamer JSON: {str(e)}")
                symbol_renamer = {}

            # Rename trading symbols based on the JSON
            if not df.empty:
                df['trading_symbol'] = df['trading_symbol'].replace(symbol_renamer)

                # Aggregate by trading_symbol
                df = df.groupby('trading_symbol').agg({
                    'quantity': 'sum',
                    'market_value': 'sum'
                }).reset_index()
                
                # Filter out rows with market_value = 0
                df = df[df['market_value'] > 0]
                logger.info(f"After filtering zero market values: {len(df)} portfolio entries")

            return self._filter_actual_portfolio(owner_id, df)
        except Exception as e:
            logger.error(f"Error retrieving actual portfolio for {owner_id}: {str(e)}")
            raise

    async def get_ideal_portfolio(self, db: AsyncSession, owner_id: str, owner_type: str) -> pd.DataFrame:
        """
        Retrieve the latest ideal portfolio for a specific owner, aggregated by trading symbol.
        
        Args:
            db (AsyncSession): The asynchronous database session
            owner_id (str): ID of the account owner
            owner_type (str): Type of the account owner ('single' or 'joint')
            
        Returns:
            pd.DataFrame: DataFrame containing the ideal portfolio data aggregated by trading symbol
        """
        logger.info(f"Retrieving ideal portfolio for {owner_type} account {owner_id}")
        try:
            latest_date = await self.get_latest_snapshot_date(db, AccountIdealPortfolio, owner_id, owner_type)
            if not latest_date:
                logger.warning(f"No ideal portfolio data found for {owner_type} account {owner_id}")
                return pd.DataFrame()
                
            query = (
                select(AccountIdealPortfolio)
                .where(
                    AccountIdealPortfolio.owner_id == owner_id,
                    AccountIdealPortfolio.owner_type == owner_type,
                    AccountIdealPortfolio.snapshot_date == latest_date
                )
            )
            result = await db.execute(query)
            portfolios = result.scalars().all()
            
            if not portfolios:
                logger.warning(f"No ideal portfolio data found for {owner_type} account {owner_id} on {latest_date}")
                return pd.DataFrame()
                
            data = [{
                'trading_symbol': portfolio.trading_symbol,
                'basket': portfolio.basket,
                'allocation_pct': portfolio.allocation_pct,
                'investment_amount': portfolio.investment_amount
            } for portfolio in portfolios]
            
            df = pd.DataFrame(data)
            
            # Filter out rows with investment_amount = 0
            if not df.empty:
                df = df[df['investment_amount'] > 0]
                logger.info(f"Filtered ideal portfolio to {len(df)} entries with non-zero investment amount")
            
            # Aggregate by trading_symbol (sum investment_amount)
            aggregated_df = df.groupby('trading_symbol').agg({
                'investment_amount': 'sum',
                'basket': lambda x: ', '.join(set(x))  # Keep track of which baskets this symbol appears in
            }).reset_index()
            
            logger.info(f"Retrieved and aggregated {len(aggregated_df)} ideal portfolio entries for {owner_type} account {owner_id}")
            return aggregated_df
        except Exception as e:
            logger.error(f"Error retrieving ideal portfolio for {owner_id}: {str(e)}")
            raise

    async def get_client_details(self, db: AsyncSession, account_id: str, account_type: str) -> Optional[Dict]:
        """
        Get client details for an account.
        
        Args:
            db (AsyncSession): The asynchronous database session
            account_id (str): ID of the account
            account_type (str): Type of the account ('single' or 'joint')
            
        Returns:
            Optional[Dict]: Dictionary with client details or None if not found
        """
        logger.info(f"Retrieving client details for {account_type} account {account_id}")
        try:
            if account_type == 'single':
                # Fetch client_id, broker_code, and broker_name properly by joining with Broker table
                query = (
                    select(Client.client_id, Client.broker_code, Broker.broker_name)
                    .join(Broker, Client.broker_id == Broker.broker_id, isouter=True)
                    .where(Client.account_id == account_id)
                )
                result = await db.execute(query)
                row = result.first()
                
                if not row:
                    logger.warning(f"No client details found for single account {account_id}")
                    return None
                
                return {
                    'client_id': row[0],
                    'broker_code': row[1] or "Unknown",
                    'broker_name': row[2] or "Unknown"  # Use actual broker_name
                }
            else:  # joint
                # For joint accounts, we'll fetch details of any single account in the joint account
                query = (
                    select(Client.client_id, Client.broker_code, Broker.broker_name)
                    .join(Broker, Client.broker_id == Broker.broker_id, isouter=True)
                    .join(SingleAccount, Client.account_id == SingleAccount.single_account_id)
                    .join(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
                    .where(JointAccountMapping.joint_account_id == account_id)
                    .limit(1)  # Get any single account in the joint account
                )
                
                result = await db.execute(query)
                row = result.first()
                
                if not row:
                    logger.warning(f"No client details found for joint account {account_id}")
                    return None
                
                return {
                    'client_id': row[0],
                    'broker_code': row[1] or "Unknown",
                    'broker_name': row[2] or "Unknown"  # Use actual broker_name
                }
        except Exception as e:
            logger.error(f"Error retrieving client details for {account_id}: {str(e)}")
            raise

    async def get_single_accounts_in_joint(self, db: AsyncSession, joint_account_id: str) -> List[Dict]:
        """
        Get all single accounts in a joint account, ordered by total_holdings descending.
        
        Args:
            db (AsyncSession): The asynchronous database session
            joint_account_id (str): ID of the joint account
            
        Returns:
            List[Dict
        """
        logger.info(f"Retrieving single accounts in joint account {joint_account_id}")
        try:
            query = (
                select(SingleAccount, JointAccountMapping)
                .join(
                    JointAccountMapping, 
                    SingleAccount.single_account_id == JointAccountMapping.account_id
                )
                .where(JointAccountMapping.joint_account_id == joint_account_id)
                .order_by(desc(SingleAccount.total_holdings))
            )
            
            result = await db.execute(query)
            rows = result.all()
            
            if not rows:
                logger.warning(f"No single accounts found in joint account {joint_account_id}")
                return []
            
            accounts = [{
                'single_account_id': row[0].single_account_id,
                'account_name': row[0].account_name,
                'total_holdings': row[0].total_holdings
            } for row in rows]
            
            logger.info(f"Retrieved {len(accounts)} single accounts in joint account {joint_account_id}")
            return accounts
        except Exception as e:
            logger.error(f"Error retrieving single accounts in joint account {joint_account_id}: {str(e)}")
            raise

    async def get_joint_account_broker_codes(self, db: AsyncSession, joint_account_id: str) -> str:
        """
        Get all broker codes for a joint account as a string with format "broker_code_1 - broker_code_2 - ... broker_code_n"
        sorted alphabetically.
        
        Args:
            db (AsyncSession): The asynchronous database session
            joint_account_id (str): ID of the joint account
            
        Returns:
            str: String with all broker codes combined and sorted
        """
        logger.info(f"Retrieving broker codes for joint account {joint_account_id}")
        try:
            query = (
                select(Client.broker_code)
                .join(SingleAccount, Client.account_id == SingleAccount.single_account_id)
                .join(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
                .where(JointAccountMapping.joint_account_id == joint_account_id)
                .distinct()
            )
            
            result = await db.execute(query)
            broker_codes = [row[0] for row in result.all() if row[0]]
            
            # Sort broker codes alphabetically and join with " - "
            if broker_codes:
                broker_codes.sort()
                combined_codes = " - ".join(broker_codes)
                logger.info(f"Combined broker codes for joint account {joint_account_id}: {combined_codes}")
                return combined_codes
            else:
                logger.warning(f"No broker codes found for joint account {joint_account_id}")
                return "Unknown"
        except Exception as e:
            logger.error(f"Error retrieving broker codes for joint account {joint_account_id}: {str(e)}")
            return "Unknown"

    def generate_single_account_reco(
        self, 
        actual_df: pd.DataFrame, 
        ideal_df: pd.DataFrame, 
        ltps: Dict[str, float],
        client_details: Dict
    ) -> pd.DataFrame:
        """
        Generate recommendations for a single account based on actual and ideal portfolios.
        
        Args:
            actual_df (pd.DataFrame): DataFrame with actual portfolio
            ideal_df (pd.DataFrame): DataFrame with ideal portfolio
            ltps (Dict[str, float]): Dictionary with last traded prices
            client_details (Dict): Dictionary with client details
            
        Returns:
            pd.DataFrame: DataFrame with recommendations
        """
        logger.info("Generating recommendations for single account")
        try:
            # 1. Update actual portfolio market values using the latest LTPs
            if not actual_df.empty:
                actual_df['updated_market_value'] = actual_df.apply(
                    lambda row: row['quantity'] * ltps.get(row['trading_symbol'], 0), 
                    axis=1
                )
            else:
                actual_df = pd.DataFrame(columns=['trading_symbol', 'quantity', 'market_value', 'updated_market_value'])
            
            # 2. Get the union of trading symbols from both dataframes
            all_symbols = set(actual_df['trading_symbol'].tolist() if not actual_df.empty else [])
            all_symbols.update(ideal_df['trading_symbol'].tolist() if not ideal_df.empty else [])
            
            # 3. Create the recommendation dataframe
            reco_data = []
            
            for symbol in all_symbols:
                actual_row = actual_df[actual_df['trading_symbol'] == symbol] if not actual_df.empty else pd.DataFrame()
                ideal_row = ideal_df[ideal_df['trading_symbol'] == symbol] if not ideal_df.empty else pd.DataFrame()
                
                actual_value = actual_row['updated_market_value'].sum() if not actual_row.empty else 0
                ideal_value = ideal_row['investment_amount'].sum() if not ideal_row.empty else 0
                
                # Calculate the difference and required quantity adjustment
                value_diff = ideal_value - actual_value
                ltp = ltps.get(symbol, 0)
                quantity_diff = value_diff / ltp if ltp > 0 else 0
                
                # Round down all stock quantities (including liquid funds)
                quantity_diff = np.floor(quantity_diff)
                
                # Determine if this is a total entry or exit
                is_total_entry = not actual_row.empty and ideal_row.empty
                is_total_exit = actual_row.empty and not ideal_row.empty
                
                # Create the recommendation record
                reco_data.append({
                    'broker_code': client_details.get('broker_code', ''),
                    'broker_name': client_details.get('broker_name', ''),
                    'trading_symbol': symbol,
                    'quantity': abs(quantity_diff),
                    'signal': 'BUY' if quantity_diff > 0 else 'SELL',
                    'total_entry_exit': 'Total ENTRY' if is_total_exit else ('Total EXIT' if is_total_entry else '')
                })
            
            reco_df = pd.DataFrame(reco_data)
            logger.info(f"Generated {len(reco_df)} recommendations")
            return reco_df
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            raise

    async def allocate_joint_account_reco(
        self,
        joint_ideal_df: pd.DataFrame,
        single_accounts: List[Dict],
        ltps: Dict[str, float],
        db: AsyncSession
    ) -> Dict[str, pd.DataFrame]:
        """
        Allocate joint account recommendations across member single accounts.
        
        Args:
            joint_ideal_df (pd.DataFrame): DataFrame with joint account ideal portfolio
            single_accounts (List[Dict]): List of single accounts in the joint account
            ltps (Dict[str, float]): Dictionary with last traded prices
            db (AsyncSession): The asynchronous database session
            
        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping single account IDs to their recommendation DataFrames
        """
        logger.info("Allocating joint account recommendations to single accounts")
        try:
            if joint_ideal_df.empty or not single_accounts:
                logger.warning("No joint ideal portfolio or single accounts to allocate")
                return {}
            
            # Sort single accounts by total holdings (should already be sorted but ensuring)
            single_accounts = sorted(single_accounts, key=lambda x: x['total_holdings'], reverse=True)
            
            # Create a dictionary to store recommendations for each single account
            single_account_recos = {}
            
            # Track remaining allocation for each symbol
            remaining_allocation = joint_ideal_df.copy()
            
            # Get actual portfolios for all single accounts
            single_actual_portfolios = {}
            for account in single_accounts:
                actual_df = await self.get_actual_portfolio(db, account['single_account_id'], 'single')
                single_actual_portfolios[account['single_account_id']] = actual_df
                
                if not actual_df.empty:
                    # Update market values using the latest LTPs
                    actual_df['updated_market_value'] = actual_df.apply(
                        lambda row: row['quantity'] * ltps.get(row['trading_symbol'], 0), 
                        axis=1
                    )
            
            # Get client details for all single accounts
            single_client_details = {}
            for account in single_accounts:
                client_details = await self.get_client_details(db, account['single_account_id'], 'single')
                single_client_details[account['single_account_id']] = client_details
            
            # Allocate to each single account in order of total holdings
            for account_idx, account in enumerate(single_accounts):
                account_id = account['single_account_id']
                actual_df = single_actual_portfolios.get(account_id, pd.DataFrame())
                client_details = single_client_details.get(account_id, {})
                
                # For the last account, allocate all remaining
                if account_idx == len(single_accounts) - 1:
                    ideal_allocation = remaining_allocation
                else:
                    # Allocate based on proportion of account holdings
                    allocation_factor = account['total_holdings'] / sum(acc['total_holdings'] for acc in single_accounts)
                    ideal_allocation = remaining_allocation.copy()
                    ideal_allocation['investment_amount'] = ideal_allocation['investment_amount'] * allocation_factor
                    
                    # Update remaining allocation
                    remaining_allocation['investment_amount'] -= ideal_allocation['investment_amount']
                
                # Generate recommendations for this single account
                reco_df = self.generate_single_account_reco(
                    actual_df, ideal_allocation, ltps, client_details
                )
                
                single_account_recos[account_id] = reco_df
            
            return single_account_recos
        except Exception as e:
            logger.error(f"Error allocating joint account recommendations: {str(e)}")
            raise

    async def get_accounts_with_both_portfolios(self, db: AsyncSession) -> Tuple[List[str], List[str]]:
        """
        Get lists of single and joint accounts that have both actual and ideal portfolios.
        Excludes single accounts that are part of joint accounts.
        
        Args:
            db (AsyncSession): The asynchronous database session
            
        Returns:
            Tuple[List[str], List[str]]: Lists of single and joint account IDs
        """
        logger.info("Retrieving accounts with both actual and ideal portfolios")
        try:
            # Get accounts with actual portfolios
            actual_query = (
                select(
                    AccountActualPortfolio.owner_id, 
                    AccountActualPortfolio.owner_type
                )
                .group_by(
                    AccountActualPortfolio.owner_id, 
                    AccountActualPortfolio.owner_type
                )
            )
            actual_result = await db.execute(actual_query)
            actual_accounts = actual_result.all()
            
            # Get accounts with ideal portfolios
            ideal_query = (
                select(
                    AccountIdealPortfolio.owner_id, 
                    AccountIdealPortfolio.owner_type
                )
                .group_by(
                    AccountIdealPortfolio.owner_id, 
                    AccountIdealPortfolio.owner_type
                )
            )
            ideal_result = await db.execute(ideal_query)
            ideal_accounts = ideal_result.all()
            
            # Find accounts with both types of portfolios
            actual_set = set((acc.owner_id, acc.owner_type) for acc in actual_accounts)
            ideal_set = set((acc.owner_id, acc.owner_type) for acc in ideal_accounts)
            both_set = actual_set.intersection(ideal_set)
            
            # Get all single accounts that are part of joint accounts
            joint_members_query = select(JointAccountMapping.account_id)
            joint_members_result = await db.execute(joint_members_query)
            joint_members = {row[0] for row in joint_members_result.all()}
            
            # Separate into single and joint account lists
            # Exclude single accounts that are in the joint_members set
            single_accounts = [acc[0] for acc in both_set if acc[1] == 'single' and acc[0] not in joint_members]
            joint_accounts = [acc[0] for acc in both_set if acc[1] == 'joint']
            
            logger.info(f"Found {len(single_accounts)} standalone single accounts and {len(joint_accounts)} joint accounts with both portfolio types")
            return single_accounts, joint_accounts
        except Exception as e:
            logger.error(f"Error retrieving accounts with both portfolios: {str(e)}")
            raise

    async def process_single_account(
        self, 
        db: AsyncSession, 
        account_id: str, 
        ltps: Dict[str, float]
    ) -> pd.DataFrame:
        """
        Process a single account and generate recommendations.
        
        Args:
            db (AsyncSession): The asynchronous database session
            account_id (str): ID of the single account
            ltps (Dict[str, float]): Dictionary with last traded prices
            
        Returns:
            pd.DataFrame: DataFrame with recommendations
        """
        logger.info(f"Processing single account {account_id}")
        try:
            # Get actual and ideal portfolios
            actual_df = await self.get_actual_portfolio(db, account_id, 'single')
            ideal_df = await self.get_ideal_portfolio(db, account_id, 'single')
            
            if actual_df.empty or ideal_df.empty:
                logger.warning(f"Missing portfolio data for single account {account_id}")
                return pd.DataFrame()
            
            # Get client details
            client_details = await self.get_client_details(db, account_id, 'single')
            if not client_details:
                logger.warning(f"No client details found for single account {account_id}")
                client_details = {}
            
            # Generate recommendations
            reco_df = self.generate_single_account_reco(actual_df, ideal_df, ltps, client_details)
            return reco_df
        except Exception as e:
            logger.error(f"Error processing single account {account_id}: {str(e)}")
            raise

    async def process_joint_account(
        self, 
        db: AsyncSession, 
        joint_account_id: str, 
        ltps: Dict[str, float]
    ) -> pd.DataFrame:
        """
        Process a joint account and generate recommendations for the joint account as a single entity.
        
        Args:
            db (AsyncSession): The asynchronous database session
            joint_account_id (str): ID of the joint account
            ltps (Dict[str, float]): Dictionary with last traded prices
            
        Returns:
            pd.DataFrame: DataFrame with recommendations for the joint account
        """
        logger.info(f"Processing joint account {joint_account_id}")
        try:
            # Get the ideal portfolio for the joint account
            joint_ideal_df = await self.get_ideal_portfolio(db, joint_account_id, 'joint')
            
            if joint_ideal_df.empty:
                logger.warning(f"No ideal portfolio found for joint account {joint_account_id}")
                return pd.DataFrame()
            
            # Get combined actual portfolio for the joint account by aggregating all single account portfolios
            combined_actual_df = await self.get_combined_actual_portfolio_for_joint(db, joint_account_id)
            
            if combined_actual_df.empty:
                logger.warning(f"No combined actual portfolio data found for joint account {joint_account_id}")
                return pd.DataFrame()
            
            # Get the combined broker names and codes for all single accounts in this joint account
            broker_names = await self.get_joint_account_broker_names(db, joint_account_id)
            broker_codes = await self.get_joint_account_broker_codes(db, joint_account_id)
            
            # Create a client details dictionary with the combined broker names and codes
            client_details = {
                'broker_code': broker_codes,  # Use combined broker codes instead of joint account ID
                'broker_name': broker_names
            }
            
            # Generate recommendations treating joint account as a single entity
            reco_df = self.generate_single_account_reco(
                combined_actual_df, joint_ideal_df, ltps, client_details
            )
            
            logger.info(f"Generated recommendations for joint account {joint_account_id} as a single entity")
            return reco_df
        except Exception as e:
            logger.error(f"Error processing joint account {joint_account_id}: {str(e)}")
            raise

    async def process_all_accounts(self) -> Dict[str, pd.DataFrame]:
        """
        Process all accounts and generate recommendations.
        
        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping account IDs to their recommendation DataFrames
        """
        logger.info("Processing all accounts")
        try:
            all_recommendations = {}
            
            async with AsyncSessionLocal() as db:
                # Get LTPs for all trading symbols
                ltps = await self.get_ltps(db)
                
                # Get accounts with both actual and ideal portfolios
                single_accounts, joint_accounts = await self.get_accounts_with_both_portfolios(db)
                
                # Process single accounts
                for account_id in single_accounts:
                    reco_df = await self.process_single_account(db, account_id, ltps)
                    if not reco_df.empty:
                        all_recommendations[account_id] = reco_df
                
                # Process joint accounts as individual entities (not distributing to single accounts)
                for joint_account_id in joint_accounts:
                    joint_reco_df = await self.process_joint_account(db, joint_account_id, ltps)
                    if not joint_reco_df.empty:
                        all_recommendations[joint_account_id] = joint_reco_df
            
            logger.info(f"Generated recommendations for {len(all_recommendations)} accounts")
            return all_recommendations
        except Exception as e:
            logger.error(f"Error processing all accounts: {str(e)}")
            raise

    def save_recommendations_to_csv(self, recommendations: Dict[str, pd.DataFrame], output_dir: str = 'data/recommendations') -> None:
        """
        Save recommendations to CSV files.
        
        Args:
            recommendations (Dict[str, pd.DataFrame]): Dictionary mapping account IDs to their recommendation DataFrames
            output_dir (str): Directory to save CSV files to
        """
        from datetime import datetime
        
        logger.info(f"Saving recommendations to CSV files in {output_dir}")
        try:
            # Create the output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get the current date for the filename
            date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Save each account's recommendations to a separate CSV file
            filtered_recommendations = {}
            for account_id, reco_df in recommendations.items():

                if not reco_df.empty:
                    # Filter out rows where quantity is 0
                    filtered_df = reco_df[reco_df['quantity'] > 0]
                    logger.info(f"Filtered out {len(reco_df) - len(filtered_df)} rows with quantity 0 for account {account_id}")
                    
                    if not filtered_df.empty:
                        filtered_recommendations[account_id] = filtered_df
                        filename = f"{output_dir}/reco_{account_id}.csv"
                        filtered_df.to_csv(filename, index=False)
                        logger.info(f"Saved recommendations for account {account_id} to {filename}")
                    else:
                        logger.warning(f"No valid recommendations for account {account_id} after filtering")
                        pass
            
            # Also save a combined file with all recommendations (filtered)
            if filtered_recommendations:
                combined_df = pd.concat([df.assign(account_id=acc_id) for acc_id, df in filtered_recommendations.items()], ignore_index=True)
                if not combined_df.empty:
                    combined_filename = f"/home/admin/Plus91Backoffice/Plus91_Backend/data/reco_files/reco_all_accounts_{date_str}.csv"
                    combined_df.to_csv(combined_filename, index=False)
                    logger.info(f"Saved combined recommendations to {combined_filename}")
        except Exception as e:
            logger.error(f"Error saving recommendations to CSV: {str(e)}")
            raise

    async def get_joint_account_broker_names(self, db: AsyncSession, joint_account_id: str) -> str:
        """
        Get all broker names for a joint account as a string with format "broker_name_1 - broker_name_2 - ... broker_name_n"
        sorted in alphabetical order.
        
        Args:
            db (AsyncSession): The asynchronous database session
            joint_account_id (str): ID of the joint account
            
        Returns:
            str: String with all broker names combined and sorted
        """
        logger.info(f"Retrieving broker names for joint account {joint_account_id}")
        try:
            query = (
                select(Broker.broker_name)
                .join(Client, Broker.broker_id == Client.broker_id)
                .join(SingleAccount, Client.account_id == SingleAccount.single_account_id)
                .join(JointAccountMapping, SingleAccount.single_account_id == JointAccountMapping.account_id)
                .where(JointAccountMapping.joint_account_id == joint_account_id)
                .distinct()
            )
            
            result = await db.execute(query)
            broker_names = [row[0] for row in result.all() if row[0]]
            
            # Sort broker names alphabetically and join with " - "
            if broker_names:
                broker_names.sort()
                combined_name = " - ".join(broker_names)
                logger.info(f"Combined broker names for joint account {joint_account_id}: {combined_name}")
                return combined_name
            else:
                logger.warning(f"No broker names found for joint account {joint_account_id}")
                return "Unknown"
        except Exception as e:
            logger.error(f"Error retrieving broker names for joint account {joint_account_id}: {str(e)}")
            return "Unknown"

    async def get_combined_actual_portfolio_for_joint(self, db: AsyncSession, joint_account_id: str) -> pd.DataFrame:
        """
        Get a combined actual portfolio for a joint account by combining all its single account portfolios.
        
        Args:
            db (AsyncSession): The asynchronous database session
            joint_account_id (str): ID of the joint account
            
            
        Returns:
            pd.DataFrame: DataFrame containing the combined actual portfolio data
        """
        logger.info(f"Getting combined actual portfolio for joint account {joint_account_id}")
        try:
            # Get all single accounts in the joint account
            single_accounts = await self.get_single_accounts_in_joint(db, joint_account_id)
            if not single_accounts:
                logger.warning(f"No single accounts found in joint account {joint_account_id}")
                return pd.DataFrame()
            
            # Get all actual portfolios for the single accounts
            all_portfolios = []
            for account in single_accounts:
                account_id = account['single_account_id']
                df = await self.get_actual_portfolio(db, account_id, 'single')
                if not df.empty:
                    all_portfolios.append(df)
            
            if not all_portfolios:
                logger.warning(f"No actual portfolios found for any single accounts in joint account {joint_account_id}")
                return pd.DataFrame()
            
            # Combine all the portfolios
            combined_df = pd.concat(all_portfolios, ignore_index=True)
            
            # Aggregate by trading symbol
            if not combined_df.empty:
                aggregated_df = combined_df.groupby('trading_symbol').agg({
                    'quantity': 'sum',
                    'market_value': 'sum'
                }).reset_index()

                logger.info(f"Created combined actual portfolio for joint account {joint_account_id} with {len(aggregated_df)} positions")
                return self._filter_actual_portfolio(joint_account_id, aggregated_df)
            else:
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error getting combined actual portfolio for joint account {joint_account_id}: {str(e)}")
            raise


async def main() -> None:
    """Main function to run the portfolio reconciliation processing."""
    logger.info("Starting portfolio reconciliation processing")
    try:
        processor = RecoProcessor()
        recommendations = await processor.process_all_accounts()
        processor.save_recommendations_to_csv(recommendations)
        logger.info("Portfolio reconciliation processing completed successfully")
    except Exception as e:
        logger.error(f"Portfolio reconciliation processing failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())