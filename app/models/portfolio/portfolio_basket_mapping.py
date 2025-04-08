from sqlalchemy import Column, Integer, ForeignKey, Float, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class PortfolioBasketMapping(Base):
    __tablename__ = "portfolio_basket_mapping"

    portfolio_basket_mapping_id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolio_template_details.portfolio_id", ondelete="CASCADE"), nullable=False)
    basket_id = Column(Integer, ForeignKey("basket_details.basket_id", ondelete="CASCADE"), nullable=False)
    allocation_pct = Column(Float, nullable=True)

    portfolio = relationship("PortfolioTemplate", back_populates="basket_mappings")
    basket = relationship("Basket", back_populates="portfolio_mappings")

    def __repr__(self):
        return f"<PortfolioBasketMapping(id={self.portfolio_basket_mapping_id}, portfolio_id={self.portfolio_id}, basket_id={self.basket_id})>"