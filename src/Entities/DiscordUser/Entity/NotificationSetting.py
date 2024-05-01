from sqlalchemy import Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class NotificationSetting(Base):
    __tablename__ = 'notification_setting'

    id = Column(Integer, primary_key=True)
    discord_id = Column(Integer, ForeignKey('discord.id'), nullable=False)
    notifications = Column(Boolean, default=True, nullable=False)
    double_xp = Column(Boolean, default=True, nullable=False)
    welcome_back = Column(Boolean, default=True, nullable=False)
    quest = Column(Boolean, default=True, nullable=False)
    xp_inventory = Column(Boolean, default=True, nullable=False)
    status_report = Column(Boolean, default=True, nullable=False)
    retrospect = Column(Boolean, default=True, nullable=False)
    xp_spin = Column(Boolean, default=True, nullable=False)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)

    def __repr__(self):
        return f"NotificationSetting(id={self.id}, DiscordUser={self.discord_user})"
