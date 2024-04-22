from sqlalchemy import Column, BigInteger, Text

from src.Entities.BaseClass import Base


class DiscordGame(Base):
    __tablename__ = 'discord_game'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)

    def __repr__(self):
        return f"DiscordGame(id={self.id}, name={self.name})"
