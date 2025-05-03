from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.portfolio.portfolio_template_details import PortfolioTemplate
from app.models.portfolio.bracket_details import Bracket
from app.models.portfolio.basket_details import Basket
from app.models.portfolio.pf_bracket_basket_allocation import PfBracketBasketAllocation
from app.models.portfolio.basket_stock_mapping import BasketStockMapping
from app.models.accounts.account_bracket_basket_allocation import AccountBracketBasketAllocation
from app.logger import logger, log_function_call
from typing import Dict, Any, List

class PortfolioService:
    @staticmethod
    @log_function_call
    async def get_portfolios(db: AsyncSession) -> List[Dict[str, Any]]:
        """Fetch all portfolio templates from the database, ordered by portfolio_id."""
        logger.info("Fetching all portfolio templates")
        q = await db.execute(select(PortfolioTemplate).order_by(PortfolioTemplate.portfolio_id))
        rows = q.scalars().all()
        data = [
            {
                "portfolio_id": r.portfolio_id,
                "portfolio_name": r.portfolio_name,
                "description": r.description
            }
            for r in rows
        ]
        logger.debug(f"Retrieved {len(data)} portfolio templates")
        return data

    @staticmethod
    @log_function_call
    async def get_portfolio_structure(db: AsyncSession, portfolio_id: int) -> Dict[str, Any]:
        """Fetch the complete structure of a portfolio, including brackets, baskets, allocations, and basket stocks."""
        logger.info(f"Fetching portfolio structure for portfolio_id: {portfolio_id}")
        p = await db.get(PortfolioTemplate, portfolio_id)
        if not p:
            logger.warning(f"Portfolio with ID {portfolio_id} not found")
            return {}
        
        logger.debug("Fetching brackets")
        qb = await db.execute(select(Bracket).order_by(Bracket.bracket_id))
        brackets = qb.scalars().all()
        
        logger.debug("Fetching baskets")
        qb2 = await db.execute(select(Basket).order_by(Basket.basket_id))
        baskets = qb2.scalars().all()
        
        logger.debug(f"Fetching allocations for portfolio_id: {portfolio_id}")
        qa = await db.execute(select(PfBracketBasketAllocation).where(PfBracketBasketAllocation.portfolio_id == portfolio_id))
        allocations = qa.scalars().all()
        
        bracket_list = [
            {
                "bracket_id": b.bracket_id,
                "bracket_name": b.bracket_name,
                "min_amount": b.bracket_min,
                "max_amount": b.bracket_max
            }
            for b in brackets
        ]
        
        basket_list = [
            {
                "basket_id": b.basket_id,
                "basket_name": b.basket_name,
                "allocation_method": b.allocation_method
            }
            for b in baskets
        ]
        
        alloc_map = {(a.bracket_id, a.basket_id): a.allocation_pct for a in allocations}
        
        basket_stocks = {}
        for b in baskets:
            logger.debug(f"Fetching stocks for basket: {b.basket_name}")
            qbsm = await db.execute(select(BasketStockMapping).where(BasketStockMapping.basket_id == b.basket_id))
            stocks = qbsm.scalars().all()
            stock_list = [
                {
                    "basket_stock_mapping_id": s.basket_stock_mapping_id,
                    "stock": s.trading_symbol,
                    "multiplier": s.multiplier
                }
                for s in stocks
            ]
            basket_stocks[b.basket_name] = stock_list
        
        logger.info(f"Portfolio structure fetched successfully for portfolio_id: {portfolio_id}")
        return {
            "portfolio_id": p.portfolio_id,
            "portfolio_name": p.portfolio_name,
            "description": p.description,
            "brackets": bracket_list,
            "baskets": basket_list,
            "allocations": alloc_map,
            "basket_stocks": basket_stocks
        }

    @staticmethod
    @log_function_call
    async def save_portfolio_structure(db: AsyncSession, portfolio_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update the portfolio structure, including brackets, baskets, allocations, and basket stocks."""
        logger.info(f"Saving portfolio structure for portfolio_id: {portfolio_id}")
        brackets_data = payload.get("brackets", [])
        baskets_data = payload.get("baskets", [])
        alloc_map = payload.get("allocations", {})
        basket_stocks = payload.get("basket_stocks", {})

        # Fetch existing brackets and baskets
        logger.debug("Fetching existing brackets")
        qb = await db.execute(select(Bracket))
        existing_brackets = qb.scalars().all()
        bracket_by_id = {str(b.bracket_id): b for b in existing_brackets}

        logger.debug("Fetching existing baskets")
        qb2 = await db.execute(select(Basket))
        existing_baskets = qb2.scalars().all()
        basket_by_id = {str(b.basket_id): b for b in existing_baskets}

        # Fetch existing allocations for the portfolio
        logger.debug(f"Fetching existing allocations for portfolio_id: {portfolio_id}")
        qa = await db.execute(
            select(PfBracketBasketAllocation).where(PfBracketBasketAllocation.portfolio_id == portfolio_id)
        )
        existing_allocs = qa.scalars().all()
        alloc_index = {(str(a.bracket_id), str(a.basket_id)): a for a in existing_allocs}

        # Process brackets
        bracket_ids_seen = set()
        for br in brackets_data:
            bracket_id = (br.get("bracket_id") or "").strip()
            b_name = (br.get("bracket_name") or "").strip()
            min_amt = br.get("min_amount", 0)
            max_amt = br.get("max_amount", 0)

            if not b_name and min_amt == 0 and max_amt == 0 and bracket_id:
                continue
            if bracket_id:
                existing_br = bracket_by_id.get(bracket_id)
                if existing_br:
                    if not b_name:
                        b_name = f"BRACKET_{existing_br.bracket_id}"
                    if min_amt <= max_amt:
                        existing_br.bracket_name = b_name
                        existing_br.bracket_min = min_amt
                        existing_br.bracket_max = max_amt
                    bracket_ids_seen.add(bracket_id)
            else:
                if not b_name:
                    b_name = "BRACKET_NULL"
                new_br = Bracket(bracket_name=b_name, bracket_min=min_amt, bracket_max=max_amt)
                db.add(new_br)
                await db.flush()
                bracket_ids_seen.add(str(new_br.bracket_id))
                br["bracket_id"] = str(new_br.bracket_id)
        await db.commit()
        logger.info("Brackets saved/updated successfully")

        # Process baskets
        basket_ids_seen = set()
        for bs in baskets_data:
            basket_id = (bs.get("basket_id") or "").strip()
            b_name = (bs.get("basket_name") or "").strip()
            allocation_method = bs.get("allocation_method", "manual")
            if not b_name and basket_id:
                continue
            if basket_id:
                existing_ba = basket_by_id.get(basket_id)
                if existing_ba:
                    if not b_name:
                        b_name = f"BASKET_{existing_ba.basket_id}"
                    existing_ba.basket_name = b_name
                    existing_ba.allocation_method = allocation_method
                    basket_ids_seen.add(basket_id)
            else:
                if not b_name:
                    b_name = "BASKET_NULL"
                new_bs = Basket(basket_name=b_name, allocation_method=allocation_method)
                db.add(new_bs)
                await db.flush()
                basket_ids_seen.add(str(new_bs.basket_id))
                bs["basket_id"] = str(new_bs.basket_id)
        await db.commit()
        logger.info("Baskets saved/updated successfully")

        # Delete unused brackets and baskets
        qb3 = await db.execute(select(Bracket))
        all_brackets_after = qb3.scalars().all()
        qb4 = await db.execute(select(Basket))
        all_baskets_after = qb4.scalars().all()

        for oldb in all_brackets_after:
            str_id = str(oldb.bracket_id)
            if str_id not in bracket_ids_seen:
                # --- FIX: Delete dependent AccountBracketBasketAllocation first ---
                delete_account_alloc_stmt = delete(AccountBracketBasketAllocation).where(
                    AccountBracketBasketAllocation.bracket_id == oldb.bracket_id
                )
                await db.execute(delete_account_alloc_stmt)
                logger.debug(f"Deleted dependent AccountBracketBasketAllocations for bracket: {str_id}")
                # --- End Fix ---

                # Also delete PfBracketBasketAllocation related to this bracket
                delete_pf_alloc_stmt = delete(PfBracketBasketAllocation).where(
                    PfBracketBasketAllocation.bracket_id == oldb.bracket_id
                )
                await db.execute(delete_pf_alloc_stmt)
                logger.debug(f"Deleted PfBracketBasketAllocations for bracket: {str_id}")

                await db.delete(oldb)
                logger.debug(f"Deleted unused bracket: {str_id}")

        for oldb in all_baskets_after:
            str_id = str(oldb.basket_id)
            if str_id not in basket_ids_seen:
                 # Delete PfBracketBasketAllocation related to this basket
                delete_pf_alloc_stmt = delete(PfBracketBasketAllocation).where(
                    PfBracketBasketAllocation.basket_id == oldb.basket_id
                )
                await db.execute(delete_pf_alloc_stmt)
                logger.debug(f"Deleted PfBracketBasketAllocations for basket: {str_id}")

                # Delete BasketStockMapping related to this basket
                delete_stock_mapping_stmt = delete(BasketStockMapping).where(
                    BasketStockMapping.basket_id == oldb.basket_id
                )
                await db.execute(delete_stock_mapping_stmt)
                logger.debug(f"Deleted BasketStockMappings for basket: {str_id}")

                await db.delete(oldb)
                logger.debug(f"Deleted unused basket: {str_id}")

        await db.commit() # Commit deletions before proceeding

        # Update allocations
        qb5 = await db.execute(select(Bracket))
        final_brackets = qb5.scalars().all()
        bracket_by_id_final = {str(b.bracket_id): b for b in final_brackets}

        qb6 = await db.execute(select(Basket))
        final_baskets = qb6.scalars().all()
        basket_by_id_final = {str(b.basket_id): b for b in final_baskets}

        for k, v in alloc_map.items():
            parts = k.split("::", 1)
            if len(parts) != 2:
                continue
            br_id_str, ba_id_str = parts[0].strip(), parts[1].strip()
            if not br_id_str or not ba_id_str:
                continue

            br_obj = bracket_by_id_final.get(br_id_str)
            ba_obj = basket_by_id_final.get(ba_id_str)
            if not br_obj or not ba_obj:
                continue

            pair = (br_id_str, ba_id_str)
            ex_alloc = alloc_index.get(pair)
            if ex_alloc:
                ex_alloc.allocation_pct = v
            else:
                new_alloc = PfBracketBasketAllocation(
                    portfolio_id=portfolio_id,
                    bracket_id=br_obj.bracket_id,
                    basket_id=ba_obj.basket_id,
                    allocation_pct=v
                )
                db.add(new_alloc)
                logger.debug(f"Added new allocation for bracket {br_id_str} and basket {ba_id_str}")

        await db.commit()
        logger.info("Allocations saved/updated successfully")

        # Update basket stocks
        qb7 = await db.execute(select(Basket))
        updated_baskets = qb7.scalars().all()
        updated_baskets_by_id = {str(b.basket_id): b for b in updated_baskets}

        for bId, stlist in basket_stocks.items():
            b_obj = updated_baskets_by_id.get(bId.strip())
            if not b_obj:
                continue

            logger.debug(f"Updating stocks for basket: {b_obj.basket_name}")
            qbsm = await db.execute(select(BasketStockMapping).where(BasketStockMapping.basket_id == b_obj.basket_id))
            old_stocks = qbsm.scalars().all()
            old_map = {str(o.basket_stock_mapping_id): o for o in old_stocks}
            new_ids = set()

            for row in stlist:
                sy = (row.get("stock") or "").strip()
                mt = row.get("multiplier", 0)
                mapping_id = row.get("basket_stock_mapping_id")

                if not sy and mt == 0 and not mapping_id:
                    continue

                if mapping_id:
                    old_record = old_map.get(mapping_id)
                    if old_record:
                        old_record.trading_symbol = sy
                        old_record.multiplier = mt
                    new_ids.add(mapping_id)
                else:
                    nm = BasketStockMapping(
                        basket_id=b_obj.basket_id,
                        trading_symbol=sy if sy else "STOCK_NULL",
                        multiplier=mt
                    )
                    db.add(nm)
                    await db.flush()
                    new_ids.add(str(nm.basket_stock_mapping_id))
                    logger.debug(f"Added new stock mapping for basket {b_obj.basket_id}")

            for old_mid, old_ob in old_map.items():
                if old_mid not in new_ids:
                    await db.delete(old_ob)
                    logger.debug(f"Deleted unused stock mapping: {old_mid}")

        await db.commit()
        logger.info(f"Portfolio structure saved successfully for portfolio_id: {portfolio_id}")
        return {"status": "ok"}