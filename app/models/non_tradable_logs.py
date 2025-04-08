from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, func
from app.models.base import Base

class NonTradableLog(Base):
    __tablename__ = "non_tradable_logs"

    id = Column(Integer, primary_key=True)
    account_id = Column(String, nullable=False)
    trading_symbol = Column(String, nullable=False)
    reason = Column(Text)
    event_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<NonTradableLog(id={self.id}, account_id={self.account_id}, trading_symbol={self.trading_symbol})>"