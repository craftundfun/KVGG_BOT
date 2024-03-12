from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.Repository.BaseClass import Base


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote: Mapped[str]
    message_external_id: Mapped[int]

    def __repr__(self):
        return f"Quote(id={self.id})"
