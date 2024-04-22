from sqlalchemy import Column, BigInteger, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class DiscordUserRelation(Base):
    __tablename__ = 'discord_user_relation'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discord_user_id_1 = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    discord_user_id_2 = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    value = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    last_time = Column(DateTime, nullable=True)
    frequency = Column(BigInteger, nullable=False, default=1)
    type = Column(Enum('online', 'stream', 'university'), nullable=True)
    # noinspection PyTypeChecker
    discord_user_1 = relationship("DiscordUser", foreign_keys=discord_user_id_1)
    # noinspection PyTypeChecker
    discord_user_2 = relationship("DiscordUser", foreign_keys=discord_user_id_2)

    def __repr__(self):
        return (f"DiscordUserRelation(id={self.id}, DiscordUser1={self.discord_user_1},"
                f" DiscordUser2={self.discord_user_2})")
