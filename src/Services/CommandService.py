import logging
from enum import Enum

import discord.interactions
from discord import HTTPException, InteractionResponded, NotFound

from src.Services.ApiServices import ApiServices
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.QuotesManager import QuotesManager
from src.Services.WhatsAppHelper import WhatsAppHelper

logger = logging.getLogger("KVGG_BOT")


class Commands(Enum):
    LOGS = 1
    JOKE = 2
    MOVE = 3
    QUOTE = 4
    TIME = 5
    COUNTER = 6
    WHATSAPP = 7
    LEADERBOARD = 8
    REGISTRATION = 9
    XP_SPIN = 10
    XP_INVENTORY = 11
    XP = 12
    XP_LEADERBOARD = 13
    NOTIFICATIONS_XP = 14
    FELIX_TIMER = 15
    DISABLE_COGS = 16
    ENABLE_COGS = 17
    WHATSAPP_SUSPEND_SETTINGS = 18
    RESET_WHATSAPP_SUSPEND_SETTINGS = 19
    LIST_WHATSAPP_SUSPEND_SETTINGS = 20
    WEATHER = 21
    CURRENCY_CONVERTER = 22
    QRCODE = 23
    NOTIFICATIONS_BACK = 24


class CommandService:

    def __init__(self, client: discord.Client):
        self.client = client

    async def __setLoading(self, ctx: discord.interactions.Interaction) -> bool:
        """
        Sets the interaction to thinking

        :param ctx: Interaction to think about
        :return: bool, True if success, false if failure
        """
        try:
            await ctx.response.defer(thinking=True)
        except HTTPException as e:
            logger.error("received HTTPException", exc_info=e)

            return False
        except InteractionResponded as e:
            logger.error("interaction was answered before", exc_info=e)

            return False

        logger.debug("set interaction to thinking")

        return True

    async def __sendAnswer(self, ctx: discord.interactions.Interaction, answer: str, pui: ProcessUserInput):
        """
        Sends the specified answer to the interaction

        :param ctx: Interaction to answer
        :param answer: Answer that will be sent
        :return:
        """
        pui.raiseMessageCounter(ctx.user, ctx.channel)

        try:
            await ctx.followup.send(answer)
        except Exception as e:
            logger.error("couldn't send answer to command", exc_info=e)

        logger.debug("sent webhook-answer")

    async def runCommand(self, command: Commands, interaction: discord.interactions.Interaction, **kwargs):
        """
        Wrapper to use commands easily

        :param command: Command-type to execute
        :param interaction: Interaction from the user to answer to
        :param kwargs: Parameters of the called function
        :return:
        """
        if not await self.__setLoading(interaction):
            return

        pui = ProcessUserInput(self.client)
        qm = QuotesManager(self.client)
        xp = ExperienceService(self.client)
        wa = WhatsAppHelper()
        api = ApiServices()

        try:
            match command:
                case Commands.LOGS:
                    answer = await pui.sendLogs(**kwargs)

                case Commands.JOKE:
                    answer = await pui.answerJoke(**kwargs)

                case Commands.MOVE:
                    answer = await pui.moveUsers(**kwargs)

                case Commands.QUOTE:
                    answer = qm.answerQuote(**kwargs)

                case Commands.TIME:
                    answer = await pui.accessTimeAndEdit(**kwargs)

                case Commands.COUNTER:
                    answer = await pui.accessNameCounterAndEdit(**kwargs)

                case Commands.WHATSAPP:
                    answer = await pui.manageWhatsAppSettings(**kwargs)

                case Commands.LEADERBOARD:
                    answer = await pui.sendLeaderboard(**kwargs)

                case Commands.REGISTRATION:
                    answer = await pui.sendRegistrationLink(**kwargs)

                case Commands.XP_SPIN:
                    answer = await xp.spinForXpBoost(**kwargs)

                case Commands.XP_INVENTORY:
                    answer = await xp.handleXpInventory(**kwargs)

                case Commands.XP:
                    answer = await xp.handleXpRequest(**kwargs)

                case Commands.XP_LEADERBOARD:
                    answer = xp.sendXpLeaderboard(**kwargs)

                case Commands.NOTIFICATIONS_BACK:
                    answer = pui.changeWelcomeBackNotificationSetting(**kwargs)

                case Commands.NOTIFICATIONS_XP:
                    answer = xp.handleXpNotification(**kwargs)

                case Commands.FELIX_TIMER:
                    answer = await pui.handleFelixTimer(**kwargs)

                case Commands.WHATSAPP_SUSPEND_SETTINGS:
                    answer = wa.addOrEditSuspendDay(**kwargs)

                case Commands.RESET_WHATSAPP_SUSPEND_SETTINGS:
                    answer = wa.resetSuspendSetting(**kwargs)

                case Commands.LIST_WHATSAPP_SUSPEND_SETTINGS:
                    answer = wa.listSuspendSettings(**kwargs)

                case Commands.WEATHER:
                    answer = await api.getWeather(**kwargs)

                case Commands.CURRENCY_CONVERTER:
                    answer = await api.convertCurrency(**kwargs)

                case Commands.QRCODE:
                    answer = await api.generateQRCode(**kwargs)

                    if isinstance(answer, discord.File):
                        try:
                            await interaction.followup.send(file=answer)
                        except Exception as e:
                            logger.error("couldn't send qr-picture", exc_info=e)

                        return

                case _:
                    answer = "Es ist etwas schief gelaufen!"

                    logger.warning("undefined enum-entry was used")

        except ValueError as e:
            answer = "Es ist etwas schief gelaufen!"

            logger.error("parameters arent matched with function parameters", exc_info=e)

        await self.__sendAnswer(interaction, answer, pui)
