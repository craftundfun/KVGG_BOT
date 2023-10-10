import logging
from os import environ

from discord import Client, Member

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Id.ChannelId import ChannelId

logger = logging.getLogger("KVGG_BOT")
IN_DOCKER = environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)


class AchievementService:

    def __init__(self, client: Client):
        self.client = client
        self.channel = self.client.get_channel(ChannelId.CHANNEL_ACHIEVEMENTS.value)

    async def sendAchievementAndGrantBoost(self, member: Member, kind: AchievementParameter, value: int):
        """
        Sends the achievement message into our achievement channel and grants the corresponding xp boost

        :param member: List of members, who reached the achievement and to be tagged
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

        match kind:
            case AchievementParameter.ONLINE:
                message = tag + ", du bist nun schon " + str(hours) + (" Stunden online gewesen. Weiter so :cookie:"
                                                                       "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                       "bekommen, schau mal nach!")

                xpService.grantXpBoost(member, AchievementParameter.ONLINE)
            case AchievementParameter.STREAM:
                tag = getTagStringFromId(str(member.id))
                message = tag + ", du hast nun schon " + str(hours) + (" Stunden gestreamt. Weiter so :cookie:"
                                                                       "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                       "bekommen, schau mal nach!")

                xpService.grantXpBoost(member, AchievementParameter.STREAM)
            case AchievementParameter.XP:
                tag = getTagStringFromId(str(member.id))
                message = (tag + ", du hast bereits %s XP gefarmt. Weiter so :cookie: :video_game:"
                           % '{:,}'.format(value).replace(',', '.'))
            case _:
                logger.critical("reached undefined enum entry")

                return

        await self.__sendAchievementMessage(message)

    async def sendAchievementAndGrantBoostForRelation(self,
                                                      member_1: Member,
                                                      member_2: Member,
                                                      kind: AchievementParameter,
                                                      value: int):
        """
        Sends the achievement message into our achievement channel and grants the corresponding xp boosts

        :param member_1: First member to receive the boost
        :param member_2: Second member to receive the boost
        :param kind: Type of achievement
        :param value: Value of the time
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

        try:
            xpService = ExperienceService(self.client)
        except ConnectionError as error:
            logger.error("failure to start ExperienceService", exc_info=error)

            return

        hours = int(value / 60)
        tag_1: str = getTagStringFromId(str(member_1.id))
        tag_2: str = getTagStringFromId(str(member_2.id))

        match kind:
            case AchievementParameter.RELATION_ONLINE:
                message = (tag_1 + " und " + tag_2 + ", ihr beide wart schon " + str(hours) + " Stunden zusammen "
                                                                                              "online! :cookie:\n\n"
                                                                                              "Dafür habt ihr beide "
                                                                                              "einen XP-Boost "
                                                                                              "bekommen!")
                xpService.grantXpBoost(member_1, AchievementParameter.RELATION_ONLINE)
                xpService.grantXpBoost(member_2, AchievementParameter.RELATION_ONLINE)
            case AchievementParameter.RELATON_STREAM:
                message = (tag_1 + " und " + tag_2 + ", ihr habt schon beide " + str(hours) + " Stunden gemeinsam "
                                                                                              "gestreamt! :cookie:\n\n"
                                                                                              "Dafür habt ihr beide "
                                                                                              "einen XP-Boost "
                                                                                              "bekommen!")
                xpService.grantXpBoost(member_1, AchievementParameter.RELATON_STREAM)
                xpService.grantXpBoost(member_2, AchievementParameter.RELATON_STREAM)
            case _:
                logger.critical("undefined enum entry was reached")

                return

        await self.__sendAchievementMessage(message)

    async def __sendAchievementMessage(self, message: str):
        """
        Sends the achievement message into the correct channel (bot-test-environment for debug purposes outside of
        docker container)

        :param message:
        :return:
        """
        if IN_DOCKER:
            try:
                await self.channel.send(message)
            except Exception as error:
                logger.error("the achievement couldn't be sent", exc_info=error)
        else:
            try:
                await self.client.get_channel(ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value).send(message)
            except Exception as error:
                logger.error("the test-achievement couldn't be sent", exc_info=error)
