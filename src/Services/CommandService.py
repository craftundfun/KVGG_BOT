import logging
from enum import Enum

import discord.interactions
from discord import HTTPException, InteractionResponded, NotFound

from src.Services.ApiServices import ApiServices
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.QuotesManager import QuotesManager
from src.Services.ReminderService import ReminderService
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
    CREATE_REMINDER = 25
    LIST_REMINDERS = 26
    DELETE_REMINDER = 27


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

    async def __sendAnswer(self, ctx: discord.interactions.Interaction, answer: str):
        """
        Sends the specified answer to the interaction

        :param ctx: Interaction to answer
        :param answer: Answer that will be sent
        :return:
        """
        ProcessUserInput(self.client).raiseMessageCounter(ctx.user, ctx.channel)

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

        try:
            match command:
                case Commands.LOGS:
                    # answer = await pui.sendLogs(**kwargs)
                    answer = "Dieser Dienst wird aktuell nicht unterstüzt."

                case Commands.JOKE:
                    answer = await ProcessUserInput(self.client).answerJoke(**kwargs)

                case Commands.MOVE:
                    answer = await ProcessUserInput(self.client).moveUsers(**kwargs)

                case Commands.QUOTE:
                    answer = QuotesManager(self.client).answerQuote(**kwargs)

                case Commands.TIME:
                    answer = await ProcessUserInput(self.client).accessTimeAndEdit(**kwargs)

                case Commands.COUNTER:
                    answer = await ProcessUserInput(self.client).accessNameCounterAndEdit(**kwargs)

                case Commands.WHATSAPP:
                    answer = await ProcessUserInput(self.client).manageWhatsAppSettings(**kwargs)

                case Commands.LEADERBOARD:
                    answer = await ProcessUserInput(self.client).sendLeaderboard(**kwargs)

                case Commands.REGISTRATION:
                    answer = await ProcessUserInput(self.client).sendRegistrationLink(**kwargs)

                case Commands.XP_SPIN:
                    answer = await ExperienceService(self.client).spinForXpBoost(**kwargs)

                case Commands.XP_INVENTORY:
                    answer = await ExperienceService(self.client).handleXpInventory(**kwargs)

                case Commands.XP:
                    answer = await ExperienceService(self.client).handleXpRequest(**kwargs)

                case Commands.XP_LEADERBOARD:
                    answer = ExperienceService(self.client).sendXpLeaderboard(**kwargs)

                case Commands.NOTIFICATIONS_BACK:
                    answer = ProcessUserInput(self.client).changeWelcomeBackNotificationSetting(**kwargs)

                case Commands.NOTIFICATIONS_XP:
                    answer = ExperienceService(self.client).handleXpNotification(**kwargs)

                case Commands.FELIX_TIMER:
                    answer = await ProcessUserInput(self.client).handleFelixTimer(**kwargs)

                case Commands.WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper().addOrEditSuspendDay(**kwargs)

                case Commands.RESET_WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper().resetSuspendSetting(**kwargs)

                case Commands.LIST_WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper().listSuspendSettings(**kwargs)

                case Commands.WEATHER:
                    answer = await ApiServices().getWeather(**kwargs)

                case Commands.CURRENCY_CONVERTER:
                    answer = await ApiServices().convertCurrency(**kwargs)

                case Commands.QRCODE:
                    answer = await ApiServices().generateQRCode(**kwargs)

                    if isinstance(answer, discord.File):
                        try:
                            await interaction.followup.send(file=answer)
                        except Exception as e:
                            logger.error("couldn't send qr-picture", exc_info=e)

                        return

                case Commands.CREATE_REMINDER:
                    answer = ReminderService(self.client).createReminder(**kwargs)

                case Commands.LIST_REMINDERS:
                    answer = ReminderService(self.client).listReminders(**kwargs)

                case Commands.DELETE_REMINDER:
                    answer = ReminderService(self.client).deleteReminder(**kwargs)

                case _:
                    answer = "Es ist etwas schief gelaufen!"

                    logger.warning("undefined enum-entry was used")

        except ValueError as e:
            answer = "Es ist etwas schief gelaufen!"

            logger.error("parameters arent matched with function parameters", exc_info=e)

        await self.__sendAnswer(interaction, answer)
