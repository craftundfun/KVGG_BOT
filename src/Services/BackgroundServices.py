import logging
import traceback

import discord
from discord.ext import tasks, commands

from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Services import DatabaseRefreshService
from src.Helper.EmailService import send_exception_mail
from src.Services.RelationService import RelationService
from src.Services.ReminderService import ReminderService
from src.Services.UpdateTimeService import UpdateTimeService

logger = logging.getLogger("KVGG_BOT")


class BackgroundServices(commands.Cog):
    def __init__(self, client: discord.Client):
        self.client = client

        self.refreshDatabaseWithDiscord.start()
        logger.info("refreshDatabaseWithDiscord started")

        self.refreshMembersInDatabase.start()
        logger.info("refreshMembersInDatabase started")

        self.minutely.start()
        logger.info("minutely-job started")

    @tasks.loop(seconds=60)
    async def minutely(self):
        logger.debug("running minutely-job")

        try:
            logger.debug("running updateTimesAndExperience")

            uts = UpdateTimeService(self.client)

            await uts.updateTimesAndExperience()
        except ConnectionError as error:
            logger.error("failure to start UpdateTimeService", exc_info=error)
        except Exception as e:
            logger.critical("encountered exception while executing updateTimeService", exc_info=e)

            send_exception_mail(traceback.format_exc())

        try:
            logger.debug("running callReminder")

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

            fc = FelixCounter()

            await fc.updateFelixCounter(self.client)
        except Exception as e:
            logger.critical("encountered exception while executing updateFelixCounter", exc_info=e)

            send_exception_mail(traceback.format_exc())

    @tasks.loop(minutes=30)
    async def refreshDatabaseWithDiscord(self):
        logger.debug("running refreshDatabaseWithDiscord")

        dbr = DatabaseRefreshService.DatabaseRefreshService(self.client)

        await dbr.updateDatabaseToServerState()

    @tasks.loop(hours=24)
    async def refreshMembersInDatabase(self):
        logger.debug("running refreshMembersInDatabase")

        dbr = DatabaseRefreshService.DatabaseRefreshService(self.client)

        await dbr.updateAllMembers()
