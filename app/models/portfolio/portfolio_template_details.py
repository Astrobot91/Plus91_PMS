from sqlalchemy import Column, Integer, Text, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class PortfolioTemplate(Base):
    __tablename__ = "portfolio_template_details"

    portfolio_id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    accounts = relationship("SingleAccount", back_populates="portfolio_template")
    joint_accounts = relationship("JointAccount", back_populates="portfolio_template")
    pf_bracket_basket_allocations = relationship("PfBracketBasketAllocation", back_populates="portfolio_template")
    basket_mappings = relationship("PortfolioBasketMapping", back_populates="portfolio", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PortfolioTemplate(id={self.portfolio_id}, name={self.portfolio_name})>"