import logging.handlers
import traceback

import discord
from discord.ext import tasks, commands

from src.Helper.EmailService import send_exception_mail
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Services import DatabaseRefreshService
from src.Services.RelationService import RelationService
from src.Services.ReminderService import ReminderService
from src.Services.UpdateTimeService import UpdateTimeService

logger = logging.getLogger("KVGG_BOT")

loggerTime = logging.getLogger("TIME")
fileHandler = logging.handlers.TimedRotatingFileHandler(filename='Logs/times.txt', when='midnight', backupCount=5)

fileHandler.setFormatter(CustomFormatterFile())
loggerTime.addHandler(fileHandler)
loggerTime.setLevel(logging.INFO)


class BackgroundServices(commands.Cog):
    def __init__(self, client: discord.Client):
        self.client = client

        self.refreshMembersInDatabase.start()
        logger.info("refreshMembersInDatabase started")

        self.minutely.start()
        logger.info("minutely-job started")

    @tasks.loop(seconds=60)
    async def minutely(self):
        logger.debug("running minutely-job")
        loggerTime.info("start")

        try:
            logger.debug("running updateTimesAndExperience")
            loggerTime.info("updateTimeService")

            uts = UpdateTimeService(self.client)

            await uts.updateTimesAndExperience()
        except ConnectionError as error:
            logger.error("failure to start UpdateTimeService", exc_info=error)

            send_exception_mail(traceback.format_exc())
        except Exception as e:
            logger.critical("encountered exception while executing updateTimeService", exc_info=e)

            send_exception_mail(traceback.format_exc())

        try:
            logger.debug("running callReminder")
            loggerTime.info("reminderService")

            rs = ReminderService(self.client)

            await rs.manageReminders()
        except ConnectionError as error:
            logger.error("failure to start ReminderService", exc_info=error)

            send_exception_mail(traceback.format_exc())
        except Exception as e:
            logger.critical("encountered exception while executing reminderService", exc_info=e)

            send_exception_mail(traceback.format_exc())

        try:
            logger.debug("running increaseRelations")
            loggerTime.info("relationService")

            rs = RelationService(self.client)

            await rs.increaseAllRelation()
        except ConnectionError as error:
            logger.error("failure to start RelationService", exc_info=error)

            send_exception_mail(traceback.format_exc())
        except Exception as e:
            logger.critical("encountered exception while executing relationService", exc_info=e)

            send_exception_mail(traceback.format_exc())

        try:
            logger.debug("running updateFelixCounter")
            loggerTime.info("updateFelixCounter")

            fc = FelixCounter()

            await fc.updateFelixCounter(self.client)
        except Exception as e:
            logger.critical("encountered exception while executing updateFelixCounter", exc_info=e)

            send_exception_mail(traceback.format_exc())

        loggerTime.info("end")

    @tasks.loop(hours=1)
    async def refreshMembersInDatabase(self):
        logger.debug("running refreshMembersInDatabase")

        dbr = DatabaseRefreshService.DatabaseRefreshService(self.client)

        await dbr.updateAllMembers()
