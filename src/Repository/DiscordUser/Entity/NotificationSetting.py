from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class NotificationSetting(Base):
    __tablename__ = "notification_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    notifications: Mapped[bool]
    double_xp: Mapped[bool]
    welcome_back: Mapped[bool]
    quest: Mapped[bool]
    xp_inventory: Mapped[bool]
    status_report: Mapped[bool]
    retrospect: Mapped[bool]
    xp_spin: Mapped[bool]

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"NotificationSetting(id={self.id}, DiscordUser={self.discord_user})"
