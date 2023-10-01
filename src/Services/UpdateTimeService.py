import logging
from datetime import datetime

from discord import Client, VoiceChannel

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.MuteParameter import MuteParameter
from src.Helper.GetChannelsFromCategory import getVoiceChannelsFromCategoryEnum
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.AchievementService import AchievementService
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService

logger = logging.getLogger("KVGG_BOT")


class UpdateTimeService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client: Client = client
        self.database = Database()

        self.whatsappChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, TrackedCategories)
        self.universityChannels: list[VoiceChannel] = getVoiceChannelsFromCategoryEnum(self.client, UniversityCategory)
        self.allowedChannels: list[VoiceChannel] = self.whatsappChannels + self.universityChannels

        self.experienceService = ExperienceService(self.client)
        self.achievementService = AchievementService(self.client)

    def __getChannels(self):
        """
        Yields all channels to track from the guild filtered by number of members and if they are tracked

        :return:
        """
        for channel in self.client.get_guild(GuildId.GUILD_KVGG.value).channels:
            if channel in self.allowedChannels and len(channel.members) > 0:
                yield channel

    def __eligibleForGettingTime(self, dcUserDbAndChannelType: tuple[dict, str], channel: VoiceChannel) -> bool:
        """
        Checks for the given user if he / she can receive online time (and XP)

        :param dcUserDbAndChannelType:
        :param channel:
        :return:
        """
        dcUserDb, channelType = dcUserDbAndChannelType

        # ignore all restrictions except for at least two members for uni counting
        if channelType == "uni" and len(channel.members) > 1:
            logger.debug("%s in university channel and not alone => ACCEPTED" % dcUserDb['username'])

            return True

        # if user is alone only look at full-mute
        if len(channel.members) == 1:
            # not full muted -> grant time
            if (fullMutedAt := dcUserDb['full_muted_at']) is None:
                logger.debug("%s not full-muted and alone => ACCEPTED" % dcUserDb['username'])

                return True

            # longer than allowed to be full muted
            if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
                logger.debug("%s too long full-muted and alone => DENIED" % dcUserDb['username'])

                return False

            # full-muted but in time
            logger.debug("%s not too long full-muted and alone => ACCEPTED" % dcUserDb['username'])

            return True

        mutedAt: datetime = dcUserDb['muted_at']
        fullMutedAt: datetime = dcUserDb['full_muted_at']

        # user is not (full-) muted
        if not mutedAt or not fullMutedAt:
            logger.debug("%s not (full-) muted and not alone => ACCEPTED" % dcUserDb['username'])

            return True

        # user is too long muted
        if (datetime.now() - mutedAt).seconds // 60 >= MuteParameter.MUTE_LIMIT.value:
            logger.debug("%s too long muted and not alone => DENIED" % dcUserDb['username'])

            return False

        # user is too long full muted
        if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
            logger.debug("%s too long full-muted and not alone => DENIED" % dcUserDb['username'])

            return False

        # user is within allowed times to be (full-) muted
        logger.debug("%s not too long (full-) muted and not alone => ACCEPTED" % dcUserDb['username'])

        return True

    async def updateTimesAndExperience(self):
        """
        Updates the time online, stream (if the member is streaming) and writes new formatted values

        :return:
        """
        for channel in self.__getChannels():
            # specify a type of channel for easier distinguishing later
            if channel in self.universityChannels:
                channelType = "uni"
            else:
                channelType = "gaming"

            for member in channel.members:
                if not (dcUserDb := getDiscordUser(member)):
                    logger.critical("couldn't fetch %s (%d) from database" % (member.name, member.id,))

                    continue

                # user cant get time -> continue with next user
                if not self.__eligibleForGettingTime((dcUserDb, channelType), channel):
                    continue

                # update commonly changing things
                dcUserDb['channel_id'] = channel.id
                dcUserDb['username'] = member.nick if member.nick else member.name
                dcUserDb['profile_picture_discord'] = member.display_avatar

                if channelType == "gaming":
                    # time_online can be None -> None-safe operation
                    if not dcUserDb['time_online']:
                        dcUserDb['time_online'] = 1
                    else:
                        dcUserDb['time_online'] = dcUserDb['time_online'] + 1

                    dcUserDb['formated_time'] = getFormattedTime(dcUserDb['time_online'])

                    # online time achievement
                    if (dcUserDb['time_online'] % (AchievementParameter.ONLINE_TIME_HOURS.value * 60)) == 0:
                        await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                                   AchievementParameter.ONLINE,
                                                                                   dcUserDb['time_online'])

                    logger.debug("%s gets XP for being online" % member.name)
                    await self.experienceService.addExperience(ExperienceParameter.XP_FOR_ONLINE.value, member=member)

                    # increase time for streaming
                    if member.voice.self_video or member.voice.self_stream:
                        # don't check for None here, default value is 0
                        dcUserDb['time_streamed'] = dcUserDb['time_streamed'] + 1
                        dcUserDb['formatted_stream_time'] = getFormattedTime(dcUserDb['time_streamed'])

                        if (dcUserDb['time_streamed'] % (AchievementParameter.STREAM_TIME_HOURS.value * 60)) == 0:
                            await self.achievementService.sendAchievementAndGrantBoost(member,
                                                                                       AchievementParameter.STREAM,
                                                                                       dcUserDb['time_streamed'])

                        logger.debug("%s gets XP for streaming" % member.name)
                        await self.experienceService.addExperience(ExperienceParameter.XP_FOR_STREAMING.value,
                                                                   member=member)

                    self.experienceService.reduceXpBoostsTime(member)
                else:
                    # university_time_online can be None -> None-safe operation
                    if not dcUserDb['university_time_online']:
                        dcUserDb['university_time_online'] = 1
                    else:
                        dcUserDb['university_time_online'] = dcUserDb['university_time_online'] + 1

                    dcUserDb['formated_university_time'] = getFormattedTime(dcUserDb['university_time_online'])

                query, nones = writeSaveQuery("discord", dcUserDb['id'], dcUserDb)

                if not self.database.runQueryOnDatabase(query, nones):
                    logger.critical("couldn't save changes to database")

                    continue
