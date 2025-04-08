import sys
import boto3
import asyncio
import logging
import calendar
import pandas as pd
from app.scripts.db_processors.db_runner import runner
from app.scripts.report_generation.report_generator import (
    generate_report,
    load_bse500_data,
    get_portfolio_summary,
    get_returns_table,
    get_bse500_twrr_cagr,
    get_portfolio_report,
)
from app.scripts.report_generation.data_feeder import report_datafeeder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

s3 = boto3.client('s3')
bucket_name = 'plus91backoffice'

async def main() -> None:
    """Main function to update database and generate reports."""
    try:
        logger.info("Starting database update...")
        await runner()
        logger.info("Database update completed.")

        logger.info("Fetching report data...")
        data = await report_datafeeder()
        if not data:
            logger.warning("No data fetched for reports.")
            return

        report_df = pd.DataFrame(data)
        report_df.loc[:, 'broker_codes'] = report_df['broker_codes'].apply(sort_broker_codes)
        bse500_df = load_bse500_data()

        grouped_df = report_df.groupby('account_id')
        for account_id, group in grouped_df:
            if account_id in ['ACC_000304']:
                logger.info(f"Generating report for account ID: {account_id}")
                account_name = group['account_name'].iloc[0]
                acc_start_date = group['acc_start_date'].iloc[0]
                snapshot_date = group['snapshot_date'].iloc[0]
                invested_amt = group['invested_amt'].iloc[0]
                pf_value = group['pf_value'].iloc[0]
                cash_value = group['cash_value'].iloc[0]
                total_holdings = group['total_holdings'].iloc[0]
                actual_portfolio = group[['trading_symbol', 'quantity', 'market_value']]
                total_twrr = group['total_twrr'].iloc[0]
                current_yr_twrr = group['current_yr_twrr'].iloc[0]
                cagr = group['cagr'].iloc[0]
                broker_code = group['broker_codes'].iloc[0]

                formatted_broker_code = format_broker_code(broker_code)

                portfolio_summary = get_portfolio_summary(str(acc_start_date), total_holdings, invested_amt)
                portfolio_report = get_portfolio_report(actual_portfolio, cash_value, total_holdings)
                bse500_current_yr_twrr, bse500_abs_twrr, bse500_abs_cagr = get_bse500_twrr_cagr(
                    str(acc_start_date), str(snapshot_date), bse500_df
                )
                returns_table = get_returns_table(
                    current_yr_twrr, total_twrr, cagr,
                    bse500_current_yr_twrr, bse500_abs_twrr, bse500_abs_cagr
                )

                # Generate the report
                logo_path = "/home/admin/Plus91Backoffice/plus91_management/app/scripts/report_generation/assets/Plus91_logo.jpeg"
                down_design_path = "/home/admin/Plus91Backoffice/plus91_management/app/scripts/report_generation/assets/Down_design.jpeg"
                pdf_bytes = generate_report(
                    portfolio_report,
                    portfolio_summary,
                    returns_table,
                    logo_path,
                    down_design_path,
                    account_name,
                    formatted_broker_code,
                    str(acc_start_date)
                )
                snapshot_date = pd.to_datetime(snapshot_date)
                year = snapshot_date.year
                month_abbr = calendar.month_abbr[snapshot_date.month].upper()

                filename = f"{formatted_broker_code} {month_abbr} {year} Report.pdf"
                s3_key = f"PLUS91_PMS/reports/{year}/{month_abbr}/{filename}"
                s3.put_object(
                        Body=pdf_bytes,
                        Bucket=bucket_name,
                        Key=s3_key,
                        ContentType='application/pdf'
                    )
                logger.info(f"Report generated for {account_name} in S3 at: {s3_key}.")
    except Exception as e:
        logger.error(f"Error in main process: {e}", exc_info=True)

def format_broker_code(broker_code: str) -> str:
    """Format broker code(s) into a string like '[CODE1 - CODE2]'."""
    if "," in broker_code:
        codes = broker_code.split(", ")
        sorted_codes = sorted(codes)
        return f"[{' - '.join(sorted_codes)}]"
    return f"[{broker_code}]"

def sort_broker_codes(broker_code: str) -> str:
    return ', '.join(sorted(broker_code.split(', ')))


if __name__ == "__main__":
    asyncio.run(main())