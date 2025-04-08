from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from app.models.base import Base

class StockException(Base):
    __tablename__ = "stock_exceptions"

    id = Column(Integer, primary_key=True)
    account_id = Column(String, nullable=False)
    trading_symbol = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    def __repr__(self):
        return f"<StockException(id={self.id}, account_id={self.account_id}, trading_symbol={self.trading_symbol})>"