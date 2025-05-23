import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from discord import Client, Member
from sqlalchemy import null

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Manager.AchievementManager import AchievementService
from src.Manager.DatabaseManager import getSession
from src.Manager.UpdateTimeManager import UpdateTimeService
from src.Services.ExperienceService import ExperienceService
from src.Services.GameDiscordService import GameDiscordService
from src.Services.RelationService import RelationService
from src.Services.ReminderService import ReminderService

logger = logging.getLogger("KVGG_BOT")
tz = datetime.now().astimezone().tzinfo


class MinutelyJobRunner:

    def __init__(self, client: Client):
        self.client = client

        self.updateTimeManager = UpdateTimeService(self.client)
        self.gameDiscordService = GameDiscordService(self.client)
        self.felixCounter = FelixCounter(self.client)
        self.reminderService = ReminderService(self.client)
        self.relationService = RelationService(self.client)
        self.achievementService = AchievementService(self.client)
        self.experienceService = ExperienceService(self.client)

    async def run(self):
        if not (session := getSession()):
            logger.error("couldn't fetch session for minutelyJob")

            return

        for member in self.client.get_all_members():
            if not (dcUserDb := getDiscordUser(member, session)):
                logger.warning(f"couldn't fetch DiscordUser for {member.display_name} from the database")

                continue

            try:
                # updating time and experience
                await self.updateTimeManager.updateTimesAndExperience(member, dcUserDb, session)

                # updating game statistics
                await self.gameDiscordService.increaseGameRelationsForMember(member, session)

                # updating Felix.Counter
                await self.felixCounter.updateFelixCounter(member, dcUserDb, session)

                # update things
                dcUserDb.username = member.display_name
                dcUserDb.profile_picture_discord = member.display_avatar.url
                dcUserDb.channel_id = member.voice.channel.id if member.voice else null()

                if (now := datetime.now()).hour == 0 and now.minute == 0:
                    logger.debug("running anniversary check")

                    await self._runAnniversaryCheck(member)
            except Exception as error:
                logger.error(f"error occurred while running the minutely job for {member.display_name}", exc_info=error)
            finally:
                try:
                    session.commit()
                except Exception as error:
                    logger.error(f"couldn't save DiscordUser for {member.display_name}", exc_info=error)
                    session.rollback()

        session.close()

        # increase all relations
        await self.relationService.increaseAllRelations()
        logger.debug("increased relations")

        # check reminder
        await self.reminderService.manageReminders()
        logger.debug("ran reminder update")

        # check xp-spin reminder
        await self.experienceService.runExperienceReminder()
        logger.debug("ran xp-spin reminder")

    async def _runAnniversaryCheck(self, member: Member):
        """
        Checks if the given member has "birthday"

        :param member: Member to check
        """
        utcJoinedAt = member.joined_at
        joinedAt = utcJoinedAt.replace(tzinfo=tz)
        now = datetime.now().replace(tzinfo=tz)

        logger.debug(f"checking anniversary for: {member.display_name}")
        logger.debug(f"comparing dates - joined at: {joinedAt} vs now: {now}")

        if not (joinedAt.month == now.month and joinedAt.day == now.day):
            return

        difference = relativedelta(now, joinedAt)
        years = difference.years + 1

        await self.achievementService.sendAchievementAndGrantBoost(member, AchievementParameter.ANNIVERSARY, years)
