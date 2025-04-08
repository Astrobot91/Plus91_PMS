from sqlalchemy import Column, String, Text, TIMESTAMP, func, text
from sqlalchemy.orm import relationship
from app.models.base import Base


class Distributor(Base):
    __tablename__ = "distributor_details"

    distributor_id = Column(
        String,
        primary_key=True,
        server_default=text("CONCAT('DIST_', LPAD(NEXTVAL('distributor_seq')::TEXT, 5, '0'))")
    )
    name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    clients = relationship("Client", back_populates="distributor")

    def __repr__(self):
        return f"<Distributor(id={self.distributor_id}, name={self.name})>"
