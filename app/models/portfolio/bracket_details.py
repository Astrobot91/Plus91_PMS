from sqlalchemy import Column, Integer, Float, Text, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Bracket(Base):
    __tablename__ = "bracket_details"

    bracket_id = Column(Integer, primary_key=True, autoincrement=True)
    bracket_min = Column(Float, nullable=False)
    bracket_max = Column(Float, nullable=False)
    bracket_name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    accounts = relationship("SingleAccount", back_populates="bracket")
    joint_accounts = relationship("JointAccount", back_populates="bracket")
    pf_bracket_basket_allocations = relationship("PfBracketBasketAllocation", back_populates="bracket", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Bracket(id={self.bracket_id}, name={self.bracket_name})>"