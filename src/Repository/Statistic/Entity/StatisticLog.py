from sqlalchemy import Column, Integer, DateTime, ForeignKey, BigInteger, String
from sqlalchemy import Enum
from sqlalchemy.orm import relationship

from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Repository.BaseClass import Base


class StatisticLog(Base):
    __tablename__ = 'statistic_log'

    id = Column(Integer, primary_key=True)
    value = Column(BigInteger, nullable=False, default=0)
    # time_online = Column(Integer, nullable=False)
    type = Column(Enum(StatisticsParameter), nullable=False)
    created_at = Column(DateTime, nullable=False)
    statistic_type = Column(String(80), nullable=False)
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_user_id)

    def __repr__(self):
        return f"StatisticLog(id={self.id}, DiscordUser={self.discord_user})"
