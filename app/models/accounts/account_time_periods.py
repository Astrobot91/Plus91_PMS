from sqlalchemy import Column, String, Integer, Float, Date, TIMESTAMP, func
from app.models.accounts.owner_mixin import OwnerMixin
from sqlalchemy.orm import relationship
from app.models.base import Base

class AccountTimePeriods(Base, OwnerMixin):
    __tablename__ = "account_time_periods"

    owner_id = Column(String, primary_key=True)
    owner_type = Column(String, nullable=False)
    time_period_id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    start_value = Column(Float, nullable=False)
    end_date = Column(Date, nullable=False)
    end_value = Column(Float, nullable=False)
    returns = Column(Float, nullable=False)
    returns_1 = Column(Float)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())  # Added

    single_account = relationship(
        "SingleAccount",
        back_populates="time_periods",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountTimePeriods.owner_id), "
                    "AccountTimePeriods.owner_type=='single')",
        overlaps="time_periods,joint_account"
    )

    joint_account = relationship(
        "JointAccount",
        back_populates="time_periods",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountTimePeriods.owner_id), "
                    "AccountTimePeriods.owner_type=='joint')",
        overlaps="time_periods,single_account"
    )

    def __repr__(self):
        return f"<AccountTimePeriods(id={self.time_period_id}, owner_id={self.owner_id})>"