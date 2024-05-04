from sqlalchemy import Column, BigInteger, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class GameDiscordMapping(Base):
    __tablename__ = 'game_discord_mapping'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    discord_game_id = Column(BigInteger, ForeignKey('discord_game.id'), nullable=False)
    time_played_online = Column(BigInteger, nullable=False, default=0)
    time_played_offline = Column(BigInteger, nullable=False, default=0)
    last_played = Column(DateTime, nullable=True)
    currently_playing = Column(Boolean, nullable=False, default=False)

    discord_user = relationship("DiscordUser", back_populates="game_mappings")
    discord_game = relationship("DiscordGame")

    def __repr__(self):
        return f"GameDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, DiscordGame={self.discord_game_id})"
