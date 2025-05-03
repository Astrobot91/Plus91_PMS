from sqlalchemy import Column, Integer, String, Float, TIMESTAMP, Text, func, Date, CheckConstraint
from app.models.accounts.owner_mixin import OwnerMixin
from sqlalchemy.orm import relationship
from app.models.base import Base

class AccountIdealPortfolio(Base):

    __tablename__ = 'account_ideal_portfolio'

    owner_id = Column(String, primary_key=True)
    owner_type = Column(String, nullable=False)
    snapshot_date = Column(Date, primary_key=True)
    trading_symbol = Column(Text, primary_key=True)
    basket = Column(Text, primary_key=True)
    allocation_pct = Column(Float, nullable=False)
    investment_amount = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('single', 'joint')", 
            name="ideal_portfolio_owner_type_check"
        ),
    )

    single_account = relationship(
        "SingleAccount",
        back_populates="ideal_portfolios",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountIdealPortfolio.owner_id), "
                    "AccountIdealPortfolio.owner_type=='single')",
        overlaps="ideal_portfolios,joint_account"
    )
    
    joint_account = relationship(
        "JointAccount",
        back_populates="ideal_portfolios",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountIdealPortfolio.owner_id), "
                    "AccountIdealPortfolio.owner_type=='joint')",
        overlaps="ideal_portfolios,single_account"
    )

    def __repr__(self):
        return f"<AccountIdealPortfolio(owner_id={self.owner_id}, symbol={self.trading_symbol})>"