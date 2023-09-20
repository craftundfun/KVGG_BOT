import logging
from datetime import datetime

from discord import Message
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection

from src.Id.ChannelId import ChannelId
from src.Repository.DiscordUserRepository import getDiscordUser

logger = logging.getLogger("KVGG_BOT")


@DeprecationWarning
class LogHelper:
    """
    Saves the given Logs, usually called by commands, into the database
    """

    def __init__(self):
        self.databaseConnection = getDatabaseConnection()

    def addLog(self, message: Message):
        """
        Adds a log into the database

        :param message: Whole Message that triggered the logging
        :return:
        """
        logger.info("%s initiated saving a Log" % message.author.name)

        if not message.channel.id == ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value:
            return

        dcUserDb = getDiscordUser(self.databaseConnection, message.author)

        if not dcUserDb:
            logger.warning("Couldn't fetch DiscordUser!")

            return

        with self.databaseConnection.cursor() as cursor:
            query = "INSERT INTO logs (discord_user_id, command, created_at) " \
                    "VALUES (%s, %s, %s)"

            cursor.execute(query, (dcUserDb['id'], message.content, datetime.now(),))
            self.databaseConnection.commit()

    def __del__(self):
        self.databaseConnection.close()
