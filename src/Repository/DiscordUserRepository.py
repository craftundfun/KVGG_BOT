from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Dict, Any
from discord import Message, Member, User
from mysql.connector import MySQLConnection

from src.Helper.Database import Database

logger = logging.getLogger("KVGG_BOT")


@DeprecationWarning
def __createDiscordUser(message: Message) -> None | dict:
    """
    Returns a new DiscordUser Dict with the information given by the message

    :param message:
    :return:
    """
    if message.author.bot:
        return None

    if username := not message.author.nick:
        username = message.author.name

    return {
        'guild_id': message.guild.id,
        'user_id': message.author.id,
        'username': username,
        'created_at': datetime.now().date(),
        'time_streamed': 0
    }


def getDiscordUser(member: Member) -> dict | None:
    """
    Returns the user from the database.
    If he doesn't exist yet, a new entry is created (only if a member was given)

    :param member: Member to retrieve all data from
    :return: None | Dict[Any, Any] DiscordUser
    """
    logger.debug("trying to get DiscordUser from database")

    try:
        database = Database()
    except ConnectionError as error:
        logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

        return None

    if member is None or isinstance(member, User):
        logger.debug("member was None or not the correct format")

        return None
    elif member.bot:
        logger.debug("member was a bot")

        return None

    query = "SELECT * " \
            "FROM discord " \
            "WHERE user_id = %s"

    dcUserDb = database.queryOneResult(query, (member.id,))

    # user does not exist yet -> create new entry
    if not dcUserDb:
        logger.debug("creating new DiscordUser")

        query = "INSERT INTO discord (guild_id, user_id, username, created_at, time_streamed) " \
                "VALUES (%s, %s, %s, %s, %s)"
        username = member.nick if member.nick else member.name

        if not database.saveChangesToDatabase(query,
                                              (member.guild.id, member.id, username, datetime.now(), 0,)):
            return None

        # fetch the newly added DiscordUser
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        dcUserDb = database.queryOneResult(query, (member.id,))

        if not dcUserDb:
            logger.error("couldn't create DiscordUser!")

            return None
        else:
            logger.debug("new DiscordUser entry for %s" % username)

    # update quickly changing attributes
    dcUserDb['profile_picture_discord'] = member.display_avatar
    dcUserDb['username'] = member.nick if member.nick else member.name

    return dcUserDb


def getDiscordUserById(userId: int) -> dict | None:
    """
    Returns a discord user from the database.
    Doesn't create one if missing or else.

    :param userId: int - Id of the user
    :return: dict | None
    """
    try:
        database = Database()
    except ConnectionError as error:
        logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

        return None

    query = "SELECT * FROM discord WHERE user_id = %s"
    dcUserDb = database.queryOneResult(query, (userId,))

    if not dcUserDb:
        logger.debug("no DiscordUser was found")

        return None
    return dcUserDb


def getOnlineUsers() -> List[Dict[Any, Any]] | None:
    """
    Retrieves all current users that are online (according to our database)

    :return: None | List[Dict[Any, Any]] List of all DiscordUsers
    """
    try:
        database = Database()
    except ConnectionError as error:
        logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

        return None

    query = "SELECT * " \
            "FROM discord " \
            "WHERE channel_id IS NOT NULL"

    return database.queryAllResults(query)
