from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from discord import Member, User

from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")
basepath = Path(__file__).parent.parent.parent


def getDiscordUser(member: Member, database: Database) -> dict | None:
    """
    Returns the user from the database.
    If he doesn't exist yet, a new entry is created (only if a member was given)

    :param member: Member to retrieve all data from
    :param database:
    :return: None | Dict[Any, Any] DiscordUser
    """
    if member is None or isinstance(member, User):
        logger.debug("member was None or not the correct format")

        return None
    elif member.bot:
        logger.debug("member was a bot")

        return None

    query = "SELECT * " \
            "FROM discord " \
            "WHERE user_id = %s"

    dcUserDb = database.fetchOneResult(query, (member.id,))

    # user does not exist yet -> create new entry
    if not dcUserDb:
        logger.debug("creating new DiscordUser")

        query = "INSERT INTO discord (guild_id, user_id, username, created_at, time_streamed) " \
                "VALUES (%s, %s, %s, %s, %s)"
        username = member.nick if member.nick else member.name

        if not database.runQueryOnDatabase(query,
                                           (member.guild.id, member.id, username, datetime.now(), 0)):
            logger.critical("couldn't create new discordUser entry in our database")

            return None

        # fetch the newly added DiscordUser
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        dcUserDb = database.fetchOneResult(query, (member.id,))

        if not dcUserDb:
            logger.error("couldn't create DiscordUser!")

            return None
        else:
            logger.debug("new DiscordUser entry for %s" % username)

    # update quickly changing attributes
    dcUserDb['profile_picture_discord'] = member.display_avatar
    dcUserDb['username'] = member.display_name

    return dcUserDb


def getDiscordUserById(userId: int, database: Database) -> dict | None:
    """
    Returns a discord user from the database.
    Doesn't create one if missing or else.

    :param userId: Int - ID of the user
    :param database:
    :return: dict | None
    """
    query = "SELECT * FROM discord WHERE user_id = %s"
    dcUserDb = database.fetchOneResult(query, (userId,))

    if not dcUserDb:
        logger.debug("no DiscordUser was found")

        return None
    return dcUserDb
