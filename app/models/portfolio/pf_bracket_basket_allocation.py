from sqlalchemy import Column, Integer, Float, TIMESTAMP, func, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class PfBracketBasketAllocation(Base):
    __tablename__ = "pf_bracket_basket_allocation"

    allocation_id = Column(Integer, primary_key=True, autoincrement=True)
    bracket_id = Column(Integer, ForeignKey("bracket_details.bracket_id"), nullable=True)
    basket_id = Column(Integer, ForeignKey("basket_details.basket_id"), nullable=True)
    portfolio_id = Column(Integer, ForeignKey("portfolio_template_details.portfolio_id"), nullable=True)
    allocation_pct = Column(Float, nullable=False, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("allocation_pct >= 0", name="allocation_pct_positive"),
    )

    bracket = relationship("Bracket", back_populates="pf_bracket_basket_allocations")
    basket = relationship("Basket", back_populates="pf_bracket_basket_allocations")
    portfolio_template = relationship("PortfolioTemplate", back_populates="pf_bracket_basket_allocations")

    def __repr__(self):
        return f"<PfBracketBasketAllocation(id={self.allocation_id}, allocation_pct={self.allocation_pct})>"