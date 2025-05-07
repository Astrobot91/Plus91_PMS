import asyncio
from sqlalchemy.orm import aliased
from sqlalchemy import select, func, literal, union_all
from app.logger import logger

from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.clients.client_details import Client
from app.models.clients.distributor_details import Distributor
from app.models.clients.broker_details import Broker
from app.models.accounts.account_cashflow_details import AccountCashflow
from app.models.accounts.account_time_periods import AccountTimePeriods
from app.models.accounts.account_actual_portfolio import AccountActualPortfolio
from app.models.accounts.account_ideal_portfolio import AccountIdealPortfolio
from app.models.accounts.account_performance import AccountPerformance
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.models.portfolio.portfolio_template_details import PortfolioTemplate
from app.models.portfolio.pf_bracket_basket_allocation import PfBracketBasketAllocation
from app.models.portfolio.portfolio_basket_mapping import PortfolioBasketMapping
from app.models.portfolio.bracket_details import Bracket
from app.models.portfolio.basket_details import Basket
from app.models.portfolio.basket_stock_mapping import BasketStockMapping
from app.database import AsyncSessionLocal

# Aliases for tables
sa = aliased(SingleAccount, name='single_account_1')
ja = aliased(JointAccount, name='joint_account_1')
cd = aliased(Client, name='client_details_1')
ap = aliased(AccountActualPortfolio, name='account_actual_portfolio_1')
perf = aliased(AccountPerformance, name='account_performance_1')
jam = aliased(JointAccountMapping, name='joint_account_mapping_1')
dist = aliased(Distributor, name='distributor_1')

# Subquery for latest snapshot date for single accounts
latest_ap_single = select(
    AccountActualPortfolio.owner_id,
    func.max(AccountActualPortfolio.snapshot_date).label('latest_date')
).where(AccountActualPortfolio.owner_type == 'single'
).group_by(AccountActualPortfolio.owner_id
).subquery('latest_ap_single')

# Subquery for latest snapshot date for joint accounts
latest_ap_joint = select(
    AccountActualPortfolio.owner_id,
    func.max(AccountActualPortfolio.snapshot_date).label('latest_date')
).where(AccountActualPortfolio.owner_type == 'joint'
).group_by(AccountActualPortfolio.owner_id
).subquery('latest_ap_joint')

# Single account query
single_query = select(
    literal('single').label('account_type'),
    sa.single_account_id.label('account_id'),
    sa.account_name,
    cd.acc_start_date,
    sa.cash_value,
    sa.invested_amt,
    sa.pf_value,
    sa.total_holdings,
    ap.trading_symbol,
    ap.quantity,
    ap.market_value,
    ap.snapshot_date,
    perf.total_twrr,
    perf.current_yr_twrr,
    perf.cagr,
    cd.broker_code.label('broker_codes'),
    dist.name.label('distributor_name')  # Changed from dist.distributor_name to dist.name
).join(
    cd, sa.single_account_id == cd.account_id
).outerjoin(
    dist, cd.distributor_id == dist.distributor_id
).join(
    latest_ap_single, sa.single_account_id == latest_ap_single.c.owner_id
).outerjoin(
    perf, (sa.single_account_id == perf.owner_id) & (perf.owner_type == 'single')
).outerjoin(
    ap, (sa.single_account_id == ap.owner_id) &
        (ap.owner_type == 'single') &
        (ap.snapshot_date == latest_ap_single.c.latest_date)
)

# Joint account query with explicit joins
joint_query = select(
    literal('joint').label('account_type'),
    ja.joint_account_id.label('account_id'),
    ja.joint_account_name.label('account_name'),
    func.min(cd.acc_start_date).label('acc_start_date'),
    ja.cash_value,
    ja.invested_amt,
    ja.pf_value,
    ja.total_holdings,
    ap.trading_symbol,
    ap.quantity,
    ap.market_value,
    ap.snapshot_date,
    perf.total_twrr,
    perf.current_yr_twrr,
    perf.cagr,
    func.string_agg(cd.broker_code, ', ').label('broker_codes'),
    func.coalesce(
        func.min(func.nullif(dist.name, '')), 
        func.min(dist.name)
    ).label('distributor_name')
).join(
    jam, ja.joint_account_id == jam.joint_account_id
).join(
    sa, jam.account_id == sa.single_account_id
).join(
    cd, sa.single_account_id == cd.account_id
).outerjoin(
    dist, cd.distributor_id == dist.distributor_id
).join(
    latest_ap_joint, ja.joint_account_id == latest_ap_joint.c.owner_id
).outerjoin(
    perf, (ja.joint_account_id == perf.owner_id) & (perf.owner_type == 'joint')
).outerjoin(
    ap, (ja.joint_account_id == ap.owner_id) &
        (ap.owner_type == 'joint') &
        (ap.snapshot_date == latest_ap_joint.c.latest_date)
).group_by(
    ja.joint_account_id,
    ja.joint_account_name,
    ja.cash_value,
    ja.invested_amt,
    ja.pf_value,
    ja.total_holdings,
    ap.trading_symbol,
    ap.quantity,
    ap.market_value,
    ap.snapshot_date,
    perf.total_twrr,
    perf.current_yr_twrr,
    perf.cagr
)

# Combine single and joint queries
combined_query = union_all(single_query, joint_query)

async def report_datafeeder():
    """
    Fetch report data by combining single and joint account details from the database.

    Returns:
        List[dict]: A list of dictionaries containing the report data.
    """
    logger.info("Starting report data feeder process")
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Executing combined query for single and joint accounts")
            result = await session.execute(combined_query)
            rows = result.mappings().all()
            report_data = [dict(row) for row in rows]
            logger.info(f"Successfully fetched {len(report_data)} rows of report data")
            logger.debug(f"Sample row: {report_data[0] if report_data else 'No data'}")
            return report_data
        except Exception as e:
            logger.error(f"Error in report data feeder: {str(e)}")
            raise
        finally:
            logger.debug("Closing database session")
