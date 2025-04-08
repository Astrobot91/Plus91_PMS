from sqlalchemy import (
    Column, String, Text, TIMESTAMP, ForeignKey, UniqueConstraint, text   
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class Client(Base):
    __tablename__ = "client_details"

    client_id = Column(
        String,
        primary_key=True,
        server_default=text("CONCAT('CLIENT_', LPAD(NEXTVAL('client_seq')::TEXT, 6, '0'))")
    )
    account_id = Column(String, ForeignKey("single_account.single_account_id", ondelete="SET NULL"), nullable=True)
    client_name = Column(Text, nullable=False)
    broker_id = Column(String, ForeignKey("broker_details.broker_id", ondelete="SET NULL"), nullable=True)
    broker_code = Column(Text, nullable=True)
    broker_passwd = Column(Text, nullable=True)
    pan_no = Column(String, nullable=False)
    phone_no = Column(Text, nullable=True)
    country_code = Column(Text, nullable=True)
    email_id = Column(Text, nullable=True)
    addr = Column(Text, nullable=True)
    acc_start_date = Column(String, nullable=True)
    distributor_id = Column(String, ForeignKey("distributor_details.distributor_id", ondelete="SET NULL"), nullable=True)
    type = Column(Text, nullable=True)
    alias_name = Column(Text, nullable=True)
    alias_phone_no = Column(String, nullable=True)
    alias_addr = Column(Text, nullable=True)
    onboard_status = Column(Text, default="pending")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now()) 

    __table_args__ = (
        UniqueConstraint('broker_id', 'pan_no', name='unique_broker_id_pan'),
    )

    distributor = relationship("Distributor", back_populates="clients")
    broker = relationship("Broker", back_populates="clients")
    account = relationship("SingleAccount", back_populates="client", uselist=False)

    @property
    def broker_name(self):
        return self.broker.broker_name if self.broker else None
    
    @property
    def distributor_name(self):
        return self.distributor.name if self.distributor else None

    def __repr__(self): 
        return f"<Client(client_id={self.client_id}, name={self.client_name})>"