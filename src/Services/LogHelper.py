from datetime import datetime

from discord import Message
from mysql.connector import MySQLConnection
from src.Id.ChannelId import ChannelId
from src.Repository.DiscordUserRepository import getDiscordUser


class LogHelper:

    def __init__(self, databaseConnection: MySQLConnection):
        self.databaseConnection = databaseConnection

    def addLog(self, message: Message):
        if not message.channel.id == int(ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value):
            return

        dcUserDb = getDiscordUser(self.databaseConnection, message.author)

        if not dcUserDb:
            return

        with self.databaseConnection.cursor() as cursor:
            query = "INSERT INTO logs (discord_user_id, command, created_at) " \
                    "VALUES (%s, %s, %s)"

            cursor.execute(query, (dcUserDb['id'], message.content, datetime.now(),))
            self.databaseConnection.commit()
