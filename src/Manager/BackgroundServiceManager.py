import asyncio
import datetime
import logging.handlers

import discord
from discord.ext import tasks, commands

from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Manager.AchievementManager import AchievementService
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
midnightTime = datetime.time(hour=9, minute=9, second=15, microsecond=0, tzinfo=tz)
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

        # self.minutely.start()
        logger.info("minutely-job started")

        self.midnight.start()
        logger.info("midnight-job started")

    @tasks.loop(time=midnightTime)
    async def midnight(self):
        try:
            await self.memeService.midnightJob()
        except Exception as error:
            logger.error("error while running midnight job of MemeService", exc_info=error)

        try:
            await self.questService.midnightJob()
        except Exception as error:
            logger.error("error while running midnight job of QuestService", exc_info=error)

        try:
            await self.statisticManager.midnightJob()
        except Exception as error:
            logger.error("error while running midnight job of StatisticManager", exc_info=error)

        logger.debug("finished midnight jobs")

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
        # too fast or too slow
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
