from typing import Optional

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.Repository.BaseClass import Base


class Counter(Base):
    __tablename__ = "counter"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    tts_voice_line: Mapped[Optional[str]]

    def __repr__(self):
        return f"Counter(id={self.id}, name={self.name})"
