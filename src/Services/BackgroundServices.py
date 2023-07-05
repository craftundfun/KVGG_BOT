import logging

import discord
from discord.ext import tasks, commands
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Id.ChannelId import ChannelId
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Services.ProcessUserInput import getTagStringFromId

logger = logging.getLogger("KVGG_BOT")


class BackgroundServices(commands.Cog):
    def __init__(self, client: discord.Client):
        self.client = client

        self.onlineTimeAchievement.start()
        logger.info("onlineTimeAchievement started")
        self.streamTimeAchievement.start()
        logger.info("streamTimeAchievement started")
        self.xpAchievement.start()
        logger.info("xpAchievement started")

    def cog_unload(self) -> None:
        """
        Cancels all running tasks

        :return:
        """
        self.onlineTimeAchievement.cancel()
        self.streamTimeAchievement.cancel()
        self.xpAchievement.cancel()

    async def cog_load(self):
        self.onlineTimeAchievement.start()
        self.streamTimeAchievement.start()
        self.xpAchievement.start()

    @tasks.loop(seconds=60)
    async def onlineTimeAchievement(self):
        logger.info("Running onlineTimeAchievement")

        try:
            databaseConnection = getDatabaseConnection()
        except TypeError:
            logger.critical("Couldn't fetch database connection! Aborting task.")

            return

        with databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM discord " \
                    "WHERE channel_id IS NOT NULL and time_online IS NOT NULL and MOD(time_online, %s) = 0"

            cursor.execute(query, (AchievementParameter.ONLINE_TIME_HOURS.value * 60,))

            data = cursor.fetchall()

            if not data:
                return

            users = [dict(zip(cursor.column_names, date)) for date in data]

        channel = self.client.get_channel(int(ChannelId.CHANNEL_ACHIEVEMENTS.value))

        if not channel:
            logger.critical("Achievement-Channel not found!")

            return

        for user in users:
            if str(user['channel_id']) not in ChannelIdWhatsAppAndTracking.getValues():
                continue

            tag = getTagStringFromId(user['user_id'])
            hours = int(user['time_online'] / 60)

            await channel.send(str(tag) + ", du bist nun schon " + str(hours) + " Stunden online gewesen. Weiter so "
                                                                                ":cookie:")

    @tasks.loop(seconds=60)
    async def streamTimeAchievement(self):
        logger.info("Running streamTimeAchievement")

        try:
            databaseConnection = getDatabaseConnection()
        except TypeError:
            logger.critical("Couldn't fetch database connection! Aborting task.")

            return

        with databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM discord " \
                    "WHERE channel_id IS NOT NULL and time_streamed > 0 and MOD(time_streamed, %s) = 0"

            cursor.execute(query, (AchievementParameter.STREAM_TIME_HOURS.value * 60,))

            data = cursor.fetchall()

            if not data:
                return

            users = [dict(zip(cursor.column_names, date)) for date in data]

        channel = self.client.get_channel(int(ChannelId.CHANNEL_ACHIEVEMENTS.value))

        if not channel:
            logger.critical("Achievement-Channel not found!")

            return

        for user in users:
            if str(user['channel_id']) not in ChannelIdWhatsAppAndTracking.getValues():
                continue

            tag = getTagStringFromId(user['user_id'])
            hours = int(user['time_streamed'] / 60)

            await channel.send(str(tag) + ", du hast nun schon " + str(hours) + " Stunden gestreamt. Weiter so "
                                                                                ":cookie:")

    @tasks.loop(seconds=60)
    async def xpAchievement(self):
        logger.info("Running xpAchievement")

        try:
            databaseConnection = getDatabaseConnection()
        except TypeError:
            logger.critical("Couldn't fetch database connection! Aborting task.")

            return

        with databaseConnection.cursor() as cursor:
            query = "SELECT e.xp_amount, d.user_id " \
                    "FROM experience e " \
                    "INNER JOIN discord d on e.discord_user_id = d.id " \
                    "WHERE d.channel_id IS NOT NULL and e.xp_amount > 0 and MOD(e.xp_amount, %s) = 0"

            cursor.execute(query, (AchievementParameter.XP_AMOUNT.value,))

            data = cursor.fetchall()

            if not data:
                return

            users = [dict(zip(cursor.column_names, date)) for date in data]

        channel = self.client.get_channel(int(ChannelId.CHANNEL_ACHIEVEMENTS.value))

        if not channel:
            logger.critical("Achievement-Channel not found!")

            return

        for user in users:
            if str(user['channel_id']) not in ChannelIdWhatsAppAndTracking.getValues():
                continue

            tag = getTagStringFromId(user['user_id'])
            xp = user['xp_amount']

            await channel.send(str(tag) + ", du hast bereits " + str(xp) + " XP gefarmt. Weiter so "
                                                                           ":cookie:")
