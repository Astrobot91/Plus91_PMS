from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.database import get_db
from app.services.portfolio.portfolio_service import PortfolioService 

portfolio_router = APIRouter(prefix="/portfolios", tags=["Portfolios"])

@portfolio_router.get("/", response_model=List[Dict[str, Any]])
async def list_portfolios(db: AsyncSession = Depends(get_db)):
    """Get data for all the portfolios in the DB."""
    return await PortfolioService.get_portfolios(db)  

@portfolio_router.get("/{portfolio_id}/structure", response_model=Dict[str, Any])
async def portfolio_structure(portfolio_id: int, db: AsyncSession = Depends(get_db)):
    data = await PortfolioService.get_portfolio_structure(db, portfolio_id)  
    if not data:
        raise HTTPException(404, "Portfolio not found")
    return data

@portfolio_router.post("/{portfolio_id}/structure/save", response_model=Dict[str, Any])
async def save_structure(portfolio_id: int, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await PortfolioService.save_portfolio_structure(db, portfolio_id, payload) 