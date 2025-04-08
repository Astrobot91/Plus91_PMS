from sqlalchemy import Column, String, CheckConstraint


class OwnerMixin:
    owner_id = Column(String, nullable=False)
    owner_type = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("owner_type IN ('single','joint')", name="owner_type_check"),
    )
    