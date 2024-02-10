import asyncio
import datetime
import logging.handlers

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import tasks, commands

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Id.GuildId import GuildId
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Manager.AchievementManager import AchievementService
from src.Manager.MinutelyJobRunner import MinutelyJobRunner
from src.Manager.StatisticManager import StatisticManager
from src.Services.Database import Database
from src.Services.MemeService import MemeService
from src.Services.QuestService import QuestService

logger = logging.getLogger("KVGG_BOT")

loggerTime = logging.getLogger("TIME")
fileHandlerTime = logging.handlers.TimedRotatingFileHandler(filename='Logs/times.txt', when='midnight', backupCount=5)

loggerThread = logging.getLogger("THREAD")
fileHandlerThread = logging.handlers.TimedRotatingFileHandler(filename='Logs/thread.txt', when='midnight',
                                                              backupCount=5)

fileHandlerTime.setFormatter(CustomFormatterFile())
fileHandlerThread.setFormatter(CustomFormatterFile())

loggerTime.addHandler(fileHandlerTime)
loggerTime.setLevel(logging.INFO)

loggerThread.addHandler(fileHandlerThread)
loggerThread.setLevel(logging.INFO)

tz = datetime.datetime.now().astimezone().tzinfo
midnight = datetime.time(hour=0, minute=0, second=15, microsecond=0, tzinfo=tz)


class BackgroundServices(commands.Cog):
    def __init__(self, client: discord.Client):
        self.client = client

        self.achievementService = AchievementService(self.client)
        self.questService = QuestService(self.client)
        self.memeService = MemeService(self.client)
        self.minutelyJobRunner = MinutelyJobRunner(self.client)
        self.statisticManager = StatisticManager(self.client)

        self.minutely.start()
        logger.info("minutely-job started")

        self.refreshQuests.start()
        logger.info("refresh-quest-job started")

        self.chooseWinnerOfMemes.start()
        logger.info("choose-winner-job started")

        self.createStatistics.start()
        logger.info("createStatistics-job started")

    @tasks.loop(seconds=60)
    async def minutely(self):
        loggerTime.info("start")

        # double wrapped -> maybe look into it again in the future
        async def functionExecutor(function: callable):
            """
            Executes the given function safely
            """
            functionName = function.__name__

            try:
                logger.debug(f"running {functionName}")
                loggerTime.info(f"{functionName}")

                await function()
            except Exception as error:
                logger.error(f"encountered exception while executing {functionName}", exc_info=error)

        async def functionWrapper(function: callable):
            """
            Ensures that the given function will not run longer than wanted
            """
            functionName = function.__name__
            task = asyncio.create_task(
                functionExecutor(
                    function,
                )
            )

            try:
                await asyncio.wait_for(task, 50)
            except TimeoutError as error:
                logger.error(f"{functionName} took too long (longer than 50 seconds!)", exc_info=error)
            except Exception as error:
                logger.error(f"error while running {functionName}", exc_info=error)

        await functionWrapper(self.minutelyJobRunner.run)

        loggerTime.info("end")
        loggerThread.info("minutely task ended")

    @DeprecationWarning
    @tasks.loop(time=midnight)
    async def runAnniversary(self):
        """
        Iterates at midnight through all database members to check for their anniversary.
        """
        loggerTime.info("running runAnniversary")

        query = "SELECT user_id FROM discord"

        try:
            database = Database()
        except ConnectionError as error:
            logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

            return

        if not (users := database.fetchAllResults(query)):
            logger.error("couldn't fetch any users from the database")

            return

        guild = self.client.get_guild(GuildId.GUILD_KVGG.value)

        if not guild:
            logger.error("couldn't fetch guild")

            return

        for user in users:
            member = guild.get_member(int(user['user_id']))

            if not member:
                logger.warning(f"couldn't fetch member for id: {str(user['user_id'])}")

                continue

            if member.bot:
                continue

            if not member.joined_at:
                continue

            utcJoinedAt = member.joined_at
            joinedAt = utcJoinedAt.replace(tzinfo=tz)
            now = datetime.datetime.now().replace(tzinfo=tz)

            logger.debug(f"checking anniversary for: {member.display_name}")
            logger.debug(f"comparing dates - joined at: {joinedAt} vs now: {now}")

            if not (joinedAt.month == now.month and joinedAt.day == now.day):
                continue

            difference = relativedelta(now, joinedAt)
            years = difference.years + 1

            await self.achievementService.sendAchievementAndGrantBoost(member, AchievementParameter.ANNIVERSARY, years)

    @tasks.loop(time=midnight)
    async def refreshQuests(self):
        loggerTime.info("running refreshQuests")

        now = datetime.datetime.now().replace(tzinfo=tz)

        await self.questService.resetQuests(QuestDates.DAILY)
        logger.debug("reset daily quests")

        # if monday reset weekly's as well
        if now.weekday() == 0:
            await self.questService.resetQuests(QuestDates.WEEKLY)
            logger.debug("reset weekly quests")

        # if 1st of month reset monthly's
        if now.day == 1:
            await self.questService.resetQuests(QuestDates.MONTHLY)
            logger.debug("reset monthly quests")

    @tasks.loop(time=midnight)
    async def chooseWinnerOfMemes(self):
        if datetime.datetime.now().day != 1:
            logger.debug("not first of the month, dont choose winner for memes")

            return

        try:
            await self.memeService.chooseWinner()
        except Exception as error:
            logger.error("error while running chooseWinner", exc_info=error)

    @tasks.loop(time=midnight)
    async def createStatistics(self):
        """
        Creates statistics at the end of the week, month or year
        """
        now = datetime.datetime.now()

        if now.weekday() == 0:
            logger.debug("running weekly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.WEEKLY)
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.WEEKLY.value)
            except Exception as error:
                logger.error("couldn't run weekly statistics", exc_info=error)

        # 1st day of the month
        if now.day == 1:
            logger.debug("running monthly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.MONTHLY)
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.MONTHLY.value)
            except Exception as error:
                logger.error("couldn't run yearly statistics", exc_info=error)

        # 1st day of the year
        if now.month == 1 and now.day == 1:
            logger.debug("running yearly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.YEARLY)
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.YEARLY.value)
            except Exception as error:
                logger.error("couldn't run monthly statistics", exc_info=error)
