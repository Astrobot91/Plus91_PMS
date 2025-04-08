from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class JointAccountMapping(Base):
    __tablename__ = "joint_account_mapping"

    joint_account_mapping_id = Column(Integer, primary_key=True)
    joint_account_id = Column(
        String,
        ForeignKey("joint_account.joint_account_id", ondelete="CASCADE"),
        nullable=False
    )
    account_id = Column(
        String,
        ForeignKey("single_account.single_account_id", ondelete="CASCADE"),
        nullable=False
    )

    joint_account = relationship("JointAccount", back_populates="joint_account_mappings")

    def __repr__(self):
        return f"<JointAccountMapping(id={self.joint_account_mapping_id})>"