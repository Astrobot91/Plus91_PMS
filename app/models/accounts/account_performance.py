from sqlalchemy import Column, String, Float, TIMESTAMP, func
from app.models.accounts.owner_mixin import OwnerMixin
from sqlalchemy.orm import relationship
from app.models.base import Base

class AccountPerformance(Base, OwnerMixin):
    __tablename__ = "account_performance"

    performance_id = Column(String, primary_key=True)
    total_twrr = Column(Float)
    current_yr_twrr = Column(Float)
    cagr = Column(Float)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())  # Added

    single_account = relationship(
        "SingleAccount",
        back_populates="performance",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountPerformance.owner_id), "
                    "AccountPerformance.owner_type=='single')",
        overlaps="performance,joint_account"
    )

    joint_account = relationship(
        "JointAccount",
        back_populates="performance",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountPerformance.owner_id), "
                    "AccountPerformance.owner_type=='joint')",
        overlaps="performance,single_account"
    )

    def __repr__(self):
        return f"<AccountPerformance(owner_id={self.owner_id}, total_twrr={self.total_twrr})>" 