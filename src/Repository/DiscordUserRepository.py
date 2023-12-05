from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from discord import Member, User, Client

from src.DiscordParameters.QuestParameter import QuestDates
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getDiscordUser(member: Member, database: Database, client: Client | None = None) -> dict | None:
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
                                           (member.guild.id, member.id, username, datetime.now(), 0,)):
            logger.critical("couldn't create new discordUser entry in our database")

            return None

        query = "INSERT INTO notification_setting (discord_id) VALUES ((SELECT id FROM discord WHERE user_id = %s))"

        if not database.runQueryOnDatabase(query, (member.id,)):
            logger.critical(f"couldn't create notification settings for {member.name}")

        # fetch the newly added DiscordUser
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        dcUserDb = database.fetchOneResult(query, (member.id,))

        if not dcUserDb:
            logger.error("couldn't create DiscordUser!")

            return None

        logger.debug("new DiscordUser entry for %s" % username)

        if not client:
            logger.warning(f"cant create Quests for {member.display_name}: no client given")
        else:
            from src.Services.QuestService import QuestService

            questService = QuestService(client)

            loop = asyncio.get_event_loop()

            loop.run_until_complete(questService.createQuestForMember(member, QuestDates.DAILY, database))
            logger.debug("created daily-quests for new member")

            loop.run_until_complete(questService.createQuestForMember(member, QuestDates.WEEKLY, database))
            logger.debug("created weekly-quests for new member")

            loop.run_until_complete(questService.createQuestForMember(member, QuestDates.MONTHLY, database))
            logger.debug("created monthly-quests for new member")

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
