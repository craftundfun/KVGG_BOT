from sqlalchemy import Column, BigInteger, Text, Boolean

from src.Entities.BaseClass import Base


class DiscordGame(Base):
    __tablename__ = 'discord_game'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    visible = Column(Boolean, nullable=False, default=True)
    is_playable = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"DiscordGame(id={self.id}, name={self.name})"
