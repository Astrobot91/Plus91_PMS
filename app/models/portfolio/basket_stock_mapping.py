from sqlalchemy import Column, Integer, Text, Float, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class BasketStockMapping(Base):
    __tablename__ = "basket_stock_mapping"

    basket_stock_mapping_id = Column(Integer, primary_key=True, autoincrement=True)
    basket_id = Column(Integer, ForeignKey("basket_details.basket_id", ondelete="CASCADE"), nullable=False)
    trading_symbol = Column(Text, nullable=False)
    multiplier = Column(Float, nullable=False)

    basket = relationship("Basket", back_populates="stock_mappings")

    def __repr__(self):
        return f"<BasketStockMapping(id={self.basket_stock_mapping_id}, symbol={self.trading_symbol})>"
