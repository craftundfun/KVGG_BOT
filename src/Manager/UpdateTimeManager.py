import logging
from datetime import datetime

from discord import Client, VoiceChannel, Member
from sqlalchemy.orm import Session

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.MuteParameter import MuteParameter
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId
from src.Manager.AchievementManager import AchievementService
from src.Manager.StatisticManager import StatisticManager
from src.Services.ExperienceService import ExperienceService
from src.Services.QuestService import QuestService, QuestType

logger = logging.getLogger("KVGG_BOT")


class UpdateTimeService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client: Client = client

        self.whatsappChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
        self.universityChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
        self.allowedChannels: list[VoiceChannel] = self.whatsappChannels + self.universityChannels

        self.experienceService = ExperienceService(self.client)
        self.achievementService = AchievementService(self.client)
        self.questService = QuestService(self.client)
        self.statisticManager = StatisticManager(self.client)

    def _getChannels(self):
        """
        Yields all channels to track from the guild filtered by number of members and if they are tracked

        :return:
        """
        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).voice_channels:
            if channel in self.allowedChannels and len(channel.members) > 0:
                yield channel

    def _eligibleForGettingTime(self, dcUserDbAndChannelType: tuple[DiscordUser, str], channel: VoiceChannel) -> bool:
        """
        Checks for the given user if he / she can receive online time (and XP)

        :param dcUserDbAndChannelType:
        :param channel:
        :return:
        """
        dcUserDb, channelType = dcUserDbAndChannelType

        # ignore all restrictions except for at least two members for uni counting
        if channelType == "uni" and len(channel.members) > 1:
            logger.debug(f"{dcUserDb.username} in university channel and not alone => ACCEPTED")

            return True

        # if user is alone only look at full-mute
        if len(channel.members) == 1:
            # not full muted -> grant time
            if (fullMutedAt := dcUserDb.full_muted_at) is None:
                logger.debug(f"{dcUserDb.username} not full-muted and alone => ACCEPTED")

                return True

            # longer than allowed to be full muted
            if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
                logger.debug(f"{dcUserDb.username} too long full-muted and alone => DENIED")

                return False

            # full-muted but in time
            logger.debug(f"{dcUserDb.username} not too long full-muted and alone => ACCEPTED")

            return True

        mutedAt: datetime = dcUserDb.muted_at
        fullMutedAt: datetime = dcUserDb.full_muted_at

        # user is not (full-) muted
        if not mutedAt and not fullMutedAt:
            logger.debug(f"{dcUserDb.username} not (full-) muted and not alone => ACCEPTED")

            return True

        if mutedAt:
            # user is too long muted
            if (datetime.now() - mutedAt).seconds // 60 >= MuteParameter.MUTE_LIMIT.value:
                logger.debug(f"{dcUserDb.username} too long muted and not alone => DENIED")

                return False

        if fullMutedAt:
            # user is too long full muted
            if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
                logger.debug(f"{dcUserDb.username} too long full-muted and not alone => DENIED")

                return False

        # user is within allowed times to be (full-) muted
        logger.debug(f"{dcUserDb.username} not too long (full-) muted and not alone => ACCEPTED")

        return True

    async def updateTimesAndExperience(self, member: Member, dcUserDb: DiscordUser, session: Session):
        """
        Updates the time online, stream (if the member is streaming)

        :return:
        """
        if not member.voice:
            logger.debug(f"{member.display_name} has no voice status")

            return

        if (channel := member.voice.channel) in self.universityChannels:
            channelType = "uni"
        elif channel in self.whatsappChannels:
            channelType = "gaming"
        else:
            logger.debug(f"{member.display_name} is in a channel that is not tracked")

            return

        # user cant get time -> continue with next user
        if not self._eligibleForGettingTime((dcUserDb, channelType), channel):
            return

        if channelType == "gaming":
            dcUserDb.time_online += 1

            await self.questService.addProgressToQuest(member, QuestType.ONLINE_TIME)
            logger.debug(f"checked online-quest for {dcUserDb}")

            await self.experienceService.addExperience(ExperienceParameter.XP_FOR_ONLINE.value, member=member)
            logger.debug(f"increased online-xp for {dcUserDb}")

            self.statisticManager.increaseStatistic(StatisticsParameter.ONLINE, member, session)
            logger.debug(f"increased online statistics for {dcUserDb}")

            # increase time for streaming
            if member.voice.self_video or member.voice.self_stream:
                dcUserDb.time_streamed += 1

                await self.questService.addProgressToQuest(member, QuestType.STREAM_TIME)
                logger.debug(f"checked stream-quest for {dcUserDb}")

                await self.experienceService.addExperience(ExperienceParameter.XP_FOR_STREAMING.value,
                                                           member=member)
                logger.debug(f"increased stream-xp for {dcUserDb}")

                self.statisticManager.increaseStatistic(StatisticsParameter.STREAM, member, session)
                logger.debug(f"increased stream statistics for {dcUserDb}")

            self.experienceService.reduceXpBoostsTime(member)
            logger.debug(f"reduced xp boosts for {dcUserDb}")

            await self._checkForAchievements(member, dcUserDb)
            logger.debug(f"checked for achievements for {dcUserDb}")
        else:
            dcUserDb.university_time_online += 1

            self.statisticManager.increaseStatistic(StatisticsParameter.UNIVERSITY, member, session)
            logger.debug(f"increased university statistics for {dcUserDb}")

    async def _checkForAchievements(self, member: Member, dcUserDb: DiscordUser):
        """
        Maybe this will fix my achievement problem :(

        :param member: Member that is currently online to check achievements for
        :param dcUserDb: a belonging database object for the member
        """
        # online time achievement
        if (dcUserDb.time_online % (AchievementParameter.ONLINE_TIME_HOURS.value * 60)) == 0:
            logger.debug(f"{member.display_name} gets an online achievement")

            await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                       AchievementParameter.ONLINE,
                                                                       dcUserDb.time_online, )

        if member.voice.self_video or member.voice.self_stream:
            # stream time achievement
            if (dcUserDb.time_streamed % (AchievementParameter.STREAM_TIME_HOURS.value * 60)) == 0:
                logger.debug(f"{member.display_name} gets an stream achievement")

                await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                           AchievementParameter.STREAM,
                                                                           dcUserDb.time_streamed, )
