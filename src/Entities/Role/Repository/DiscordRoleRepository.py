import logging

from discord import Role, Member
from sqlalchemy import select, insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Role.Entity.DiscordRole import DiscordRole
from src.Entities.Role.Entity.DiscordRoleMapping import DiscordRoleMapping

logger = logging.getLogger("KVGG_BOT")


def getDiscordRoleMapping(role: Role, member: Member, session: Session) -> DiscordRoleMapping | None:
    if not (discordRole := getDiscordRole(role, session)):
        logger.error(f"couldn't fetch DiscordRole for {role}")

        return None

    if not (dcUserDb := getDiscordUser(member, session)):
        logger.error(f"couldn't fetch DiscordUser for {member}")

        return None

    # noinspection PyTypeChecker
    getQuery = select(DiscordRoleMapping).where(DiscordRoleMapping.discord_id == dcUserDb.id,
                                                DiscordRoleMapping.role_id == discordRole.id, )

    try:
        discordRoleMapping = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"multiple results found for role mapping: {role} and {member}", exc_info=error)

        return None
    except NoResultFound:
        logger.debug(f"found no DiscordRoleMapping for {role} and {member}")

        insertQuery = insert(DiscordRoleMapping).values(discord_id=dcUserDb.id, role_id=discordRole.id)

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new role mapping for {role} and {member}", exc_info=error)
            session.rollback()

            return None
        else:
            logger.debug(f"created role mapping for {role} and {member}")

        try:
            discordRoleMapping = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted role mapping for {role} and {member}", exc_info=error)

            return None

    return discordRoleMapping


def getDiscordRole(role: Role, session: Session) -> DiscordRole | None:
    # noinspection PyTypeChecker
    getQuery = select(DiscordRole).where(DiscordRole.role_id == str(role.id))

    try:
        discordRole = session.scalars(getQuery).one()
    except MultipleResultsFound as error:
        logger.error(f"multiple results found for role: {role}", exc_info=error)

        return None
    except NoResultFound:
        logger.debug(f"did not found exact role match for {role}")

        insertQuery = insert(DiscordRole).values(role_id=str(role.id), name=role.name)

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new role with name: {role.name}", exc_info=error)
            session.rollback()

            return None
        else:
            logger.debug(f"created role: {role} in database")

        try:
            discordRole = session.scalars(getQuery).one()
        except Exception as error:
            logger.error(f"couldn't fetch newly inserted role with name: {role.name}", exc_info=error)

            return None
        else:
            logger.debug(f"fetched newly inserted role: {discordRole}")
    else:
        logger.debug(f"found role: {discordRole}")

    return discordRole
