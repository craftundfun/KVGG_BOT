import logging

from discord import Client, Member

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Id.ChannelId import ChannelId
from src.DiscordParameters.AchievementParameter import AchievementParameter

logger = logging.getLogger("KVGG_BOT")


class AchievementService:

    def __init__(self, client: Client):
        self.client = client
        self.channel = self.client.get_channel(int(ChannelId.CHANNEL_ACHIEVEMENTS.value))
        self.databaseConnection = getDatabaseConnection()

    async def sendAchievement(self, member: Member, kind: AchievementParameter, value: int):
        """
        Sends the achievement message into our achievement channel and grants the corresponding xp boost

        :param member: Member, who reached the achievement and to be tagged
        :param kind: ONLINE, STREAM or XP
        :param value: Value of the achievement, for example 300 minutes online -> will be calculated into hours
        :return:
        """
        # import here to avoid circular import
        from src.Services.ProcessUserInput import getTagStringFromId
        from src.Services.ExperienceService import ExperienceService

        if type(kind.value) != str:
            logger.critical("false argument type")

            return
        elif not self.channel:
            logger.critical("cant reach channel")

            return

        tag = getTagStringFromId(str(member.id))
        hours = int(value / 60)

        try:
            xpService = ExperienceService(self.client)
        except ConnectionError as error:
            logger.error("failure to start ExperienceService", exc_info=error)

            return

        if kind == AchievementParameter.ONLINE:
            message = tag + ", du bist nun schon " + str(hours) + (" Stunden online gewesen. Weiter so :cookie:"
                                                                   "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                   "bekommen, schau mal nach!")

            xpService.grantXpBoost(member, AchievementParameter.ONLINE)
        elif kind == AchievementParameter.STREAM:
            message = tag + ", du hast nun schon " + str(hours) + (" Stunden gestreamt. Weiter so :cookie:"
                                                                   "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                   "bekommen, schau mal nach!")

            xpService.grantXpBoost(member, AchievementParameter.STREAM)
        else:
            message = tag + ", du hast bereits " + str(value) + " XP gefarmt. Weiter so :cookie: :video_game:"

        try:
            await self.channel.send(message)
        except Exception as error:
            logger.error("the achievement couldn't be sent", exc_info=error)
