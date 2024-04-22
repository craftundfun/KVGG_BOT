from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from src.Entities.BaseClass import Base


class NewsletterDiscordMapping(Base):
    __tablename__ = 'newsletter_discord_mapping'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    newsletter_id = Column(BigInteger, ForeignKey('newsletter.id'), nullable=False)
    discord_id = Column(BigInteger, ForeignKey('discord.id'), nullable=False)
    sent_at = Column(DateTime, nullable=False)
    # noinspection PyTypeChecker
    newsletter = relationship("Newsletter", foreign_keys=newsletter_id)
    # noinspection PyTypeChecker
    discord_user = relationship("DiscordUser", foreign_keys=discord_id)

    def __repr__(self):
        return f"NewsletterDiscordMapping(id={self.id}, DiscordUser={self.discord_user}, Newsletter={self.newsletter})"
