import logging
from enum import Enum

import discord.interactions
from discord import HTTPException, InteractionResponded, Client

from src.Helper.SplitStringAtMaxLength import splitStringAtMaxLength
from src.Services.ApiServices import ApiServices
from src.Services.ChannelService import ChannelService
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.QuestService import QuestService, QuestType
from src.Services.QuotesManager import QuotesManager
from src.Services.ReminderService import ReminderService
from src.Services.SoundboardService import SoundboardService
from src.Services.UserSettings import UserSettings
from src.Services.VoiceClientService import VoiceClientService
from src.Services.WhatsAppHelper import WhatsAppHelper
from src.View.PaginationView import PaginationView

logger = logging.getLogger("KVGG_BOT")


class Commands(Enum):
    # LOGS = 1
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
    # NOTIFICATIONS_XP = 14
    FELIX_TIMER = 15
    DISABLE_COGS = 16
    ENABLE_COGS = 17
    WHATSAPP_SUSPEND_SETTINGS = 18
    RESET_WHATSAPP_SUSPEND_SETTINGS = 19
    LIST_WHATSAPP_SUSPEND_SETTINGS = 20
    WEATHER = 21
    CURRENCY_CONVERTER = 22
    QRCODE = 23
    # NOTIFICATIONS_WELCOME_BACK = 24
    CREATE_REMINDER = 25
    LIST_REMINDERS = 26
    DELETE_REMINDER = 27
    PLAY_SOUND = 28
    STOP_SOUND = 29
    KNEIPE = 30
    LIST_SOUNDS = 31
    DELETE_SOUND = 32
    LIST_QUESTS = 33
    NOTIFICATION_SETTING = 34


class CommandService:

    def __init__(self, client: Client):
        self.client = client
        # TODO remove #
        self.apiService = ApiServices()  #
        self.userInputService = ProcessUserInput(self.client)  #
        self.quotesManager = QuotesManager(self.client)  #
        self.userSettings = UserSettings()  #
        self.experienceService = ExperienceService(self.client)  #
        self.whatsappHelper = WhatsAppHelper(self.client)  #
        self.reminderService = ReminderService(self.client)  #
        self.soundboardService = SoundboardService(self.client)  #
        self.voiceClientService = VoiceClientService(self.client)  #
        self.channelService = ChannelService(self.client)  #
        self.questService = QuestService(self.client)

    async def __setLoading(self, ctx: discord.interactions.Interaction) -> bool:
        """
        Sets the interaction to thinking

        :param ctx: Interaction to think about
        :return: bool, True if success, false if failure
        """
        try:
            await ctx.response.defer(thinking=True)
        except discord.errors.NotFound as error:
            logger.error("too late :(", exc_info=error)

            return False
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
            await self.userInputService.raiseMessageCounter(ctx.user, ctx.channel, True)
        except ConnectionError as error:
            logger.error("failure to start ProcessUserInput", exc_info=error)

        try:
            for part in splitStringAtMaxLength(answer):
                await ctx.followup.send(part)
        except Exception as e:
            logger.error("couldn't send answer to command", exc_info=e)

        logger.debug("sent webhook-answer")

        await self.questService.addProgressToQuest(ctx.user, QuestType.COMMAND_COUNT)

    async def runCommand(self, command: Commands, interaction: discord.interactions.Interaction, **kwargs):
        """
        Wrapper to use commands easily

        :param command: Command-type to execute
        :param interaction: Interaction from the user to answer to
        :param kwargs: Parameters of the called function
        :return:
        """
        # https://chat.openai.com/share/35c755a0-677d-4d33-aa82-91caee4546ac

        if not await self.__setLoading(interaction):
            return

        answer = ""

        try:
            match command:
                case Commands.JOKE:
                    answer = await self.apiService.getJoke(**kwargs)

                case Commands.MOVE:
                    answer = await self.userInputService.moveUsers(**kwargs)

                case Commands.QUOTE:
                    answer = self.quotesManager.answerQuote(**kwargs)

                case Commands.TIME:
                    answer = await self.userInputService.accessTimeAndEdit(**kwargs)

                case Commands.COUNTER:
                    answer = await self.userInputService.accessNameCounterAndEdit(**kwargs)

                case Commands.WHATSAPP:
                    answer = await self.userSettings.manageWhatsAppSettings(**kwargs)

                case Commands.LEADERBOARD:
                    answer = await self.userInputService.sendLeaderboard(**kwargs)

                case Commands.REGISTRATION:
                    answer = await self.userInputService.sendRegistrationLink(**kwargs)

                case Commands.XP_SPIN:
                    answer = self.experienceService.spinForXpBoost(**kwargs)

                case Commands.XP_INVENTORY:
                    answer = self.experienceService.handleXpInventory(**kwargs)

                case Commands.XP:
                    answer = self.experienceService.handleXpRequest(**kwargs)

                case Commands.NOTIFICATION_SETTING:
                    answer = self.userSettings.changeNotificationSetting(**kwargs)

                case Commands.FELIX_TIMER:
                    answer = await self.userInputService.handleFelixTimer(**kwargs)

                case Commands.WHATSAPP_SUSPEND_SETTINGS:
                    answer = self.whatsappHelper.addOrEditSuspendDay(**kwargs)

                case Commands.RESET_WHATSAPP_SUSPEND_SETTINGS:
                    answer = self.whatsappHelper.resetSuspendSetting(**kwargs)

                case Commands.LIST_WHATSAPP_SUSPEND_SETTINGS:
                    answer = self.whatsappHelper.listSuspendSettings(**kwargs)

                case Commands.WEATHER:
                    answer = await self.apiService.getWeather(**kwargs)

                case Commands.CURRENCY_CONVERTER:
                    answer = await self.apiService.convertCurrency(**kwargs)

                case Commands.QRCODE:
                    answer = await self.apiService.generateQRCode(**kwargs)

                    # TODO: dont skip command increase and so on
                    if isinstance(answer, discord.File):
                        try:
                            await interaction.followup.send(file=answer)
                        except Exception as e:
                            logger.error("couldn't send qr-picture", exc_info=e)

                        return

                case Commands.CREATE_REMINDER:
                    answer = self.reminderService.createReminder(**kwargs)

                case Commands.LIST_REMINDERS:
                    answer = self.reminderService.listReminders(**kwargs)

                case Commands.DELETE_REMINDER:
                    answer = self.reminderService.deleteReminder(**kwargs)

                case Commands.PLAY_SOUND:
                    answer = await self.soundboardService.playSound(ctx=interaction, **kwargs)

                case Commands.STOP_SOUND:
                    answer = await self.voiceClientService.stop(**kwargs)

                case Commands.KNEIPE:
                    answer = await self.channelService.createKneipe(interaction.user, **kwargs)

                case Commands.LIST_SOUNDS:
                    data = await self.soundboardService.listPersonalSounds(ctx=interaction)

                    await PaginationView(
                        ctx=interaction,
                        data=data,
                        client=self.client,
                        title="Sounds",
                        defer=False,
                    ).send()

                case Commands.DELETE_SOUND:
                    answer = await self.soundboardService.deletePersonalSound(ctx=interaction, **kwargs)

                case Commands.LIST_QUESTS:
                    answer = self.questService.listQuests(**kwargs)

                case _:
                    answer = "Es ist etwas schief gelaufen!"

                    logger.warning("undefined enum-entry was used")

        except ValueError as e:
            answer = "Es ist etwas schief gelaufen!"

            logger.error("parameters arent matched with function parameters", exc_info=e)

        await self.__sendAnswer(interaction, answer)
