from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.Repository.BaseClass import Base


class Quest(Base):
    __tablename__ = "quest"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_type: Mapped[str]
    type: Mapped[str]
    description: Mapped[str]
    value_to_reach: Mapped[int]
    unit: Mapped[str]

    def __repr__(self):
        return f"Quest(id={self.id})"
