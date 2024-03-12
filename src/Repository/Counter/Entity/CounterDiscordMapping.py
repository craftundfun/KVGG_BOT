from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.Repository.BaseClass import Base
# from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.Counter.Entity.Counter import Counter


class CounterDiscordMapping(Base):
    __tablename__ = "counter_discord_mapping"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int]

    counter_id: Mapped[int] = mapped_column(ForeignKey("counter.id"))
    counter: Mapped["Counter"] = relationship("Counter")

    discord_id: Mapped[int] = mapped_column(ForeignKey("discord.id"))
    discord_user: Mapped["DiscordUser"] = relationship("DiscordUser")

    def __repr__(self):
        return f"Counter(id={self.id}, DiscordUser={self.discord_user}, Counter={self.counter})"
