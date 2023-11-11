import datetime
import logging.handlers

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import tasks, commands

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.QuestParameter import QuestDates
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Services import DatabaseRefreshService
from src.Services.AchievementService import AchievementService
from src.Services.Database import Database
from src.Services.QuestService import QuestService
from src.Services.RelationService import RelationService
from src.Services.ReminderService import ReminderService
from src.Services.UpdateTimeService import UpdateTimeService

logger = logging.getLogger("KVGG_BOT")

loggerTime = logging.getLogger("TIME")
fileHandler = logging.handlers.TimedRotatingFileHandler(filename='Logs/times.txt', when='midnight', backupCount=5)

fileHandler.setFormatter(CustomFormatterFile())
loggerTime.addHandler(fileHandler)
loggerTime.setLevel(logging.INFO)

tz = datetime.datetime.now().astimezone().tzinfo
midnight = datetime.time(hour=0, minute=0, second=15, microsecond=0, tzinfo=tz)


class BackgroundServices(commands.Cog):
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
        except Exception as e:
            logger.error("encountered exception while executing updateTimeService", exc_info=e)

        try:
            logger.debug("running callReminder")
            loggerTime.info("reminderService")

            rs = ReminderService(self.client)

            await rs.manageReminders()
        except ConnectionError as error:
            logger.error("failure to start ReminderService", exc_info=error)
        except Exception as e:
            logger.error("encountered exception while executing reminderService", exc_info=e)

        try:
            logger.debug("running increaseRelations")
            loggerTime.info("relationService")

            rs = RelationService(self.client)

            await rs.increaseAllRelation()
        except ConnectionError as error:
            logger.error("failure to start RelationService", exc_info=error)
        except Exception as e:
            logger.error("encountered exception while executing relationService", exc_info=e)

        try:
            logger.debug("running updateFelixCounter")
            loggerTime.info("updateFelixCounter")

            fc = FelixCounter()

            await fc.updateFelixCounter(self.client)
        except Exception as e:
            logger.error("encountered exception while executing updateFelixCounter", exc_info=e)

        loggerTime.info("end")

    @tasks.loop(hours=1)
    async def refreshMembersInDatabase(self):
        logger.debug("running refreshMembersInDatabase")

        dbr = DatabaseRefreshService.DatabaseRefreshService(self.client)

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

            logger.debug(f"checking anniversary for: {member.nick if member.nick else member.name}")
            logger.debug(f"comparing dates - joined at: {joinedAt} vs now: {now}")

            if not (joinedAt.month == now.month and joinedAt.day == now.day):
                continue

            difference = relativedelta(now, joinedAt)
            years = difference.years

            if years == 0:
                continue

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
