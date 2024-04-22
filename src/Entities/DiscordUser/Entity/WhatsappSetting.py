from sqlalchemy import Column, BigInteger, Boolean
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


# from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser

class WhatsappSetting(Base):
    __tablename__ = 'whatsapp_setting'

    id = Column(BigInteger, autoincrement=True, primary_key=True)
    discord_user_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    receive_join_notification = Column(Boolean, default=True, nullable=False)
    receive_leave_notification = Column(Boolean, default=True, nullable=False)
    receive_uni_join_notification = Column(Boolean, default=True, nullable=False)
    receive_uni_leave_notification = Column(Boolean, default=True, nullable=False)
    suspend_times = Column(JSON)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", back_populates="whatsapp_setting")

    def __repr__(self):
        return f"WhatsappSetting(id={self.id}, DiscordUser={self.discord_user})"
