import inspect
import logging
from enum import Enum
from pathlib import Path

import discord.interactions
from discord import Client

from src.Helper.SplitStringAtMaxLength import splitStringAtMaxLength
from src.Manager.ChannelManager import ChannelService
from src.Manager.QuotesManager import QuotesManager
from src.Services.ApiServices import ApiServices
from src.Services.CounterService import CounterService
from src.Services.ExperienceService import ExperienceService
from src.Services.GameDiscordService import GameDiscordService
from src.Services.LeaderboardService import LeaderboardService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.QuestService import QuestService, QuestType
from src.Services.ReminderService import ReminderService
from src.Services.SoundboardService import SoundboardService
from src.Services.UserSettings import UserSettings
from src.Services.VoiceClientService import VoiceClientService
from src.Services.WhatsAppService import WhatsAppHelper
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
    # LEADERBOARD = 8
    # REGISTRATION = 9
    XP_SPIN = 10
    XP_INVENTORY = 11
    XP = 12
    XP_LEADERBOARD = 13
    # NOTIFICATIONS_XP = 14
    FELIX_TIMER = 15
    # DISABLE_COGS = 16
    # ENABLE_COGS = 17
    WHATSAPP_SUSPEND_SETTINGS = 18
    RESET_WHATSAPP_SUSPEND_SETTINGS = 19
    LIST_WHATSAPP_SUSPEND_SETTINGS = 20
    # WEATHER = 21
    # CURRENCY_CONVERTER = 22
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
    CREATE_COUNTER = 35
    LIST_COUNTERS = 36
    CREATE_TIMER = 37
    CHOOSE_RANDOM_GAME = 38
    DATA_FROM_MEMBER = 39
    CHOOSE_RANDOM_GAME_IN_CHANNEL = 40
    SHOW_ALL_TOGETHER_PLAYED_GAMES = 41


