from datetime import datetime

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.Entities.BaseClass import Base


class Newsletter(Base):
    __tablename__ = "newsletter"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str]
    created_at: Mapped[datetime]

    def __repr__(self):
        return f"Newsletter(id={self.id})"
