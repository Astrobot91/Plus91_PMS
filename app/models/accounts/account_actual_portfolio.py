from sqlalchemy import Column, String, Text, Float, TIMESTAMP, ForeignKey, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.accounts.owner_mixin import OwnerMixin
from app.models.base import Base

class AccountActualPortfolio(Base):

    __tablename__ = 'account_actual_portfolio'

    owner_id = Column(String, primary_key=True)
    owner_type = Column(String, nullable=False)
    snapshot_date = Column(Date, primary_key=True) 
    trading_symbol = Column(Text, primary_key=True)
    quantity = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    single_account = relationship(
        "SingleAccount",
        back_populates="actual_portfolios",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountActualPortfolio.owner_id), "
                    "AccountActualPortfolio.owner_type=='single')",
        overlaps="actual_portfolios,joint_account"
    )
    joint_account = relationship(
        "JointAccount",
        back_populates="actual_portfolios",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountActualPortfolio.owner_id), "
                    "AccountActualPortfolio.owner_type=='joint')",
        overlaps="actual_portfolios,single_account"
    )

    def __repr__(self):
        return f"<AccountActualPortfolio(owner_id={self.owner_id}, symbol={self.trading_symbol})>"