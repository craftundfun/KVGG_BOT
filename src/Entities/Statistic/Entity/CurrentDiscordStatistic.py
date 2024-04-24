from sqlalchemy import Column, String, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class CurrentDiscordStatistic(Base):
    __tablename__ = 'current_discord_statistic'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    discord_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    statistic_type = Column(String(80), nullable=False)
    statistic_time = Column(String(80), nullable=False)
    value = Column(BigInteger, nullable=False, default=0)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)

    def __repr__(self):
        return f"CurrentDiscordStatistic(id={self.id}, DiscordUser={self.discord_user})"
