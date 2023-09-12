import logging
from datetime import datetime

from discord import Client, VoiceChannel

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.MuteParameter import MuteParameter
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelIdUniversityTracking import ChannelIdUniversityTracking
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.AchievementService import checkForAchievement
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

        self.uniChannels: set = ChannelIdUniversityTracking.getValues()
        self.whatsappChannels: set = ChannelIdWhatsAppAndTracking.getValues()
        self.allowedChannels: set = self.uniChannels | self.whatsappChannels

        self.experienceService = ExperienceService(self.client)
        # TODO ^^

    def __getChannels(self):
        """
        Yields all channels to track from the guild filtered by number of members and if they are tracked

        :return:
        """
        for channel in self.client.get_guild(int(GuildId.GUILD_KVGG.value)).channels:
            if str(channel.id) in self.allowedChannels and len(channel.members) > 0:
                yield channel

    def __eligibleForGettingTime(self, dcUserDbAndChannelType: tuple[dict, str], channel: VoiceChannel) -> bool:
        """
        Checks for the given user if he / she can receive online time (and XP)

        :param dcUserDbAndChannelType:
        :param channel:
        :return:
        """
        # ignore all restrictions except for at least two members for uni counting
        if dcUserDbAndChannelType[1] == "uni" and len(channel.members) > 1:
            return True

        # if user is alone only look at full-mute
        if len(channel.members) == 1:
            # not full muted -> grant time
            if (fullMutedAt := dcUserDbAndChannelType[0]['full_muted_at']) is None:
                return True

            # longer than allowed to be full muted
            if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
                return False

            # full-muted but in time
            return True

        mutedAt: datetime = dcUserDbAndChannelType[0]['muted_at']
        fullMutedAt: datetime = dcUserDbAndChannelType[0]['full_muted_at']

        # user is not (full-) muted
        if not mutedAt or not fullMutedAt:
            return True

        # user is too long muted
        if (datetime.now() - mutedAt).seconds // 60 >= MuteParameter.MUTE_LIMIT.value:
            return False

        # user is too long full muted
        if (datetime.now() - fullMutedAt).seconds // 60 >= MuteParameter.FULL_MUTE_LIMIT.value:
            return False

        # user is within allowed times to be (full-) muted
        return True

    async def updateTimesAndExperience(self):
        """
        Updates the time online, stream (if the member is streaming) and writes new formatted values

        :return:
        """
        for channel in self.__getChannels():
            # specify a type of channel for easier distinguishing later
            if str(channel.id) in self.uniChannels:
                channelType = "uni"
            else:
                channelType = "gaming"

            for member in channel.members:
                if not (dcUserDb := getDiscordUser(member)):
                    logger.critical("couldn't fetch %s (%d) from database" % (member.name, member.id))

                    continue

                # user cant get time -> continue with next user
                if not self.__eligibleForGettingTime((dcUserDb, channelType), channel):
                    continue

                if channelType == "gaming":
                    # time_online can be None -> None-safe operation
                    if not dcUserDb['time_online']:
                        dcUserDb['time_online'] = 1
                    else:
                        dcUserDb['time_online'] = dcUserDb['time_online'] + 1

                    dcUserDb['formated_time'] = getFormattedTime(dcUserDb['time_online'])

                    # online time achievement
                    await checkForAchievement(AchievementParameter.ONLINE, dcUserDb['time_online'], self.client, member)
                    # add xp and achievement
                    await self.experienceService.addExperience(ExperienceParameter.XP_FOR_ONLINE.value, member=member)

                    # increase time for streaming
                    if member.voice.self_video or member.voice.self_stream:
                        # don't check for None here, default value is 0
                        dcUserDb['time_streamed'] = dcUserDb['time_streamed'] + 1
                        dcUserDb['formatted_stream_time'] = getFormattedTime(dcUserDb['time_streamed'])

                        # stream time achievement
                        await checkForAchievement(AchievementParameter.STREAM,
                                                  dcUserDb['time_streamed'],
                                                  self.client,
                                                  member)
                        # add xp and achievement
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
