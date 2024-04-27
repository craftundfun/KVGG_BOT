import asyncio
import datetime
import logging.handlers

import discord
from discord.ext import tasks, commands

from src.DiscordParameters.QuestParameter import QuestDates
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession
from src.Manager.MinutelyJobRunner import MinutelyJobRunner
from src.Manager.StatisticManager import StatisticManager
from src.Services.MemeService import MemeService
from src.Services.QuestService import QuestService

logger = logging.getLogger("KVGG_BOT")

loggerTime = logging.getLogger("TIME")
fileHandlerTime = logging.handlers.TimedRotatingFileHandler(filename='Logs/times.txt', when='midnight', backupCount=5)

loggerMinutelyJob = logging.getLogger("MINUTELY_JOB")
fileHandlerMinutelyJob = logging.handlers.TimedRotatingFileHandler(filename='Logs/minutelyJob.txt',
                                                                   when='midnight',
                                                                   backupCount=5, )

fileHandlerTime.setFormatter(CustomFormatterFile())
fileHandlerMinutelyJob.setFormatter(CustomFormatterFile())

loggerTime.addHandler(fileHandlerTime)
loggerTime.setLevel(logging.INFO)

loggerMinutelyJob.addHandler(fileHandlerMinutelyJob)
loggerMinutelyJob.setLevel(logging.DEBUG)

tz = datetime.datetime.now().astimezone().tzinfo
midnight = datetime.time(hour=0, minute=0, second=15, microsecond=0, tzinfo=tz)
minutelyErrorCount = 0


class BackgroundServices(commands.Cog):

    def __init__(self, client: discord.Client):
        self.client = client
        self.lastTimeMinutely = None

        self.achievementService = AchievementService(self.client)
        self.questService = QuestService(self.client)
        self.memeService = MemeService(self.client)
        self.minutelyJobRunner = MinutelyJobRunner(self.client)
        self.statisticManager = StatisticManager(self.client)

        self.minutely.start()
        logger.info("minutely-job started")

        self.refreshQuests.start()
        logger.info("refresh-quest-job started")

        self.chooseWinnerAndLoserOfMemes.start()
        logger.info("choose-winner-job started")

        self.createStatistics.start()
        logger.info("createStatistics-job started")

    @tasks.loop(seconds=60)
    async def minutely(self):
        global minutelyErrorCount

        # first execution
        if not self.lastTimeMinutely:
            loggerMinutelyJob.info("no last execution time for minutely job")
        # too many errors, abort minutely
        elif minutelyErrorCount >= 5:
            logger.warning(f"skipping minutely job")
            loggerMinutelyJob.error(f"skipping minutely job")

            return
        # too fast
        elif ((difference := (datetime.datetime.now() - self.lastTimeMinutely).total_seconds() * 1000000) <= 58000000
              or difference >= 62000000):
            minutelyErrorCount += 1

            if minutelyErrorCount == 5:
                logger.error("⚠️ CANCELLING MINUTELY JOB FROM NOW ON ⚠️")
                loggerMinutelyJob.error("STOPPING MINUTELY JOB")

                return
            else:
                logger.error(f"minutely job started too early or too late: difference between runs was {difference} "
                             f"microseconds, current errors: {minutelyErrorCount}")
                loggerMinutelyJob.error(f"minutely job started too early: waited only {difference} microseconds, "
                                        f"current errors: {minutelyErrorCount}")

        self.lastTimeMinutely = datetime.datetime.now()

        loggerMinutelyJob.info("execute")
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
    async def chooseWinnerAndLoserOfMemes(self):
        if datetime.datetime.now().day != 1:
            logger.debug("not first of the month, dont choose winner for memes")

            return

        try:
            await self.memeService.chooseWinnerAndLoser()
        except Exception as error:
            logger.error("error while running chooseWinner", exc_info=error)

    @tasks.loop(time=midnight)
    async def createStatistics(self):
        """
        Creates statistics at the end of the week, month or year
        """
        now = datetime.datetime.now()

        if not (session := getSession()):
            return

        logger.debug("running daily statistics")

        try:
            self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.DAILY, session)
        except Exception as error:
            logger.error("couldn't save daily statistics", exc_info=error)

        if now.weekday() == 0:
            logger.debug("running weekly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.WEEKLY, session)
            except Exception as error:
                logger.error("couldn't run weekly statistics", exc_info=error)

            try:
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.WEEKLY, session)
            except Exception as error:
                logger.error("couldn't save weekly statistics", exc_info=error)

        # 1st day of the month
        if now.day == 1:
            logger.debug("running monthly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.MONTHLY, session)
            except Exception as error:
                logger.error("couldn't run weekly statistics", exc_info=error)

            try:
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.MONTHLY, session)
            except Exception as error:
                logger.error("couldn't save weekly statistics", exc_info=error)

        # 1st day of the year
        if now.month == 1 and now.day == 1:
            logger.debug("running yearly statistics")

            try:
                await self.statisticManager.runRetrospectForUsers(StatisticsParameter.YEARLY, session)
            except Exception as error:
                logger.error("couldn't run weekly statistics", exc_info=error)

            try:
                self.statisticManager.saveStatisticsToStatisticLog(StatisticsParameter.YEARLY, session)
            except Exception as error:
                logger.error("couldn't save weekly statistics", exc_info=error)
