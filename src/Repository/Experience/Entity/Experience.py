from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class Experience(Base):
    __tablename__ = 'experience'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    xp_amount = Column(BigInteger, default=0, nullable=True)
    xp_boosts_inventory = Column(JSON, nullable=True)
    last_spin_for_boost = Column(DateTime, nullable=True)
    active_xp_boosts = Column(JSON, nullable=True)
    last_cookie_boost = Column(DateTime, nullable=True)
    time_to_send_spin_reminder = Column(DateTime, nullable=True)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_user_id)

    def __repr__(self):
        return f"Experience(id={self.id}, DiscordUser={self.discord_user})"
