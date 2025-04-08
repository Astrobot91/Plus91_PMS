from sqlalchemy import Column, Integer, Text, TIMESTAMP, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base

class Basket(Base):
    __tablename__ = "basket_details"

    basket_id = Column(Integer, primary_key=True)
    basket_name = Column(Text, nullable=False)
    allocation_method = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "allocation_method IN ('equal','manual')",
            name="basket_allocation_method_check"
        ),
    )

    stock_mappings = relationship("BasketStockMapping", back_populates="basket", cascade="all, delete-orphan")
    pf_bracket_basket_allocations = relationship("PfBracketBasketAllocation", back_populates="basket")
    portfolio_mappings = relationship("PortfolioBasketMapping", back_populates="basket", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Basket(basket_id={self.basket_id}, name={self.basket_name})>"