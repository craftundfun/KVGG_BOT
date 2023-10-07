import logging
from enum import Enum

import discord.interactions
from discord import HTTPException, InteractionResponded

from src.Services.ApiServices import ApiServices
from src.Services.ChannelService import ChannelService
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.QuotesManager import QuotesManager
from src.Services.ReminderService import ReminderService
from src.Services.SoundboardService import SoundboardService
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
    NOTIFICATIONS_WELCOME_BACK = 24
    CREATE_REMINDER = 25
    LIST_REMINDERS = 26
    DELETE_REMINDER = 27
    PLAY_SOUND = 28
    STOP_SOUND = 29
    KNEIPE = 30


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
        try:
            await ProcessUserInput(self.client).raiseMessageCounter(ctx.user, ctx.channel)
        except ConnectionError as error:
            logger.error("failure to start ProcessUserInput", exc_info=error)

        def splitStringAtMaxLength(string: str, maxLength: int = 2000) -> list[str]:
            """
            Splits the string at the nearest newline at 2000 characters.

            :param string:
            :param maxLength:
            :return:
            """
            if not string:
                return [""]

            if len(string) <= maxLength:
                return [string]

            for i in range(maxLength, 0, -1):
                if string[i] == '\n':
                    return [string[:i], string[i + 1:]]

            return [string[:maxLength], string[maxLength:]]

        try:
            for part in splitStringAtMaxLength(answer):
                await ctx.followup.send(part)
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
                case Commands.JOKE:
                    answer = await ApiServices().getJoke(**kwargs)

                case Commands.MOVE:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.moveUsers(**kwargs)

                case Commands.QUOTE:
                    try:
                        qm = QuotesManager(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start QuotesManager", exc_info=error)
                    else:
                        answer = qm.answerQuote(**kwargs)

                case Commands.TIME:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.accessTimeAndEdit(**kwargs)

                case Commands.COUNTER:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.accessNameCounterAndEdit(**kwargs)

                case Commands.WHATSAPP:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.manageWhatsAppSettings(**kwargs)

                case Commands.LEADERBOARD:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.sendLeaderboard(**kwargs)

                case Commands.REGISTRATION:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.sendRegistrationLink(**kwargs)

                case Commands.XP_SPIN:
                    try:
                        es = ExperienceService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ExperienceService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = es.spinForXpBoost(**kwargs)

                case Commands.XP_INVENTORY:
                    try:
                        es = ExperienceService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ExperienceService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = es.handleXpInventory(**kwargs)

                case Commands.XP:
                    try:
                        es = ExperienceService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ExperienceService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = es.handleXpRequest(**kwargs)

                case Commands.NOTIFICATIONS_WELCOME_BACK:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = pui.changeWelcomeBackNotificationSetting(**kwargs)

                case Commands.NOTIFICATIONS_XP:
                    try:
                        es = ExperienceService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ExperienceService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = es.handleXpNotification(**kwargs)

                case Commands.FELIX_TIMER:
                    try:
                        pui = ProcessUserInput(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ProcessUserInput", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = await pui.handleFelixTimer(**kwargs)

                case Commands.WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper(self.client).addOrEditSuspendDay(**kwargs)

                case Commands.RESET_WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper(self.client).resetSuspendSetting(**kwargs)

                case Commands.LIST_WHATSAPP_SUSPEND_SETTINGS:
                    answer = WhatsAppHelper(self.client).listSuspendSettings(**kwargs)

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
                    try:
                        rs = ReminderService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ReminderService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = rs.createReminder(**kwargs)

                case Commands.LIST_REMINDERS:
                    try:
                        rs = ReminderService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ReminderService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = rs.listReminders(**kwargs)

                case Commands.DELETE_REMINDER:
                    try:
                        rs = ReminderService(self.client)
                    except ConnectionError as error:
                        logger.error("failure to start ReminderService", exc_info=error)

                        answer = "Es ist ein Fehler aufgetreten."
                    else:
                        answer = rs.deleteReminder(**kwargs)

                case Commands.PLAY_SOUND:
                    voiceClientService = SoundboardService(self.client)
                    answer = await voiceClientService.play(ctx=interaction, **kwargs)

                case Commands.STOP_SOUND:
                    voiceClientService = SoundboardService(self.client)
                    answer = await voiceClientService.stop(**kwargs)

                case Commands.KNEIPE:
                    channelService = ChannelService(self.client)
                    answer = await channelService.createKneipe()

                case _:
                    answer = "Es ist etwas schief gelaufen!"

                    logger.warning("undefined enum-entry was used")

        except ValueError as e:
            answer = "Es ist etwas schief gelaufen!"

            logger.error("parameters arent matched with function parameters", exc_info=e)

        await self.__sendAnswer(interaction, answer)
