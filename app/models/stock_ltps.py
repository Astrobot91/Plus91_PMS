from sqlalchemy import Column, Integer, String, Float, TIMESTAMP, func
from app.models.base import Base

class StockLTP(Base):
    __tablename__ = "stock_ltps"

    id = Column(Integer, primary_key=True)
    trading_symbol = Column(String, unique=True, nullable=False)
    ltp = Column(Float, nullable=False)
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    def __repr__(self):
        return f"<StockLTP(id={self.id}, trading_symbol={self.trading_symbol}, ltp={self.ltp})>"