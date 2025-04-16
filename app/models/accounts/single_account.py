from sqlalchemy import Column, String, Text, TIMESTAMP, Float, func, ForeignKey, text, Integer
from sqlalchemy.orm import relationship
from app.models.base import Base

class SingleAccount(Base):
    __tablename__ = "single_account"
    
    single_account_id = Column(
        String,
        primary_key=True,
        server_default=text("CONCAT('ACC_', LPAD(NEXTVAL('single_account_seq')::TEXT, 6, '0'))")
    )
    account_name = Column(Text, nullable=False)
    account_type = Column(String, nullable=False, default='single')
    portfolio_id = Column(Integer, ForeignKey("portfolio_template_details.portfolio_id"), nullable=True)
    bracket_id = Column(Integer, ForeignKey("bracket_details.bracket_id"), nullable=True)
    pf_value = Column(Float, default=0)
    cash_value = Column(Float, default=0)
    total_holdings = Column(Float, default=0)
    invested_amt = Column(Float, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    portfolio_template = relationship("PortfolioTemplate", back_populates="accounts")
    bracket = relationship("Bracket", back_populates="accounts")

    performance = relationship(
        "AccountPerformance",
        uselist=False,
        back_populates="single_account",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountPerformance.owner_id), "
                    "AccountPerformance.owner_type=='single')",
        overlaps="performance,joint_account"
    )

    actual_portfolios = relationship(
        "AccountActualPortfolio",
        back_populates="single_account",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountActualPortfolio.owner_id), "
                    "AccountActualPortfolio.owner_type=='single')",
        overlaps="actual_portfolios,joint_account"
    )
    ideal_portfolios = relationship(
        "AccountIdealPortfolio",
        back_populates="single_account",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountIdealPortfolio.owner_id), "
                    "AccountIdealPortfolio.owner_type=='single')",
        overlaps="ideal_portfolios,joint_account"
    )
    
    cashflow_details = relationship(
        "AccountCashflow",
        back_populates="single_account",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountCashflow.owner_id), "
                    "AccountCashflow.owner_type=='single')",
        overlaps="cashflow_details,joint_account"
    )
    
    time_periods = relationship(
        "AccountTimePeriods",
        back_populates="single_account",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountTimePeriods.owner_id), "
                    "AccountTimePeriods.owner_type=='single')",
        overlaps="time_periods,joint_account"
    )
    
    actual_portfolio_exceptions = relationship(
        "AccountActualPortfolioException",
        primaryjoin="and_(SingleAccount.single_account_id == foreign(AccountActualPortfolioException.owner_id), "
                    "AccountActualPortfolioException.owner_type == 'single')",
        back_populates="single_account",
        overlaps="actual_portfolio_exceptions"
    )

    client = relationship("Client", back_populates="account")

    def __repr__(self):
        return f"<Account(single_account_id={self.single_account_id}, name={self.account_name})>"