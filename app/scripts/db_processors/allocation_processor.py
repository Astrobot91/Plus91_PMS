from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.portfolio.basket_details import Basket
from app.models.portfolio.bracket_details import Bracket
from app.models.portfolio.basket_stock_mapping import BasketStockMapping
from app.models.portfolio.pf_bracket_basket_allocation import PfBracketBasketAllocation
from app.logger import logger

class AllocationProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_bracket_for_amount(self, amount: float) -> Bracket:
        """Find the appropriate bracket for a given amount."""
        query = select(Bracket).where(
            Bracket.bracket_min <= amount,
            Bracket.bracket_max >= amount
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_basket_allocations_for_amount(self, amount: float, portfolio_id: int = 1) -> dict:
        """
        Get basket allocations for a given investment amount from the default portfolio template.
        
        Args:
            amount: Investment amount
            portfolio_id: Portfolio template ID (defaults to 1 for standard portfolio)
            
        Returns:
            Dictionary containing:
            - bracket_info: Selected bracket details
            - basket_allocations: List of basket allocations with percentages
        """
        try:
            # Get appropriate bracket for the amount
            bracket = await self.get_bracket_for_amount(amount)
            if not bracket:
                logger.warning(f"No suitable bracket found for amount {amount}")
                return {}

            # Get basket allocations for this bracket from pf_bracket_basket_allocation
            query = select(
                PfBracketBasketAllocation,
                Basket.basket_name
            ).join(
                Basket,
                PfBracketBasketAllocation.basket_id == Basket.basket_id
            ).where(
                PfBracketBasketAllocation.portfolio_id == portfolio_id,
                PfBracketBasketAllocation.bracket_id == bracket.bracket_id
            )

            result = await self.db.execute(query)
            allocations = result.all()

            basket_allocations = [{
                'basket_id': row.PfBracketBasketAllocation.basket_id,
                'basket_name': row.basket_name,
                'allocation_pct': row.PfBracketBasketAllocation.allocation_pct
            } for row in allocations]

            return {
                'bracket_info': {
                    'bracket_id': bracket.bracket_id,
                    'bracket_name': bracket.bracket_name,
                    'min_amount': bracket.bracket_min,
                    'max_amount': bracket.bracket_max
                },
                'basket_allocations': basket_allocations,
                'total_allocation': sum(b['allocation_pct'] for b in basket_allocations)
            }

        except Exception as e:
            logger.error(f"Error getting basket allocations: {e}")
            raise


