from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class CounterDiscordMapping(Base):
    __tablename__ = 'counter_discord_mapping'

    id = Column(Integer, primary_key=True, autoincrement=True)
    counter_id = Column(Integer, ForeignKey('counter.id'), nullable=False)
    discord_id = Column(Integer, ForeignKey('discord.id'), nullable=False)
    value = Column(Integer, default=0, nullable=False)

    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)
    # noinspection PyTypeChecker
    counter = relationship("Counter", foreign_keys=counter_id)

    def __repr__(self):
        return f"CounterDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Counter={self.counter})"
