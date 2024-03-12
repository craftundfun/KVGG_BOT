from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class CurrentDiscordStatistic(Base):
    __tablename__ = "current_discord_statistic"

    id: Mapped[int] = mapped_column(primary_key=True)
    statistic_type: Mapped[str]
    statistic_time: Mapped[str]
    value: Mapped[int]

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"CurrentDiscordStatistic(id={self.id}, DiscordUser={self.discord_user})"
