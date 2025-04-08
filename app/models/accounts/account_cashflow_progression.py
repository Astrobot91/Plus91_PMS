from sqlalchemy import Column, Integer, String, Float, Date, TIMESTAMP, func, CheckConstraint
from app.models.base import Base

class AccountCashflowProgression(Base):
    __tablename__ = "account_cashflow_progression"

    id = Column(Integer, primary_key=True)
    owner_id = Column(String, nullable=False)
    owner_type = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    cashflow = Column(Float, nullable=False)
    portfolio_value = Column(Float, nullable=False)
    portfolio_plus_cash = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint("owner_type IN ('single', 'joint')", name="owner_type_check"),
    )

    def __repr__(self):
        return f"<AccountCashflowProgression(id={self.id}, owner_id={self.owner_id}, event_date={self.event_date})>"