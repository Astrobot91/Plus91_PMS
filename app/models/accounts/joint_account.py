from sqlalchemy import (
    Column, String, Text, TIMESTAMP, Float, Integer, func, ForeignKey, text
)
from sqlalchemy.orm import relationship
from app.models.base import Base

class JointAccount(Base):
    __tablename__ = "joint_account"

    joint_account_id = Column(
        String,
        primary_key=True,
        server_default=text("CONCAT('JACC_', LPAD(NEXTVAL('joint_account_seq')::TEXT, 6, '0'))")
    )
    joint_account_name = Column(Text, nullable=False)
    account_type = Column(String, nullable=False, default="joint")
    portfolio_id = Column(Integer, ForeignKey("portfolio_template_details.portfolio_id"), nullable=True)
    bracket_id = Column(Integer, ForeignKey("bracket_details.bracket_id"), nullable=True)
    pf_value = Column(Float, default=0)
    cash_value = Column(Float, default=0)
    total_holdings = Column(Float, default=0)
    invested_amt = Column(Float, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    portfolio_template = relationship("PortfolioTemplate", back_populates="joint_accounts")
    bracket = relationship("Bracket", back_populates="joint_accounts")
    
    performance = relationship(
        "AccountPerformance",
        uselist=False,
        back_populates="joint_account",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountPerformance.owner_id), "
                    "AccountPerformance.owner_type=='joint')",
        overlaps="performance,single_account"
    )

    actual_portfolios = relationship(
        "AccountActualPortfolio",
        back_populates="joint_account",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountActualPortfolio.owner_id), "
                    "AccountActualPortfolio.owner_type=='joint')",
        overlaps="actual_portfolios,single_account"
    )

    ideal_portfolios = relationship(
        "AccountIdealPortfolio",
        back_populates="joint_account",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountIdealPortfolio.owner_id), "
                    "AccountIdealPortfolio.owner_type=='joint')",
        overlaps="ideal_portfolios,single_account"
    )
    
    cashflow_details = relationship(
        "AccountCashflow",
        back_populates="joint_account",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountCashflow.owner_id), "
                    "AccountCashflow.owner_type=='joint')",
        overlaps="cashflow_details,single_account"
    )
    
    time_periods = relationship(
        "AccountTimePeriods",
        back_populates="joint_account",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountTimePeriods.owner_id), "
                    "AccountTimePeriods.owner_type=='joint')",
        overlaps="time_periods,single_account"
    )

    actual_portfolio_exceptions = relationship(
        "AccountActualPortfolioException",
        primaryjoin="and_(JointAccount.joint_account_id == foreign(AccountActualPortfolioException.owner_id), "
                    "AccountActualPortfolioException.owner_type == 'joint')",
        back_populates="joint_account"
    )

    joint_account_mappings = relationship("JointAccountMapping", back_populates="joint_account")

    def __repr__(self):
        return f"<JointAccount(joint_account_id={self.joint_account_id}, name={self.joint_account_name})>"