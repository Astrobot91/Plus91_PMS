from sqlalchemy import Column, String, Date, Numeric, TIMESTAMP, func
from app.models.base import Base

class HistStockPrice(Base):
    __tablename__ = "hist_stock_prices"

    trading_symbol = Column(String(20), primary_key=True, nullable=False)
    snapshot_date = Column(Date, primary_key=True, nullable=False)
    open = Column(Numeric(12, 4), nullable=False)
    high = Column(Numeric(12, 4), nullable=False)
    low = Column(Numeric(12, 4), nullable=False)
    close = Column(Numeric(12, 4), nullable=False)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<HistStockPrice(trading_symbol={self.trading_symbol}, snapshot_date={self.snapshot_date}, close={self.close})>"