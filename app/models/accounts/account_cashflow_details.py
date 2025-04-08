from sqlalchemy import Column, Integer, Text, Float, Date, TIMESTAMP, func
from app.models.accounts.owner_mixin import OwnerMixin
from sqlalchemy.orm import relationship
from app.models.base import Base

class AccountCashflow(Base, OwnerMixin):
    __tablename__ = "account_cashflow_details"

    cashflow_id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False)
    cashflow = Column(Float, nullable=False)
    tag = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    single_account = relationship(
        "SingleAccount",
        back_populates="cashflow_details",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountCashflow.owner_id), "
                    "AccountCashflow.owner_type=='single')",
        overlaps="cashflow_details,joint_account"
    )

    joint_account = relationship(
        "JointAccount",
        back_populates="cashflow_details",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountCashflow.owner_id), "
                    "AccountCashflow.owner_type=='joint')",
        overlaps="cashflow_details,single_account"
    )
    
    def __repr__(self):
        return f"<AccountCashflow(id={self.cashflow_id}, owner_id={self.owner_id})>"