from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class GameDiscordMapping(Base):
    __tablename__ = "game_discord_mapping"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_played_online: Mapped[int]
    time_played_offline: Mapped[int]
    last_played: Mapped[Optional[datetime]]

    discord_game_id: Mapped[int] = mapped_column(ForeignKey('discord_game.id'))
    discord_game: Mapped["Game"] = relationship("Game")

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"GameDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, DiscordGame={self.discord_game})"