class CommandService:

    def __init__(self, client: Client):
        self.client = client

        self.apiService = ApiServices()
        self.userInputService = ProcessUserInput(self.client)
        self.quotesManager = QuotesManager(self.client)
        self.userSettings = UserSettings()
        self.experienceService = ExperienceService(self.client)
        self.whatsappHelper = WhatsAppHelper(self.client)
        self.reminderService = ReminderService(self.client)
        self.soundboardService = SoundboardService(self.client)
        self.voiceClientService = VoiceClientService(self.client)
        self.channelService = ChannelService(self.client)
        self.questService = QuestService(self.client)
        self.counterService = CounterService(self.client)
        self.gameDiscordService = GameDiscordService(self.client)

    async def _prepareCommandRun(self, ctx: discord.interactions.Interaction, contextMenu: bool) -> bool:
        """
        Sets the interaction to thinking

        :param ctx: Interaction to think about
        :return: bool, True if success, false if failure
        """
        try:
            # noinspection PyUnresolvedReferences
            await ctx.response.defer(thinking=True, ephemeral=contextMenu)
        except discord.errors.NotFound:
            logger.warning("too late :(")

            return False
        except Exception as error:
            logger.error("couldn't set interaction to loading", exc_info=error)

            return False

        logger.debug("set interaction to thinking")

        # run increases here to avoid having database changes after a (completed) command
        await self.userInputService.raiseMessageCounter(ctx.user, ctx.channel, True)
        await self.questService.addProgressToQuest(ctx.user, QuestType.COMMAND_COUNT)

        return True

    # noinspection PyMethodMayBeStatic
    async def _sendAnswer(self, ctx: discord.interactions.Interaction, answer: str | list[str], contextMenu: bool):
        """
        Sends the specified answer to the interaction

        :param ctx: Interaction to answer
        :param answer: Answer that will be sent
        :param contextMenu: True if the command was called from a context menu
        :return:
        """
        try:
            # special case for images
            if isinstance(answer, Path):
                await ctx.followup.send(file=discord.File(answer), ephemeral=contextMenu)
            elif isinstance(answer, list):
                for part in answer:
                    for splitPart in splitStringAtMaxLength(part):
                        await ctx.followup.send(splitPart, ephemeral=contextMenu)
            else:
                for part in splitStringAtMaxLength(answer):
                    await ctx.followup.send(part, ephemeral=contextMenu)
        except Exception as e:
            logger.error("couldn't send answer to command", exc_info=e)

        logger.debug("sent webhook-answer")

    async def runCommand(self,
                         command: Commands,
                         interaction: discord.interactions.Interaction,
                         contextMenu: bool = False,
                         **kwargs):
        """
        Wrapper to use commands easily

        :param command: Command-type to execute
        :param interaction: Interaction from the user to answer to
        :param contextMenu: True if the command was called from a context menu
        :param kwargs: Parameters of the called function
        :return:
        """
        if not await self._prepareCommandRun(interaction, contextMenu):
            return

        function = None

        match command:
            case Commands.JOKE:
                function = self.apiService.getJoke

            case Commands.MOVE:
                function = self.userInputService.moveUsers

            case Commands.QUOTE:
                function = self.quotesManager.answerQuote

            case Commands.TIME:
                function = self.userInputService.accessTimeAndEdit

            case Commands.COUNTER:
                function = self.counterService.accessNameCounterAndEdit

            case Commands.WHATSAPP:
                function = self.userSettings.manageWhatsAppSettings

            # case Commands.LEADERBOARD:
            #     data = await LeaderboardService(self.client).getLeaderboard()

            #     await PaginationView(
            #         ctx=interaction,
            #         data=data,
            #         client=self.client,
            #         title="Leaderboard",
            #         defer=False,
            #         seperator=1,
            #     ).send()

            #     function = "Pagination-View"

            case Commands.XP_SPIN:
                function = self.experienceService.spinForXpBoost

            case Commands.XP_INVENTORY:
                function = self.experienceService.handleXpInventory

            case Commands.XP:
                function = self.experienceService.handleXpRequest

            case Commands.NOTIFICATION_SETTING:
                function = self.userSettings.changeNotificationSetting

            case Commands.FELIX_TIMER:
                function = self.userInputService.handleFelixTimer

            case Commands.WHATSAPP_SUSPEND_SETTINGS:
                function = self.whatsappHelper.addOrEditSuspendDay

            case Commands.RESET_WHATSAPP_SUSPEND_SETTINGS:
                function = self.whatsappHelper.resetSuspendSetting

            case Commands.LIST_WHATSAPP_SUSPEND_SETTINGS:
                function = self.whatsappHelper.listSuspendSettings

            # case Commands.WEATHER:
            #     function = self.apiService.getWeather

            case Commands.QRCODE:
                function = self.apiService.generateQRCode

            case Commands.CREATE_REMINDER:
                function = self.reminderService.createReminder

            case Commands.LIST_REMINDERS:
                data = self.reminderService.listReminders(**kwargs)

                await PaginationView(
                    ctx=interaction,
                    data=data,
                    client=self.client,
                    title="Reminder",
                    defer=False,
                    seperator=9,
                ).send()

                function = "Pagination-View"

            case Commands.DELETE_REMINDER:
                function = self.reminderService.deleteReminder

            case Commands.PLAY_SOUND:
                function = self.soundboardService.playSound

            case Commands.STOP_SOUND:
                function = self.voiceClientService.stop

            case Commands.KNEIPE:
                function = self.channelService.createKneipe

            case Commands.LIST_SOUNDS:
                data = await self.soundboardService.listPersonalSounds(**kwargs)

                await PaginationView(
                    ctx=interaction,
                    data=data,
                    client=self.client,
                    title="Sounds",
                    defer=False,
                    seperator=9,
                ).send()

                function = "Pagination-View"

            case Commands.DELETE_SOUND:
                function = self.soundboardService.deletePersonalSound

            case Commands.LIST_QUESTS:
                function = self.questService.listQuests

            case Commands.CREATE_COUNTER:
                function = self.counterService.createNewCounter

            case Commands.LIST_COUNTERS:
                function = self.counterService.listAllCounters

            case Commands.CREATE_TIMER:
                function = self.reminderService.createTimer

            case Commands.CHOOSE_RANDOM_GAME:
                function = self.gameDiscordService.chooseRandomGame

            case Commands.DATA_FROM_MEMBER:
                function = LeaderboardService(self.client).getDataForMember

            case Commands.CHOOSE_RANDOM_GAME_IN_CHANNEL:
                function = self.gameDiscordService.chooseRandomGameInChannel

            case Commands.SHOW_ALL_TOGETHER_PLAYED_GAMES:
                function = self.gameDiscordService.getTogetherPlayedGames

            case _:
                logger.error("undefined enum entry was reached!")

        try:
            if not function:
                await self._sendAnswer(interaction, "Es ist etwas schief gelaufen!", contextMenu)

                return
            elif inspect.iscoroutinefunction(function):
                answer = await function(**kwargs)
            # special case for Pagination-Views
            elif function == "Pagination-View":
                answer = ""
            else:
                answer = function(**kwargs)
        except Exception as error:
            logger.error(f"An error occurred while running {function}!", exc_info=error)

            answer = "Es gab einen Fehler!"

        await self._sendAnswer(interaction, answer, contextMenu)
