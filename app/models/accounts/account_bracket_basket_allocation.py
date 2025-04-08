from sqlalchemy import Column, Integer, String, Float, Boolean, TIMESTAMP, func, ForeignKey, CheckConstraint
from app.models.base import Base

class AccountBracketBasketAllocation(Base):
    __tablename__ = "account_bracket_basket_allocation"

    id = Column(Integer, primary_key=True)
    account_id = Column(String, nullable=False)
    account_type = Column(String, nullable=False)
    bracket_id = Column(Integer, ForeignKey("bracket_details.bracket_id"), nullable=False)
    basket_id = Column(Integer, ForeignKey("basket_details.basket_id"), nullable=False)
    allocation_pct = Column(Float, nullable=False)
    is_custom = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint("account_type IN ('single', 'joint')", name="account_type_check"),
    )

    def __repr__(self):
        return f"<AccountBracketBasketAllocation(id={self.id}, account_id={self.account_id}, allocation_pct={self.allocation_pct})>"