import logging
from datetime import datetime

from discord import Member, User
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.orm.exc import NoResultFound

from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser

logger = logging.getLogger("KVGG_BOT")


def getDiscordUser(member: Member, session: Session) -> DiscordUser | None:
    """
    Returns the user from the database.
    If he doesn't exist yet, a new entry is created (only if a member was given)

    :param member: Member to retrieve all data from
    :param session: Session of the database connection
    :return: None | Dict[Any, Any] DiscordUser
    """
    if not member or isinstance(member, User):
        logger.debug("member was None or not the correct format")

        return None

    getQuery = select(DiscordUser).where(DiscordUser.user_id == str(member.id))

    try:
        dcUserDb = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"found multiple results for {member.display_name} in database", exc_info=error)

        return None
    except NoResultFound:
        logger.debug("creating new DiscordUser")

        insertQuery = insert(DiscordUser).values(guild_id=str(member.guild.id),
                                                 user_id=str(member.id),
                                                 username=member.display_name,
                                                 discord_name=member.name,
                                                 created_at=datetime.now(), )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new DiscordUser for {member.display_name}", exc_info=error)
            session.rollback()

            return None

        try:
            dcUserDb = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted DiscordUser for {member.display_name}", exc_info=error)

            return None
    except Exception as error:
        logger.error(f"an error occurred while fetching DiscordUser for {member.display_name}", exc_info=error)

        return None

    # update quickly changing attributes
    dcUserDb.profile_picture_discord = member.display_avatar.url
    dcUserDb.username = member.display_name
    dcUserDb.discord_name = member.name

    return dcUserDb


# TODO dont use that in the future -> try to avoid
def getDiscordUserById(userId: int, session: Session) -> DiscordUser | None:
    getQuery = select(DiscordUser).where(DiscordUser.user_id == userId)

    try:
        dcUserDb = session.scalars(getQuery).one()
    except Exception as error:
        logger.error(f"couldn't fetch DiscordUser by ID: {userId}", exc_info=error)

        return None

    return dcUserDb
