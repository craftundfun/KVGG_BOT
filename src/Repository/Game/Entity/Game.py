from typing import Optional

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.Repository.BaseClass import Base


class Game(Base):
    __tablename__ = "discord_game"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[Optional[str]]
    name: Mapped[str]

    def __repr__(self):
        return f"Game(id={self.id}, name={self.name})"
