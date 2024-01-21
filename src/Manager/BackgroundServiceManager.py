import asyncio
import datetime
import logging.handlers
import threading
from asyncio import AbstractEventLoop

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import tasks, commands

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Id.DiscordUserId import DiscordUserId
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseRefreshManager import DatabaseRefreshService
from src.Manager.StatisticManager import StatisticManager
from src.Manager.UpdateTimeManager import UpdateTimeService
from src.Services.Database import Database
from src.Services.MemeService import MemeService
from src.Services.QuestService import QuestService
from src.Services.RelationService import RelationService
from src.Services.ReminderService import ReminderService

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
twentyThree = datetime.time(hour=23, minute=0, second=0, microsecond=0, tzinfo=tz)


class BackgroundServices(commands.Cog):
    thread: threading.Thread | None = None

    def __init__(self, client: discord.Client):
        self.client = client

        self.refreshMembersInDatabase.start()
        logger.info("refreshMembersInDatabase started")

        self.minutely.start()
        logger.info("minutely-job started")

        self.runAnniversary.start()
        logger.info("anniversary-job started")

        self.refreshQuests.start()
        logger.info("refresh-quest-job started")

        self.chooseWinnerOfMemes.start()
        logger.info("choose-winner-job started")

        self.informAboutUnfinishedQuests.start()
        logger.info("unfinished-quests-job started")

        self.createStatistics.start()
        logger.info("createStatistics-job started")

    @tasks.loop(seconds=60)
    async def minutely(self):
        if self.thread is None:
            loggerThread.info("no thread was previously active")
        elif self.thread.is_alive():
            # info for the file - don't spam us with emails, normal logger will take care
            loggerThread.info("Thread is still alive after one minute!")
            logger.error("Thread is still alive after one minute!")

            # so I will notice immediately
            await self.client.get_user(DiscordUserId.BJARNE.value).send("there was a problem with the thread")

        def minutelyJobs(loop: AbstractEventLoop):
            logger.debug("running minutely-job")
            loggerTime.info("start")

            try:
                logger.debug("running updateTimesAndExperience")
                loggerTime.info("updateTimeService")

                uts = UpdateTimeService(self.client)

                asyncio.run_coroutine_threadsafe(uts.updateTimesAndExperience(), loop)
            except ConnectionError as error:
                logger.error("failure to start UpdateTimeService", exc_info=error)
            except Exception as e:
                logger.error("encountered exception while executing updateTimeService", exc_info=e)

            try:
                logger.debug("running callReminder")
                loggerTime.info("reminderService")

                rs = ReminderService(self.client)

                asyncio.run_coroutine_threadsafe(rs.manageReminders(), loop)
            except ConnectionError as error:
                logger.error("failure to start ReminderService", exc_info=error)
            except Exception as e:
                logger.error("encountered exception while executing reminderService", exc_info=e)

            try:
                logger.debug("running increaseRelations")
                loggerTime.info("relationService")

                rs = RelationService(self.client)

                asyncio.run_coroutine_threadsafe(rs.increaseAllRelation(), loop)
            except ConnectionError as error:
                logger.error("failure to start RelationService", exc_info=error)
            except Exception as e:
                logger.error("encountered exception while executing relationService", exc_info=e)

            try:
                logger.debug("running updateFelixCounter")
                loggerTime.info("updateFelixCounter")

                fc = FelixCounter()

                asyncio.run_coroutine_threadsafe(fc.updateFelixCounter(self.client), loop)
            except Exception as e:
                logger.error("encountered exception while executing updateFelixCounter", exc_info=e)

            loggerTime.info("end")
            loggerThread.info("minutely thread ended")

        self.thread = threading.Thread(target=minutelyJobs, args=(asyncio.get_event_loop(),))

        loggerThread.info("minutely thread started")
        self.thread.start()

    @tasks.loop(hours=1)
    async def refreshMembersInDatabase(self):
        logger.debug("running refreshMembersInDatabase")

        dbr = DatabaseRefreshService(self.client)

        await dbr.updateAllMembers()

    @tasks.loop(time=midnight)
    async def runAnniversary(self):
        """
        Iterates at midnight through all database members to check for their anniversary.
        """
        loggerTime.info("running runAnniversary")

        query = "SELECT user_id FROM discord"

        try:
            database = Database()
            achievementService = AchievementService(self.client)
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

            await achievementService.sendAchievementAndGrantBoost(member, AchievementParameter.ANNIVERSARY, years)

    @tasks.loop(time=midnight)
    async def refreshQuests(self):
        loggerTime.info("running refreshQuests")

        now = datetime.datetime.now().replace(tzinfo=tz)

        try:
            questService = QuestService(self.client)
        except ConnectionError as error:
            logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

            return

        await questService.resetQuests(QuestDates.DAILY)
        logger.debug("reset daily quests")

        # if monday reset weekly's as well
        if now.weekday() == 0:
            await questService.resetQuests(QuestDates.WEEKLY)
            logger.debug("reset weekly quests")

        # if 1st of month reset monthly's
        if now.day == 1:
            await questService.resetQuests(QuestDates.MONTHLY)
            logger.debug("reset monthly quests")

    @tasks.loop(time=midnight)
    async def chooseWinnerOfMemes(self):
        if datetime.datetime.now().day != 1:
            logger.debug("not first of the month, dont choose winner for memes")

            return

        try:
            meme = MemeService(self.client)
        except ConnectionError as error:
            logger.error("couldn't connect to MySQL, aborting task", exc_info=error)
        else:
            await meme.chooseWinner()

    @tasks.loop(time=midnight)
    async def createStatistics(self):
        """
        Creates statistics at the end of the week, month or year
        """
        now = datetime.datetime.now()
        query = ("SELECT * "
                 "FROM current_discord_statistic "
                 "WHERE statistic_time = %s")
        database = Database()
        statisticManager = StatisticManager(self.client)

        def getUsers(type: str) -> list[dict] | None:
            if not (users := database.fetchAllResults(query, (type,))):
                logger.error(f"couldn't fetch all statistics for {type}")

                return None

            return users

        if now.weekday() == 0:
            logger.debug("running weekly statistics")

            try:
                await statisticManager.runRetrospectForUsers(StatisticsParameter.WEEKLY)
                statisticManager.saveStatisticsToStatisticLog(getUsers(StatisticsParameter.WEEKLY.value))
            except Exception as error:
                logger.error("couldn't run weekly statistics", exc_info=error)

        # 1st day of the month
        if now.day == 1:
            logger.debug("running monthly statistics")

            try:
                await statisticManager.runRetrospectForUsers(StatisticsParameter.MONTHLY)
                statisticManager.saveStatisticsToStatisticLog(getUsers(StatisticsParameter.MONTHLY.value))
            except Exception as error:
                logger.error("couldn't run yearly statistics", exc_info=error)

        # 1st day of the year
        if now.month == 1 and now.day == 1:
            logger.debug("running yearly statistics")

            try:
                await statisticManager.runRetrospectForUsers(StatisticsParameter.YEARLY)
                statisticManager.saveStatisticsToStatisticLog(getUsers(StatisticsParameter.YEARLY.value))
            except Exception as error:
                logger.error("couldn't run monthly statistics", exc_info=error)

    @tasks.loop(time=twentyThree)
    async def informAboutUnfinishedQuests(self):
        questService = QuestService(self.client)

        await questService.remindToFulFillQuests(QuestDates.DAILY)

        logger.debug("ran daily quests reminder")
