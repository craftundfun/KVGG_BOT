import logging

from discord import Member
from sqlalchemy import ForeignKey, select, insert
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.BaseClass import Base

logger = logging.getLogger("KVGG_BOT")


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

    @staticmethod
    def getNotificationSetting(member: Member, session: Session) -> 'NotificationSetting' or None:
        """
        Fetches the notification settings of the given Member from our database.

        :param member: Member, whose settings will be fetched
        :param session: Database-Session
        :return: None if no settings were found, dict otherwise
        """
        from src.Repository.DiscordUsers.DiscordUser import DiscordUser

        getQuery = (select(NotificationSetting)
                    .where(NotificationSetting.discord_id == (select(DiscordUser.id)
                                                              .where(DiscordUser.user_id == str(member.id))
                                                              .scalar_subquery())
                           )
                    )

        try:
            settings = session.scalars(getQuery).one()
        except MultipleResultsFound as error:
            logger.error(f"found multiple results for notification setting for {member.display_name}",
                         exc_info=error, )

            return None
        except NoResultFound:
            logger.debug("found no notification setting for {member.display_name}")

            insertQuery = (insert(NotificationSetting)
                           .values(notifications=True,
                                   double_xp=True,
                                   welcome_back=True,
                                   quest=True,
                                   xp_inventory=True,
                                   status_report=True,
                                   retrospect=True,
                                   xp_spin=True,
                                   discord_id=(select(DiscordUser.id)
                                               .where(DiscordUser.user_id == str(member.id))
                                               .scalar_subquery()),
                                   ))

            try:
                session.execute(insertQuery)
                session.commit()
            except Exception as error:
                logger.error("could not insert (or commit) notification setting for {member.display_name}",
                             exc_info=error)

                return None

            try:
                settings = session.scalars(getQuery).one()
            except MultipleResultsFound as error:
                logger.error(f"found multiple results for notification setting for {member.display_name}",
                             exc_info=error, )

                return None
            except NoResultFound as error:
                logger.error(f"found no notification setting for {member.display_name} after inserting", exc_info=error)

                return None

        return settings
