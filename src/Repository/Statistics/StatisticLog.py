from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class StatisticLog(Base):
    __tablename__ = "statistic_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_online: Mapped[int]
    type: Mapped[str]
    created_at: Mapped[datetime]

    discord_user_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"StatisticLog(id={self.id}, DiscordUser={self.discord_user})"
