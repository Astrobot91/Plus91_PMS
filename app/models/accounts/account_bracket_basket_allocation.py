from sqlalchemy import Column, Integer, String, Float, Boolean, TIMESTAMP, func, ForeignKey, CheckConstraint
from app.models.base import Base

class AccountBracketBasketAllocation(Base):
    __tablename__ = "account_bracket_basket_allocation"

    id = Column(Integer, primary_key=True)
    owner_id = Column(String, nullable=False)
    owner_type = Column(String, nullable=False)
    bracket_id = Column(Integer, ForeignKey("bracket_details.bracket_id"), nullable=False)
    basket_id = Column(Integer, ForeignKey("basket_details.basket_id"), nullable=False)
    allocation_pct = Column(Float, nullable=False)
    is_custom = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("owner_type IN ('single', 'joint')", name="account_bracket_basket_allocation_owner_type_check"),
    )

    def __repr__(self):
        return f"<AccountBracketBasketAllocation(id={self.id}, owner_id={self.owner_id}, allocation_pct={self.allocation_pct})>"