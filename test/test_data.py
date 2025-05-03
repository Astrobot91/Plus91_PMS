import asyncio
import pandas as pd
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer

keynote_data_transformer = KeynoteDataTransformer()
zerodha_data_transformer = ZerodhaDataTransformer()

cashflow = asyncio.run(keynote_data_transformer.transform_ledger_to_cashflow(
    broker_code="TS020",
    ))

cashflow_df = pd.DataFrame(cashflow)
print(cashflow_df)


# cashflow = asyncio.run(zerodha_data_transformer.transform_ledger_to_cashflow(
#     broker_code="TWV350"
# ))

# holdings, a = asyncio.run(keynote_data_transformer.transform_holdings_to_actual_portfolio(
#     broker_code="MK100",
#     for_date="2025-04-30"
# ))
# print(holdings)
# holding_df = pd.DataFrame(holdings)
# print(holding_df, a)


# zerodha_data_transformer = ZerodhaDataTransformer()
# holdings, a = asyncio.run(zerodha_data_transformer.transform_holdings_to_actual_portfolio(
#     broker_code="MDK705",
#     year=2025,
#     month=4,
# ))
# print(holdings, a)


# cashflow = asyncio.run(zerodha_data_transformer.transform_ledger_to_cashflow(
#     broker_code="MM5525"
# ))

# cashflow_df = pd.DataFrame(cashflow)
