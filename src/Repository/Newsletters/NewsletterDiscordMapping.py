from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base


class NewsletterDiscordMapping(Base):
    __tablename__ = "newsletter_discord_mapping"

    id: Mapped[int] = mapped_column(primary_key=True)
    sent_at: Mapped[datetime]

    newsletter_id: Mapped[int] = mapped_column(ForeignKey("newsletter.id"))
    newsletter: Mapped["Newsletter"] = relationship("Newsletter")

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"NewsletterDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Newsletter={self.newsletter})"
