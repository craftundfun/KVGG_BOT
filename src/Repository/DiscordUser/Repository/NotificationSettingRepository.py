import logging

from discord import Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.DiscordUser.Entity.NotificationSetting import NotificationSetting

logger = logging.getLogger("KVGG_BOT")


def getNotificationSettings(member: Member, session: Session) -> NotificationSetting | None:
    """
    Fetches the notification settings of the given Member from our database.

    :param member: Member, whose settings will be fetched
    :param session: Database-Session
    :return: None if no settings were found, dict otherwise
    """
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
            logger.error(f"could not insert (or commit) notification setting for {member.display_name}",
                         exc_info=error)
            session.rollback()

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
    except Exception as error:
        logger.error(f"an error occurred while fetching NotificationSettings for {member.display_name}", exc_info=error)

        return None

    return settings
