from sqlalchemy import (
    Column, Integer, String, Float, TIMESTAMP, func, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.models.base import Base

class AccountActualPortfolioException(Base):
    __tablename__ = "account_actual_portfolio_exceptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(255), nullable=False)
    owner_type = Column(String(10), nullable=False)
    trading_symbol = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint("owner_type IN ('single', 'joint')", name="owner_type_check"),
        CheckConstraint("quantity >= 0", name="quantity_positive"),
        UniqueConstraint("owner_id", "owner_type", "trading_symbol", name="unique_exception"),
    )
    single_account = relationship(
        "SingleAccount",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountActualPortfolioException.owner_id), "
                    "AccountActualPortfolioException.owner_type == 'single')",
        back_populates="actual_portfolio_exceptions",
        overlaps="actual_portfolio_exceptions,joint_account"
    )
    joint_account = relationship(
        "JointAccount",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountActualPortfolioException.owner_id), "
                    "AccountActualPortfolioException.owner_type == 'joint')",
        back_populates="actual_portfolio_exceptions",
        overlaps="actual_portfolio_exceptions,single_account"
    )

    def __repr__(self):
        return f"<AccountActualPortfolioException(id={self.id}, owner_id={self.owner_id}, trading_symbol={self.trading_symbol}, quantity={self.quantity})>"