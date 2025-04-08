from sqlalchemy import Column, String, Text, TIMESTAMP, func, text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Broker(Base):
    __tablename__ = "broker_details"

    broker_id = Column(
        String,
        primary_key=True,
        server_default=text("CONCAT('BROKER_', LPAD(NEXTVAL('broker_seq')::TEXT, 4, '0'))")
    )
    broker_name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    clients = relationship("Client", back_populates="broker")

    def __repr__(self):
        return f"<Broker(id={self.broker_id}, name={self.broker_name})>"

