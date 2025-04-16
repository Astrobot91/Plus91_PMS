import asyncio
import pandas as pd
from app.scripts.data_fetchers.data_transformer import KeynoteDataTransformer, ZerodhaDataTransformer

keynote_data_transformer = KeynoteDataTransformer()
zerodha_data_transformer = ZerodhaDataTransformer()

# cashflow = asyncio.run(keynote_data_transformer.transform_ledger_to_cashflow(
#     broker_code="MK100",
#     ))

# cashflow_df = pd.DataFrame(cashflow)
# print(cashflow_df)


cashflow = asyncio.run(zerodha_data_transformer.transform_ledger_to_cashflow(
    broker_code="TWV350"
))

# holdings = asyncio.run(keynote_data_transformer.transform_holdings_to_actual_portfolio(
#     broker_code="MK100",
#     for_date="2025-04-11"
# ))
# holding_df = pd.DataFrame(holdings)
# print(holding_df)


zerodha_data_transformer = ZerodhaDataTransformer()
# holdings = asyncio.run(zerodha_data_transformer.transform_holdings_to_actual_portfolio(
#     broker_code="TWV350",
#     year=2024,
#     month=4,
# ))


# cashflow = asyncio.run(zerodha_data_transformer.transform_ledger_to_cashflow(
#     broker_code="MM5525"
# ))

# cashflow_df = pd.DataFrame(cashflow)
