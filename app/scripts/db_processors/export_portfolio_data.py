import json
import asyncio
import pandas as pd
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.logger import logger
import os

async def export_portfolio_data_to_excel(output_path='/home/admin/Plus91Backoffice/Plus91_Backend/data/temp/portfolio_data.xlsx'):
    """
    Export portfolio data to an Excel file with multiple sheets:
    - Sheet 1: Latest portfolio data for all single accounts
    - Sheet 2: Unique trading symbols from basket stock mapping (excluding exceptions)
    
    Args:
        output_path (str): Path where the Excel file will be saved
    """
    logger.info("Starting export of portfolio data to Excel")
    
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        async with AsyncSessionLocal() as db:
            # Query 1: Latest portfolio data for all single accounts
            latest_portfolio_query = """
            WITH latest_snapshots AS (
                SELECT 
                    owner_id,
                    MAX(snapshot_date) as latest_date
                FROM account_actual_portfolio
                WHERE owner_type = 'single'
                GROUP BY owner_id
            )
            SELECT 
                sa.single_account_id as account_id,
                c.broker_code,
                b.broker_name,
                aap.trading_symbol,
                aap.quantity,
                aap.market_value,
                aap.snapshot_date
            FROM single_account sa
            LEFT JOIN latest_snapshots ls
                ON sa.single_account_id = ls.owner_id
            LEFT JOIN account_actual_portfolio aap
                ON sa.single_account_id = aap.owner_id
                AND aap.owner_type = 'single'
                AND aap.snapshot_date = ls.latest_date
            LEFT JOIN client_details c
                ON c.account_id = sa.single_account_id
            LEFT JOIN broker_details b
                ON b.broker_id = c.broker_id
            ORDER BY sa.single_account_id, aap.trading_symbol
            """
            
            # Query 2: Trading symbols from basket_stock_mapping
            basket_symbols_query = """
            SELECT trading_symbol FROM basket_stock_mapping
            """
            
            # Execute the queries
            logger.info("Executing latest portfolio data query")
            result1 = await db.execute(text(latest_portfolio_query))
            portfolio_data = result1.fetchall()
            portfolio_columns = result1.keys()
            
            logger.info("Executing basket stock mapping query")
            result2 = await db.execute(text(basket_symbols_query))
            basket_symbols = result2.fetchall()
            
            # Convert results to DataFrames
            portfolio_df = pd.DataFrame(portfolio_data, columns=portfolio_columns)
            
            # Get set of trading symbols from basket_stock_mapping for filtering
            basket_symbols_set = {row[0] for row in basket_symbols}
            
            # Create dataframe for Sheet 2: symbols NOT IN basket_stock_mapping
            if not portfolio_df.empty:
                # Keep the original portfolio_df for Sheet 1 (all data)
                # Filter for Sheet 2 (only non-basket symbols)
                not_in_basket_df = portfolio_df[~portfolio_df['trading_symbol'].isin(basket_symbols_set)]
                
                # Group the not_in_basket_df by broker_code
                not_in_basket_df = not_in_basket_df.sort_values(['broker_code', 'trading_symbol'])
            else:
                not_in_basket_df = pd.DataFrame(columns=portfolio_columns)

            # Load symbol rename map
            renamer_path = '/home/admin/Plus91Backoffice/Plus91_Backend/data/symbol_renamer.json'
            with open(renamer_path, 'r') as f:
                symbol_map = json.load(f)
            # Apply renaming to trading_symbol in both DataFrames
            portfolio_df['trading_symbol'] = portfolio_df['trading_symbol']\
                .apply(lambda s: symbol_map.get(s, s))
            not_in_basket_df['trading_symbol'] = not_in_basket_df['trading_symbol']\
                .apply(lambda s: symbol_map.get(s, s))

            # Filter out rows in not_in_basket_df where quantity is zero, NA, or empty string
            not_in_basket_df['quantity'] = not_in_basket_df['quantity'].replace('', pd.NA)
            not_in_basket_df = not_in_basket_df.dropna(subset=['quantity'])
            not_in_basket_df = not_in_basket_df[not_in_basket_df['quantity'] != 0]
            
            # Remove rows that are already in the exceptions file
            exceptions_file = '/home/admin/Plus91Backoffice/Plus91_Backend/data/cashflow_data/plus91_reco_exceptions.xlsx'
            
            try:
                # Check if exceptions file exists and read it
                if os.path.exists(exceptions_file) and os.path.getsize(exceptions_file) > 0:
                    logger.info(f"Reading exceptions from file: {exceptions_file}")
                    exceptions_df = pd.read_excel(exceptions_file)
                    
                    # Check if the exceptions file has the required columns
                    if 'broker_code' in exceptions_df.columns and 'trading_symbol' in exceptions_df.columns:
                        # Create unique keys for efficient matching
                        exceptions_df['unique_key'] = exceptions_df['broker_code'] + '|' + exceptions_df['trading_symbol'].astype(str)
                        exceptions_keys = set(exceptions_df['unique_key'].dropna())
                        
                        # Create the same key in the non-basket symbols dataframe
                        not_in_basket_df['unique_key'] = not_in_basket_df['broker_code'] + '|' + not_in_basket_df['trading_symbol'].astype(str)
                        
                        # Filter out rows matching exceptions
                        before_count = len(not_in_basket_df)
                        not_in_basket_df = not_in_basket_df[~not_in_basket_df['unique_key'].isin(exceptions_keys)]
                        after_count = len(not_in_basket_df)
                        
                        logger.info(f"Removed {before_count - after_count} rows that matched exceptions")
                        
                        # Drop the temporary key column
                        not_in_basket_df = not_in_basket_df.drop(columns=['unique_key'])
                    else:
                        logger.warning("Exceptions file doesn't have required columns, skipping exception filtering")
                else:
                    logger.info("Exceptions file does not exist or is empty, no exceptions to filter")
            except Exception as e:
                logger.error(f"Error processing exceptions file: {str(e)}")
                logger.info("Continuing without filtering exceptions")

            # Create a Pandas Excel writer using the specified output path
            logger.info(f"Writing data to Excel file: {output_path}")
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Write each DataFrame to a different sheet
                # Sheet 1: All portfolio data (unfiltered)
                portfolio_df.to_excel(writer, sheet_name='All_Portfolio_Data', index=False)
                # Sheet 2: Only non-basket symbols
                not_in_basket_df.to_excel(writer, sheet_name='Portfolio_Non_Basket_Symbols', index=False)
            
            logger.info(f"Successfully exported data to {output_path}")
            logger.info(f"Sheet 1: {len(portfolio_df)} total portfolio records")
            logger.info(f"Sheet 2: {len(not_in_basket_df)} portfolio records (symbols not in basket, excluding exceptions)")
            
    except Exception as e:
        logger.error(f"Error exporting portfolio data to Excel: {e}")
        raise

async def main():
    await export_portfolio_data_to_excel()

if __name__ == "__main__":
    asyncio.run(main())