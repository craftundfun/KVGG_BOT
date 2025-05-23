import logging

from discord import Client, Member

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.ReadParameters import getParameter, Parameters
from src.Id.ChannelId import ChannelId

logger = logging.getLogger("KVGG_BOT")


class AchievementService:

    def __init__(self, client: Client):
        self.client = client
        self.channel = self.client.get_channel(ChannelId.CHANNEL_ACHIEVEMENTS.value)

    async def sendAchievementAndGrantBoost(self,
                                           member: Member,
                                           kind: AchievementParameter,
                                           value: int,
                                           gameName: str = None, ):
        """
        Sends the achievement message into our achievement channel and grants the corresponding xp boost

        :param member: List of members who reached the achievement and to be tagged
        :param kind: ONLINE, STREAM or XP
        :param value: Value of the achievement, for example, 300 minutes online -> will be calculated into hours
        :param gameName: Optional name of the game to mention it in the message
        :return:
        """
        # import here to avoid circular import
        from src.Services.ProcessUserInput import getTagStringFromId
        from src.Services.ExperienceService import ExperienceService

        xpService = ExperienceService(self.client)

        if type(kind.value) != str:
            logger.critical("false argument type")

            return
        elif not self.channel:
            logger.critical("cant reach channel")

            return

        tag = getTagStringFromId(str(member.id))
        hours = int(value / 60)

        match kind:
            case AchievementParameter.ONLINE:
                message = tag + ", du bist nun schon " + str(hours) + (" Stunden online gewesen. Weiter so :cookie:"
                                                                       "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                       "bekommen, schau mal nach!")

                await xpService.grantXpBoost(member, AchievementParameter.ONLINE)
            case AchievementParameter.STREAM:
                message = tag + ", du hast nun schon " + str(hours) + (" Stunden gestreamt. Weiter so :cookie:"
                                                                       "\n\nAußerdem hast du einen neuen XP-Boost "
                                                                       "bekommen, schau mal nach!")

                await xpService.grantXpBoost(member, AchievementParameter.STREAM)
            case AchievementParameter.XP:
                message = (tag + ", du hast bereits %s XP gefarmt. Weiter so :cookie: :video_game:"
                           % '{:,}'.format(value).replace(',', '.'))
            case AchievementParameter.ANNIVERSARY:
                message = (":fireworks: :fireworks: Herzlichen Glückwunsch "
                           + tag
                           + ", du bist nun schon seit "
                           + str(value)
                           + f" {'Jahren' if value > 1 else 'Jahr'} auf unserem Server! :fireworks: :fireworks:")
            case AchievementParameter.TIME_PLAYED:
                if not gameName:
                    logger.error("gameName is missing")

                message = (f"Während du online warst, hast du insgesamt schon {hours} Stunden "
                           f"{gameName if gameName else 'FEHLER'} gespielt, {tag}. Viel Spaß beim Weiterspielen!\n\n"
                           f"Dafür hast du einen XP-Boost bekommen, schau mal nach!")

                await xpService.grantXpBoost(member, AchievementParameter.TIME_PLAYED)
            case _:
                logger.error("reached undefined enum entry")

                return

        await self._sendAchievementMessage(message)

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
        from src.Services.ExperienceService import ExperienceService

        xpService = ExperienceService(self.client)

        if type(kind.value) != str:
            logger.error(f"false argument type: {kind}")

            return
        elif not self.channel:
            logger.error("cant reach channel")

            return

        hours = int(value / 60)
        tag_1 = f"<@{member_1.id}>"
        tag_2 = f"<@{member_2.id}>"

        match kind:
            case AchievementParameter.RELATION_ONLINE:
                message = (tag_1 + " und " + tag_2 + ", ihr beide wart schon " + str(hours) + " Stunden zusammen "
                                                                                              "online! :cookie:\n\n"
                                                                                              "Dafür habt ihr beide "
                                                                                              "einen XP-Boost "
                                                                                              "bekommen!")
                await xpService.grantXpBoost(member_1, AchievementParameter.RELATION_ONLINE)
                await xpService.grantXpBoost(member_2, AchievementParameter.RELATION_ONLINE)
            case AchievementParameter.RELATION_STREAM:
                message = (tag_1 + " und " + tag_2 + ", ihr habt schon beide " + str(hours) + " Stunden gemeinsam "
                                                                                              "gestreamt! :cookie:\n\n"
                                                                                              "Dafür habt ihr beide "
                                                                                              "einen XP-Boost "
                                                                                              "bekommen!")
                await xpService.grantXpBoost(member_1, AchievementParameter.RELATION_STREAM)
                await xpService.grantXpBoost(member_2, AchievementParameter.RELATION_STREAM)
            case AchievementParameter.RELATION_ACTIVITY:
                message = (tag_1 + " und " + tag_2 + ", ihr habt schon " + str(hours) + " Stunden gemeinsam "
                                                                                        "Spiele gespielt! :cookie:\n\n"
                                                                                        "Dafür habt ihr beide "
                                                                                        "einen XP-Boost "
                                                                                        "bekommen!")
                await xpService.grantXpBoost(member_1, AchievementParameter.RELATION_ACTIVITY)
                await xpService.grantXpBoost(member_2, AchievementParameter.RELATION_ACTIVITY)
            case _:
                logger.error(f"undefined enum entry was reached: {kind}")

                return

        await self._sendAchievementMessage(message)

    async def _sendAchievementMessage(self, message: str):
        """
        Sends the achievement message into the correct channel (bot-test-environment for debug purposes outside of
        docker container)

        :param message:
        :return:
        """
        if getParameter(Parameters.PRODUCTION):
            try:
                await self.channel.send(message)
            except Exception as error:
                logger.error("the achievement couldn't be sent", exc_info=error)
        else:
            try:
                await self.client.get_channel(ChannelId.CHANNEL_BOT_TEST_ENVIRONMENT.value).send(message)
            except Exception as error:
                logger.error("the test-achievement couldn't be sent", exc_info=error)
