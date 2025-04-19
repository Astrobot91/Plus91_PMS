import sys
import logging
import calendar
import pandas as pd
from functools import reduce
from datetime import datetime, timedelta, date
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.accounts.joint_account_service import JointAccountService
from app.models.accounts.account_cashflow_details import AccountCashflow
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.account_time_periods import AccountTimePeriods
from app.models.accounts.account_cashflow_progression import AccountCashflowProgression
from app.scripts.db_processors.cashflow_processor import CashflowProcessor
from app.scripts.db_processors.helper_functions import (
    _generate_historical_month_ends, _get_existing_snapshot_dates
)
from app.logger import logger
from typing import List, Dict, Tuple


class CashflowProgressionProcessor:
    def __init__(self, db: AsyncSession, cashflow_processor: CashflowProcessor):
        self.db = db
        self.cashflow_processor = cashflow_processor

    async def get_month_end_portfolio_df(self, account: dict) -> pd.DataFrame:
        """Generate a DataFrame with month-end portfolio values (portfolio + cash balance) for an account."""
        account_id = account['account_id']
        account_type = account['account_type']
        today = datetime.now().date()

        if account_type == 'single':
            acc_start_date = account['acc_start_date']
            month_ends = _generate_historical_month_ends(acc_start_date, today)
            if not month_ends:
                logger.warning(f"No month-end dates for account {account_id}")
                return pd.DataFrame(columns=['event_date', 'portfolio'])

            portfolio_values, month_ends = await self.get_portfolio_values(account_id, 'single')
            cash_balances = await self.cashflow_processor.get_month_end_cash_balances(account, month_ends)

            data = []
            for month_end in month_ends:
                portfolio_value = portfolio_values.get(month_end, 0)
                cash_balance = cash_balances.get(month_end, 0) if cash_balances else 0
                total_portfolio = portfolio_value + cash_balance
                data.append({'event_date': month_end, 'portfolio': total_portfolio})
            return pd.DataFrame(data)

        elif account_type == 'joint':
            single_accounts = await JointAccountService.get_linked_single_accounts(self.db, account_id)
            if not single_accounts:
                logger.warning(f"No linked single accounts for joint account {account_id}")
                return pd.DataFrame(columns=['event_date', 'portfolio'])

            earliest_start_date = min(acc['acc_start_date'] for acc in single_accounts)
            earliest_start_date
            month_ends = _generate_historical_month_ends(earliest_start_date, today)
            if not month_ends:
                logger.warning(f"No month-end dates for joint account {account_id}")
                return pd.DataFrame(columns=['event_date', 'portfolio'])

            data = []
            for month_end in month_ends:
                total_portfolio = 0
                for single_acc in single_accounts:
                    single_id = single_acc['account_id']
                    portfolio_values, temp_month_end = await self.get_portfolio_values(single_id, 'single', [month_end])
                    cash_balances = await self.cashflow_processor.get_month_end_cash_balances(single_acc, temp_month_end)
                    portfolio_value = portfolio_values.get(month_end, 0)
                    cash_balance = cash_balances.get(month_end, 0) if cash_balances else 0
                    total_portfolio += portfolio_value + cash_balance
                data.append({'event_date': month_end, 'portfolio': total_portfolio})
            return pd.DataFrame(data)

        else:
            raise ValueError(f"Invalid account_type: {account_type}")

    async def get_portfolio_values(self, owner_id: str, owner_type: str, month_ends: list = None) -> Tuple[Dict[date, float], List[date]]:
        """
        Fetch portfolio market values for specified month-end dates or all dates if not provided.

        Args:
            owner_id (str): The ID of the portfolio owner.
            owner_type (str): The type of the portfolio owner.
            month_ends (list, optional): A list of specific dates to filter the results. If None, all dates are included.

        Returns:
            Tuple[Dict[date, float], List[date]]: A tuple containing:
                - A dictionary with snapshot dates as keys and total market values as values.
                - A list of all snapshot dates in ascending order.
        """
        query = (
            select(
                AccountActualPortfolio.snapshot_date,
                func.sum(AccountActualPortfolio.market_value).label("total_value")
            )
            .where(
                AccountActualPortfolio.owner_id == owner_id,
                AccountActualPortfolio.owner_type == owner_type
            )
        )
        if month_ends is not None:
            query = query.where(AccountActualPortfolio.snapshot_date.in_(month_ends))
        query = query.group_by(AccountActualPortfolio.snapshot_date).order_by(AccountActualPortfolio.snapshot_date)
        result = await self.db.execute(query)
        rows = result.all()
        date_value_dict = {row.snapshot_date: row.total_value for row in rows}
        date_list = [row.snapshot_date for row in rows]
        return date_value_dict, date_list

    async def get_progression_df(self, owner_id: str, owner_type: str) -> pd.DataFrame:
        """Fetch cashflow data for an account from the database."""
        try:
            query = (
                select(AccountCashflow.event_date, AccountCashflow.cashflow)
                .where(AccountCashflow.owner_id == owner_id)
                .where(AccountCashflow.owner_type == owner_type)
            )
            result = await self.db.execute(query)
            cashflows = result.all()
            df = pd.DataFrame(
                [(row.event_date, row.cashflow) for row in cashflows],
                columns=['event_date', 'cashflow']
            )
            if df.empty:
                logger.warning(f"No cashflow data found for {owner_type} account {owner_id}")
            return df
        except Exception as e:
            logger.error(f"Error fetching cashflow data for {owner_type} account {owner_id}: {e}")
            return pd.DataFrame(columns=['event_date', 'cashflow'])

    async def get_cashflow_progression_df(self, account: dict) -> pd.DataFrame:
        """Generate a DataFrame with all event dates, cashflows, and portfolio values for an account."""
        account_id = account['account_id']
        account_type = account['account_type']

        if account_type == 'single':
            acc_start_date = pd.to_datetime(account['acc_start_date'])
            acc_start_date_monthend = acc_start_date + pd.offsets.MonthEnd(0)
            fiscal_start_date = acc_start_date.replace(day=1, month=4)

            progression_df = await self.get_progression_df(account_id, 'single')
            if progression_df.empty:
                logger.warning(f"No cashflow data for single account {account_id}")
            
            portfolio_df = await self.get_month_end_portfolio_df(account)

            if portfolio_df.empty:
                logger.warning(f"No portfolio data for single account {account_id}")
            
            if progression_df.empty and portfolio_df.empty:
                return pd.DataFrame(columns=['event_date', 'cashflow', 'portfolio'])
            
            all_dates = pd.concat(
                [progression_df['event_date'], portfolio_df['event_date']]
            ).drop_duplicates().sort_values().reset_index(drop=True)
            
            combined_df = pd.DataFrame({'event_date': all_dates})
        
            combined_df = combined_df.merge(progression_df, on='event_date', how='left')
            combined_df['cashflow'] = combined_df['cashflow'].fillna(0)
            combined_df = combined_df.merge(portfolio_df, on='event_date', how='left').fillna(0)
            
            if account['broker_name'] == 'zerodha':
                combined_df = combined_df[combined_df['event_date'] >= acc_start_date_monthend.date()]

            combined_df = self.get_main_cashflow_progression_df(combined_df)
            return combined_df[['event_date', 'cashflow', 'portfolio', 'portfolio_plus_cash']]

        elif account_type == 'joint':
            single_accounts = await JointAccountService.get_linked_single_accounts(self.db, account_id)
            if not single_accounts:
                logger.warning(f"No linked single accounts for joint account {account_id}")
                return pd.DataFrame(columns=['event_date', 'cashflow', 'portfolio'])
            
            progression_dfs = []
            for single_acc in single_accounts:
                single_acc['account_type'] = 'single'
                df = await self.get_cashflow_progression_df(single_acc)
                if not df.empty:
                    progression_dfs.append(df)
            
            if not progression_dfs:
                logger.warning(f"No progression data for joint account {account_id}")
                return pd.DataFrame(columns=['event_date', 'cashflow', 'portfolio'])
            
            combined_df = pd.concat(progression_dfs, ignore_index=True)
            aggregated_df = combined_df.groupby('event_date').agg({
                'cashflow': 'sum',
                'portfolio': lambda x: x.sum(min_count=1)
            }).reset_index().fillna(0)

            progression_df = self.get_main_cashflow_progression_df(aggregated_df)
            return progression_df[['event_date', 'cashflow', 'portfolio', 'portfolio_plus_cash']]
        
        else:
            raise ValueError(f"Invalid account_type: {account_type}")

    async def update_cashflow_progression_table(
            self, account: dict, 
            cashflow_progression_df: pd.DataFrame,
            ):
        """Update the account_cashflow_progression table for a specific account by overwriting existing data."""
        account_id = account['account_id']
        account_type = account['account_type']

        if cashflow_progression_df['cashflow'].sum() == 0 and cashflow_progression_df['portfolio'].sum() == 0:
                print(f"Skipping cashflow progression update for {account_type} account {account_id}: no meaningful data")
                return

        await self.db.execute(
            delete(AccountCashflowProgression).where(
                (AccountCashflowProgression.owner_id == account_id) &
                (AccountCashflowProgression.owner_type == account_type)
            )
        )

        new_records = []
        for _, row in cashflow_progression_df.iterrows():
            new_record = AccountCashflowProgression(
                owner_id=account_id,
                owner_type=account_type,
                event_date=row['event_date'],
                cashflow=row['cashflow'],
                portfolio_value=row['portfolio'],
                portfolio_plus_cash=row.get('portfolio_plus_cash', 0.0)
            )
            new_records.append(new_record)

        self.db.add_all(new_records)
        await self.db.commit()

        logger.info(f"Updated cashflow progression for {account_type} account {account_id} with {len(new_records)} records")

    async def update_time_periods_table(self, account: dict, time_periods_df: pd.DataFrame):
        """Update the AccountTimePeriods table with calculated time periods."""
        account_id = account['account_id']
        account_type = account['account_type']
        try:
            await self.db.execute(
                delete(AccountTimePeriods).where(
                    AccountTimePeriods.owner_id == account_id,
                    AccountTimePeriods.owner_type == account_type
                )
            )
            new_records = [
                AccountTimePeriods(
                    owner_id=account_id,
                    owner_type=account_type,
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    start_value=row['start_value'],
                    end_value=row['end_value'],
                    returns=row['returns'],
                    returns_1=row['returns_1']
                ) for _, row in time_periods_df.iterrows()
            ]
            self.db.add_all(new_records)
            await self.db.commit()
            logger.info(f"Updated {len(new_records)} time periods for {account_type} account {account_id}")
        except Exception as e:
            logger.error(f"Error updating time periods for {account_type} account {account_id}: {e}")
            await self.db.rollback()

    def get_time_periods_df(self, cashflow_progression_df: pd.DataFrame) -> pd.DataFrame:
        cashflow_progression_df_v1 = cashflow_progression_df
        abs_twrr_df, absolute_twrr = self._get_twrr(cashflow_progression_df)
        if not absolute_twrr:
            absolute_twrr = 0.0

        financial_year_dfs = self._create_financial_year_dataframes(df=cashflow_progression_df_v1)

        yearly_twrrs = []
        for i, cashflow_progression_df in enumerate(financial_year_dfs):
            cashflow_progression_df = cashflow_progression_df.reset_index(drop=True)
            twrr_df, twrr = self._get_twrrs_for_cagr(cashflow_progression_df)
            if not twrr:
                twrr = 0.0
            yearly_twrrs.append(twrr)

        cagrs = [cagr + 1 for cagr in yearly_twrrs]
        product = reduce(lambda x, y: x * y, cagrs)

        cagr_value = 0
        years_value = self._calculate_years(abs_twrr_df=abs_twrr_df)
        if years_value > 1:
            cagr_value = ((product ** (1 / years_value)) - 1) * 100
        return abs_twrr_df, round(absolute_twrr * 100, 2), round(twrr * 100, 2), round(cagr_value, 2)

    def get_main_cashflow_progression_df(self, cashflow_progression_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate portfolio_plus_cash for the progression DataFrame."""
        cashflow_progression_df['event_date'] = pd.to_datetime(cashflow_progression_df['event_date'])
        cashflow_progression_df = cashflow_progression_df.sort_values('event_date').reset_index(drop=True)
        cashflow_progression_df['month'] = cashflow_progression_df['event_date'].dt.month
        cashflow_progression_df['year'] = cashflow_progression_df['event_date'].dt.year
        cashflow_progression_df['portfolio_plus_cash'] = 0

        grouped_df = cashflow_progression_df.groupby(['year', 'month'])

        monthly_cashflow_list = []
        index_list = []
        for (year, month), group in grouped_df:
            monthly_cashflow = group['cashflow'].sum()
            last_day_of_current_month = calendar.monthrange(year, month)[1]
            last_date_of_current_month = f'{year}-{month:02d}-{last_day_of_current_month:02d}'
            last_date_of_current_month_date = pd.to_datetime(last_date_of_current_month)
            first_date_of_current_month = last_date_of_current_month_date.replace(day=1)
            last_date_of_previous_month = first_date_of_current_month - timedelta(days=1)
            
            index_of_previous_month = 0
            if last_date_of_previous_month in cashflow_progression_df['event_date'].values:
                indices_of_previous_month = cashflow_progression_df.index[
                    cashflow_progression_df['event_date'] == last_date_of_previous_month
                ].tolist()
                index_of_previous_month = indices_of_previous_month[0]

            monthly_cashflow_list.append(monthly_cashflow)
            if index_of_previous_month == 0:
                index_list.append(index_of_previous_month)
            else:
                index_list.append(index_of_previous_month)

        cashflow_progression_df['portfolio_plus_cash'] = cashflow_progression_df['portfolio_plus_cash'].astype(float)
      
        for i in range(1, len(index_list)):
            cashflow_progression_df.loc[index_list[i], 'portfolio_plus_cash'] = (
                monthly_cashflow_list[i] + cashflow_progression_df.loc[index_list[i], 'portfolio']
            )
        cashflow_progression_df = cashflow_progression_df.drop(columns=['year', 'month'])
        cashflow_progression_df = cashflow_progression_df[
            (cashflow_progression_df['cashflow'] != 0) |
            (cashflow_progression_df['portfolio'] != 0) |
            (cashflow_progression_df['portfolio_plus_cash'] != 0)
        ].sort_values('event_date').reset_index(drop=True)

        first_portfolio_date = cashflow_progression_df[
            cashflow_progression_df['portfolio'] > 0
        ]['event_date'].min()
 
        pre_invest_cashflows = cashflow_progression_df[
            (cashflow_progression_df['event_date'] < first_portfolio_date) & 
            (cashflow_progression_df['cashflow'] != 0)
        ]
        starting_cash = pre_invest_cashflows['cashflow'].sum()
        starting_date = pre_invest_cashflows['event_date'].max()

        starting_row = pd.DataFrame([{
            'event_date': starting_date,
            'cashflow': starting_cash,
            'portfolio': 0.0,
            'portfolio_plus_cash': starting_cash
        }])
        rest_cashflow_progression_df = cashflow_progression_df[cashflow_progression_df['event_date'] >= first_portfolio_date].copy()
        final_cashflow_progression_df = pd.concat([starting_row, rest_cashflow_progression_df], ignore_index=True)
        final_cashflow_progression_df.sort_values('event_date', inplace=True)
        return cashflow_progression_df

    def _get_twrr(self, cashflow_progression_df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        if not cashflow_progression_df.empty and cashflow_progression_df['portfolio'].sum() != 0:
            month_end_mask = cashflow_progression_df['portfolio'] > 0
            month_ends = cashflow_progression_df[month_end_mask].copy()

            for i in range(len(month_ends) - 1):
                current_date = month_ends.iloc[i]['event_date']
                next_date = month_ends.iloc[i + 1]['event_date']

                next_month_start = current_date + pd.offsets.MonthBegin(1)
                next_month_end = next_date

                next_month_cashflow = cashflow_progression_df[
                    (cashflow_progression_df['event_date'] > current_date) &
                    (cashflow_progression_df['event_date'] <= next_date)
                ]['cashflow']

                next_month_cashflow_sum = next_month_cashflow.sum()

                if next_month_cashflow_sum == 0:
                    cashflow_progression_df.loc[
                        cashflow_progression_df['event_date'] == current_date,
                        'portfolio_plus_cash'
                    ] = 0
                else:
                    cashflow_progression_df.loc[
                        cashflow_progression_df['event_date'] == current_date,
                        'portfolio_plus_cash'
                    ] = month_ends.iloc[i]['portfolio'] + next_month_cashflow_sum

                last_date = month_ends.iloc[-1]['event_date']
                cashflow_progression_df.loc[
                    cashflow_progression_df['event_date'] == last_date,
                    'portfolio_plus_cash'
                ] = 0

            last_row = cashflow_progression_df.tail(1).copy()
            oldest_date = cashflow_progression_df['event_date'].min()
            oldest_year = oldest_date.year
            oldest_month = oldest_date.month

            first_month_mask = (cashflow_progression_df['event_date'].dt.year == oldest_year) & \
                (cashflow_progression_df['event_date'].dt.month == oldest_month)
            
            first_month = cashflow_progression_df[first_month_mask]
            first_month_cashflow_sum = first_month['cashflow'].sum()
            
            first_portfolio_idx = cashflow_progression_df[cashflow_progression_df['portfolio'] != 0].index[0]
            first_portfolio_date = cashflow_progression_df.loc[first_portfolio_idx, 'event_date']
            cashflow_before = cashflow_progression_df.loc[:first_portfolio_idx - 1]
            non_zero_cashflows = cashflow_before[cashflow_before['cashflow'] != 0]

            if not non_zero_cashflows.empty:
                first_cashflow_idx = non_zero_cashflows.index[-1]
                first_cashflow_date = cashflow_progression_df.loc[first_cashflow_idx, 'event_date']
                total_cashflow = cashflow_before['cashflow'].sum()
                new_cashflow_progression_df = cashflow_progression_df.loc[first_cashflow_idx:].copy()
                new_cashflow_progression_df.loc[first_cashflow_idx, 'cashflow'] = total_cashflow
            
            else:
                first_cashflow_idx = first_portfolio_idx
                first_cashflow_date = first_portfolio_date
                total_cashflow = 0
                new_cashflow_progression_df = cashflow_progression_df.loc[first_cashflow_idx:].copy()
                new_cashflow_progression_df.loc[first_cashflow_idx, 'cashflow'] = total_cashflow

            new_cashflow_progression_df = new_cashflow_progression_df.reset_index(drop=True)
            
            first_row = new_cashflow_progression_df.iloc[0]
            if first_row['portfolio_plus_cash'] == 0 and first_row['cashflow'] != 0:
                new_cashflow_progression_df.loc[0, 'portfolio_plus_cash'] = first_row['cashflow']
            elif first_row['portfolio_plus_cash'] != 0:
                next_month_start = first_row['event_date'].replace(day=1) + pd.DateOffset(months=1)
                next_month_end = next_month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)
                next_month_cashflow = cashflow_progression_df[
                    (cashflow_progression_df['event_date'] >= next_month_start) &
                    (cashflow_progression_df['event_date'] <= next_month_end)
                ]['cashflow'].sum()

                expected_ppc = first_row['portfolio'] + next_month_cashflow
                if abs(first_row['portfolio_plus_cash'] - expected_ppc) > 1e-2:
                    new_cashflow_progression_df.loc[0, 'portfolio_plus_cash'] = expected_ppc
            
            month_end_mask = (
                (new_cashflow_progression_df['event_date'] == new_cashflow_progression_df['event_date'] + pd.offsets.MonthEnd(0)) & 
                (new_cashflow_progression_df['portfolio'] == 0)
            )
            new_cashflow_progression_df.loc[month_end_mask, 'portfolio'] = new_cashflow_progression_df.loc[month_end_mask, 'portfolio_plus_cash']
        
            cashflow_progression_df = new_cashflow_progression_df[new_cashflow_progression_df['portfolio_plus_cash'] != 0]
            cashflow_progression_df = pd.concat([cashflow_progression_df, last_row], ignore_index=True)

            if cashflow_progression_df.empty:
                return pd.DataFrame(columns=["start_value", "start_date", "end_value", "end_date", "returns", "returns_1"]), 1
            
            start_value_list = list(cashflow_progression_df['portfolio_plus_cash'])
            end_value_list = list(cashflow_progression_df['portfolio'])
            start_date_list = list(cashflow_progression_df['event_date'])
            end_date_list = list(cashflow_progression_df['event_date'])

            start_value_list.pop(-1)
            end_value_list.pop(0)
            start_date_list.pop(-1)
            end_date_list.pop(0)

            twrr_data = {
                'start_date' : start_date_list,
                'start_value' : start_value_list,
                'end_date': end_date_list,
                'end_value' : end_value_list,
            }

            abs_twrr_df = pd.DataFrame(twrr_data)
            abs_twrr_df['returns'] = (abs_twrr_df['end_value'] / abs_twrr_df['start_value']) - 1
            abs_twrr_df['returns_1'] = abs_twrr_df['returns'] + 1
            absolute_twrr = ((abs_twrr_df['returns_1'].prod()) - 1)
            return abs_twrr_df, absolute_twrr

        else:
            return pd.DataFrame(columns=[['start_date', 'start_value', 'end_date', 'end_value', 'returns', 'returns_1']]), None

    def _get_twrrs_for_cagr(self, cashflow_progression_df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        if not cashflow_progression_df.empty and cashflow_progression_df['portfolio'].sum() != 0:
            month_end_mask = cashflow_progression_df['portfolio'] > 0
            month_ends = cashflow_progression_df[month_end_mask].copy()

            for i in range(len(month_ends) - 1):
                current_date = month_ends.iloc[i]['event_date']
                next_date = month_ends.iloc[i + 1]['event_date']

                next_month_start = current_date + pd.offsets.MonthBegin(1)
                next_month_end = next_date

                next_month_cashflow = cashflow_progression_df[
                    (cashflow_progression_df['event_date'] > current_date) &
                    (cashflow_progression_df['event_date'] <= next_date)
                ]['cashflow']

                next_month_cashflow_sum = next_month_cashflow.sum()
                has_no_cashflows = (next_month_cashflow == 0).all()

                if has_no_cashflows:
                    cashflow_progression_df.loc[
                        cashflow_progression_df['event_date'] == current_date,
                        'portfolio_plus_cash'
                    ] = 0
                else:
                    cashflow_progression_df.loc[
                        cashflow_progression_df['event_date'] == current_date,
                        'portfolio_plus_cash'
                    ] = month_ends.iloc[i]['portfolio'] + next_month_cashflow_sum

                last_date = month_ends.iloc[-1]['event_date']
                cashflow_progression_df.loc[
                    cashflow_progression_df['event_date'] == last_date,
                    'portfolio_plus_cash'
                ] = 0  
            
            last_row = cashflow_progression_df.tail(1).copy()
            oldest_date = cashflow_progression_df['event_date'].min()
            oldest_year = oldest_date.year
            oldest_month = oldest_date.month

            first_month_mask = (cashflow_progression_df['event_date'].dt.year == oldest_year) & \
                (cashflow_progression_df['event_date'].dt.month == oldest_month)
            
            first_month = cashflow_progression_df[first_month_mask]
            first_month_cashflow_sum = first_month['cashflow'].sum()
            
            first_portfolio_idx = cashflow_progression_df[cashflow_progression_df['portfolio'] != 0].index[0]
            first_portfolio_date = cashflow_progression_df.loc[first_portfolio_idx, 'event_date']
            cashflow_before = cashflow_progression_df.loc[:first_portfolio_idx - 1]
            non_zero_cashflows = cashflow_before[cashflow_before['cashflow'] != 0]

            if not non_zero_cashflows.empty:
                first_cashflow_idx = non_zero_cashflows.index[-1]
                first_cashflow_date = cashflow_progression_df.loc[first_cashflow_idx, 'event_date']
                total_cashflow = cashflow_before['cashflow'].sum()
                new_cashflow_progression_df = cashflow_progression_df.loc[first_cashflow_idx:].copy()
                new_cashflow_progression_df.loc[first_cashflow_idx, 'cashflow'] = total_cashflow
            
            else:
                first_cashflow_idx = first_portfolio_idx
                first_cashflow_date = first_portfolio_date
                total_cashflow = 0
                new_cashflow_progression_df = cashflow_progression_df.loc[first_cashflow_idx:].copy()
                new_cashflow_progression_df.loc[first_cashflow_idx, 'cashflow'] = total_cashflow

            new_cashflow_progression_df = new_cashflow_progression_df.reset_index(drop=True)
            
            first_row = new_cashflow_progression_df.iloc[0]
            if first_row['portfolio_plus_cash'] == 0 and first_row['cashflow'] != 0:
                new_cashflow_progression_df.loc[0, 'portfolio_plus_cash'] = first_row['cashflow']
            elif first_row['portfolio_plus_cash'] != 0:
                next_month_start = first_row['event_date'].replace(day=1) + pd.DateOffset(months=1)
                next_month_end = next_month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)
                next_month_cashflow = cashflow_progression_df[
                    (cashflow_progression_df['event_date'] >= next_month_start) &
                    (cashflow_progression_df['event_date'] <= next_month_end)
                ]['cashflow'].sum()

                expected_ppc = first_row['portfolio'] + next_month_cashflow
                if abs(first_row['portfolio_plus_cash'] - expected_ppc) > 1e-2:
                    new_cashflow_progression_df.loc[0, 'portfolio_plus_cash'] = expected_ppc

            if new_cashflow_progression_df['cashflow'].sum() == 0:
                new_cashflow_progression_df['portfolio_plus_cash'].iloc[0] = new_cashflow_progression_df['portfolio'].iloc[0]

            cashflow_progression_df = new_cashflow_progression_df[new_cashflow_progression_df['portfolio_plus_cash'] != 0]
            cashflow_progression_df = pd.concat([cashflow_progression_df, last_row], ignore_index=True)

            if cashflow_progression_df.empty:
                return pd.DataFrame(columns=["start_value", "start_date", "end_value", "end_date", "returns", "returns_1"]), 1
            
            start_value_list = list(cashflow_progression_df['portfolio_plus_cash'])
            end_value_list = list(cashflow_progression_df['portfolio'])
            start_date_list = list(cashflow_progression_df['event_date'])
            end_date_list = list(cashflow_progression_df['event_date'])

            start_value_list.pop(-1)
            end_value_list.pop(0)
            start_date_list.pop(-1)
            end_date_list.pop(0)

            twrr_data = {
                'start_date' : start_date_list,
                'start_value' : start_value_list,
                'end_date': end_date_list,
                'end_value' : end_value_list,
            }

            abs_twrr_df = pd.DataFrame(twrr_data)
            abs_twrr_df['returns'] = (abs_twrr_df['end_value'] / abs_twrr_df['start_value']) - 1
            abs_twrr_df['returns_1'] = abs_twrr_df['returns'] + 1
            absolute_twrr = ((abs_twrr_df['returns_1'].prod()) - 1)
            return abs_twrr_df, absolute_twrr

        else:
            return pd.DataFrame(columns=[['start_date', 'start_value', 'end_date', 'end_value', 'returns', 'returns_1']]), None

    def _create_financial_year_dataframes(self, df: pd.DataFrame) -> List[pd.DataFrame]:
        df['event_date'] = pd.to_datetime(df['event_date'])
        df = df.sort_values(by='event_date')
        df['year'] = df['event_date'].dt.year
        df['month'] = df['event_date'].dt.month
        df['FinancialYear'] = df.apply(lambda x: x['year'] if x['month'] > 3 else x['year'] - 1, axis=1)
        unique_financial_years = df['FinancialYear'].unique()

        financial_year_dataframes = []
        for year in unique_financial_years:
            start_date_prev = pd.Timestamp(year, 3, 31)
            end_date = pd.Timestamp(year+1, 3, 31)
            if not df[df['event_date'] == start_date_prev].empty:
                start_date = start_date_prev
            else:
                start_date = df[(df['FinancialYear'] == year)]['event_date'].min()
            fy_df = df[(df['event_date'] >= start_date) & (df['event_date'] <= end_date)]
            financial_year_dataframes.append(fy_df)
        return financial_year_dataframes

    def _calculate_years(self, abs_twrr_df: pd.DataFrame) -> float:
        """
        Calculate the total number of investment years based on the sub-periods in the TWRR DataFrame.

        This function calculates the time difference (in years) for each sub-period by subtracting 
        the `start_date` from the `end_date`. It then sums up the years for all rows where `returns` 
        is not equal to 0.

        Args:
            abs_twrr_df (pd.DataFrame): A DataFrame containing sub-period data with the following columns:
                - start_date: The start date of the sub-period.
                - end_date: The end date of the sub-period.
                - returns: The return for the sub-period.

        Returns:
            float: The total number of investment years for all sub-periods where `returns` != 0.
        """
        abs_twrr_df['start_date'] = pd.to_datetime(abs_twrr_df['start_date'])
        abs_twrr_df['end_date'] = pd.to_datetime(abs_twrr_df['end_date'])

        abs_twrr_df['years'] = (abs_twrr_df['end_date'] - abs_twrr_df['start_date']).dt.days / 365.25
        years_value = abs_twrr_df.loc[abs_twrr_df['returns'] != 0, 'years'].sum()
        return years_value
        
