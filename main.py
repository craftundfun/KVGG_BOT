from __future__ import unicode_literals

import logging.handlers
import os
import os.path
import sys
import threading
import time
from typing import Any

import discord
import nest_asyncio
from discord import RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, app_commands, DMChannel, \
    RawReactionActionEvent, Intents
from discord import VoiceChannel
from discord.app_commands import Choice

from src.API import main as FastAPI
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.DiscordParameters.NotificationType import NotificationType
from src.Helper import ReadParameters
from src.Id.GuildId import GuildId
from src.Id.RoleId import RoleId
from src.Logger.CustomFormatter import CustomFormatter
from src.Logger.CustomFormatterFile import CustomFormatterFile
from src.Logger.FileAndConsoleHandler import FileAndConsoleHandler
from src.Manager.CommandManager import CommandService, Commands
from src.Manager.DatabaseRefreshManager import DatabaseRefreshService
from src.Manager.QuotesManager import QuotesManager
from src.Manager.VoiceStateUpdateManager import VoiceStateUpdateService
from src.Services.Database_Old import Database_Old
from src.Services.MemeService import MemeService
from src.Services.ProcessUserInput import ProcessUserInput
from src.Services.SoundboardService import SoundboardService

# set timezone to our time
os.environ['TZ'] = 'Europe/Berlin'
time.tzset()

# to make asyncio loops reentrant
nest_asyncio.apply()

# fetch / create logger
logger = logging.getLogger("KVGG_BOT")

# creates up to five log files, every day at midnight a new one is created - if 5 was reached logs will be overwritten
fileHandler = logging.handlers.TimedRotatingFileHandler(filename='Logs/log.txt', when='midnight', backupCount=5)
fileHandler.setFormatter(CustomFormatterFile())

# handler to write errors to stderr and the log file
clientHandler = FileAndConsoleHandler(fileHandler)
clientHandler.setFormatter(CustomFormatterFile())

# prints logs to the console
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(CustomFormatter())

# docker container
if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
    logger.setLevel(logging.DEBUG)
    fileHandler.setLevel(logging.DEBUG)
    consoleHandler.setLevel(logging.INFO)
# IDE
else:
    logger.setLevel(logging.DEBUG)
    fileHandler.setLevel(logging.INFO)
    consoleHandler.setLevel(logging.DEBUG)

logger.addHandler(fileHandler)
logger.addHandler(consoleHandler)

logger.info("\n\n----Initial bot start!----\n\n")


class MyClient(discord.Client):
    backgroundServices = None

    def __init__(self, *, intents: Intents, **options: Any):
        super().__init__(intents=intents, **options)

        self.memeService = MemeService(self)
        self.soundboardService = SoundboardService(self)
        self.voiceStateUpdateService = VoiceStateUpdateService(self)
        self.quotesManager = QuotesManager(self)
        self.processUserInput = ProcessUserInput(self)
        self.databaseRefreshService = DatabaseRefreshService(self)

        thread = threading.Thread(target=FastAPI.run_server)
        thread.daemon = True
        thread.start()

    async def on_member_join(self, member: Member):
        """
        Automatically adds the roles Uni and Mitglieder to newly joined members of the guild.

        :param member: Member that newly join
        :return:
        """
        roleMitglied = member.guild.get_role(RoleId.UNI.value)
        roleUni = member.guild.get_role(RoleId.MITGLIEDER.value)

        await member.add_roles(roleMitglied, roleUni, reason="Automatic role by bot")

        logger.debug("%s received the following roles: %s, %s" % (
            member.nick if member.nick else member.name, roleMitglied.name, roleUni.name)
                     )

    async def on_member_remove(self, member):
        pass

    async def _prepareForMemeService(self, payload: RawReactionActionEvent):
        channel = client.get_channel(payload.channel_id)

        if not channel:
            return

        message = await channel.fetch_message(payload.message_id)

        if not message:
            return

        await self.memeService.changeLikeCounterOfMessage(message)

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self._prepareForMemeService(payload)

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        await self._prepareForMemeService(payload)

    async def on_ready(self):
        """
        NOT THE FIRST THING TO BE EXECUTED

        Runs all (important) start scripts, such as the BotStartUpService or syncing the commands
        to the guild.

        :return:
        """
        logger.info("Logged in as: " + str(self.user))

        # from src.Repository.Counter.Repository.CounterRepository import getCounterDiscordMapping
        # from src.Manager.DatabaseManager import getSession

        # print(getCounterDiscordMapping(self.get_guild(GuildId.GUILD_KVGG.value).get_member(416967436617777163), "Test", getSession()))

        # sys.exit(0)

        try:
            # await self.databaseRefreshService.startUp() # TODO enable again
            pass
        except ConnectionError as error:
            logger.error("failure to run database start up", exc_info=error)
        else:
            logger.info("users fetched and updated")

        if not (guild := client.get_guild(GuildId.GUILD_KVGG.value)):
            logger.error("couldn't fetch guild")

            return

        if len(sys.argv) > 1 and sys.argv[1] == "-clean":
            logger.debug("REMOVING COMMANDS FROM GUILD")

            tree.clear_commands(guild=guild)

            for removedCommand in await tree.sync(guild=guild):
                logger.warning(f"removed {removedCommand.name} from server")

            # to get some color in the console
            logger.critical("removed commands from tree")
        else:
            try:
                logger.debug("trying to sync commands to guild")

                await tree.sync(guild=guild)
            except Exception as error:
                logger.error("commands couldn't be synced to guild!", exc_info=error)
            else:
                logger.info("commands synced to guild")

        # https://stackoverflow.com/questions/59126137/how-to-change-activity-of-a-discord-py-bot
        try:
            logger.debug("trying to set activity")

            if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name="auf deine Aktivität")
                )
            else:
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name="ob alles läuft")
                )
        except Exception as e:
            logger.warning("activity couldn't be set", exc_info=e)
        else:
            logger.info("activity set")

        await self.fetch_guild(GuildId.GUILD_KVGG.value)

        logger.debug("fetched guild")

        global backgroundServices

        # backgroundServices = BackgroundServices(self) # TODO enable again

    async def on_message(self, message: discord.Message):
        """
        Checks for new Quote

        :param message:
        :return:
        """
        logger.debug("received new message")

        if not message.author.bot and not message.content == "":
            if not message.channel:
                logger.debug("no channel")

                return

            try:
                await self.processUserInput.raiseMessageCounter(message.author, message.channel)
                await self.quotesManager.checkForNewQuote(message)
                await self.memeService.checkIfMemeAndPrepareReactions(message)
            except Exception as error:
                logger.error("failure to run message functions", exc_info=error)

        # empty message but on server
        elif message.attachments and message.content == "" and not isinstance(message.channel, DMChannel):
            await self.memeService.checkIfMemeAndPrepareReactions(message)

        # empty message but as DM
        elif message.attachments and message.content == "" and isinstance(message.channel, DMChannel):
            await self.soundboardService.manageDirectMessage(message)

        else:
            logger.debug("message empty or from a bot")

    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        """
        Calls the QuotesManager to check if a quote was deleted

        :param message: RawMessageDeleteEvent
        :return:
        """
        logger.debug("received deleted message")

        await self.quotesManager.deleteQuote(message)

    async def on_raw_message_edit(self, message: RawMessageUpdateEvent):
        """
        Calls the QuotesManager to check if a quote was edited

        :param message: RawMessageUpdateEvent
        :return:
        """
        logger.debug("received edited message")

        await self.quotesManager.updateQuote(message)
        await self.memeService.updateMeme(message)

    async def on_voice_state_update(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        """
        Calls the VoiceStateUpdateService on a voice event

        :param member: Member that caused the event
        :param voiceStateBefore: VoiceState before the member triggered the event
        :param voiceStateAfter: VoiceState after the member triggered the event
        :return:
        """
        logger.debug("received voice state update")

        await self.voiceStateUpdateService.handleVoiceStateUpdate(member, voiceStateBefore, voiceStateAfter)


# reads the token
token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)

# sets the intents of the client to the default ones
intents = discord.Intents.all()

# instantiates the client
client = MyClient(intents=intents)

# create the command service
commandService = CommandService(client)

# creates the command tree
tree = app_commands.CommandTree(client)

backgroundServices = None

"""ANSWER JOKE"""


@tree.command(name="joke",
              description="Antwortet dir einen (lustigen) Witz!",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(kategorie=[
    Choice(name="Flachwitze", value="flachwitze"),
    Choice(name="Lehrerwitze", value="lehrerwitze"),
    Choice(name="Programmierwitze", value="programmierwitze"),
    Choice(name="Scherzfragen", value="scherzfragen"),
    Choice(name="Chuck Norris-Witze", value="chuck-norris-witze"),
    Choice(name="Antiwitze", value="antiwitze"),
    Choice(name="Blondinenwitze", value="blondinenwitze"),
    Choice(name="Schulwitze", value="schulwitze"),
])
async def answerJoke(interaction: discord.interactions.Interaction, kategorie: Choice[str]):
    """
    Calls the answer joke function in ProcessUserInput from this interaction

    :param interaction: Interaction object from this call
    :param kategorie: Optional choice of the category
    :return:
    """
    await commandService.runCommand(Commands.JOKE,
                                    interaction,
                                    category=kategorie.value)


"""MOVE ALL USERS"""


@tree.command(name="move",
              description="Moved alle User aus deinem Channel in den von dir angegebenen.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def moveUsers(interaction: discord.Interaction, channel: VoiceChannel):
    """
    Calls the move users from ProcessUserInput from this function

    :param interaction: Interaction object of the call
    :param channel: Destination channel
    :return:
    """
    await commandService.runCommand(Commands.MOVE, interaction, channel=channel, member=interaction.user)


"""ANSWER QUOTE"""


@tree.command(name="zitat",
              description="Antwortet die ein zufälliges Zitat aus unserem Zitat-Channel.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def answerQuote(interaction: discord.Interaction):
    """
    Calls the answer quote function from QuotesManager from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await commandService.runCommand(Commands.QUOTE, interaction, member=interaction.user)


"""ANSWER TIME / STREAMTIME / UNITIME"""


@tree.command(name="zeit",
              description="Frage die Online-, Stream- oder Uni-Zeit an!",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(zeit=[
    Choice(name="Online-Zeit", value="online"),
    Choice(name="Stream-Zeit", value="stream"),
    Choice(name="Uni-Zeit", value="uni"),
])
@app_commands.describe(zeit="Wähle die Zeit aus!")
@app_commands.describe(user="Tagge den User von dem du den Counter wissen möchtest!")
@app_commands.describe(zeit_hinzufuegen="Ändere den Wert eines Counter um den gegebenen Wert.")
async def answerTimes(interaction: discord.Interaction, zeit: Choice[str], user: Member, zeit_hinzufuegen: int = None):
    """
    Calls the access time function in ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :param zeit: Chosen time to look / edit
    :param user: Tagged user to access time from
    :param zeit_hinzufuegen: Optional parameter for Admins and Mods
    :return:
    """
    await commandService.runCommand(Commands.TIME,
                                    interaction,
                                    timeName=zeit.value,
                                    user=user,
                                    member=interaction.user,
                                    param=zeit_hinzufuegen)


"""NAME COUNTER"""


async def listCounters(interaction: discord.Interaction, current: str) -> list[Choice[str]]:
    choices = []

    try:
        database = Database_Old()
    except Exception as error:
        logger.error("couldn't create database connection", exc_info=error)
    else:
        query = "SELECT name, description FROM counter LIMIT 25"

        if not (counters := database.fetchAllResults(query)):
            logger.error("couldn't fetch any counters from database")

            return choices

        for counter in counters:
            name = counter['name']

            if current.lower() == "" or current.lower() in name.lower():
                choices.append(Choice(name=(name.capitalize() + " - " + counter['description'])[:100], value=name))
    finally:
        return choices


@tree.command(name='counter',
              description="Frag einen beliebigen Counter von einem User an.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.autocomplete(counter=listCounters)
@app_commands.describe(counter="Wähle den Name-Counter aus!")
@app_commands.describe(user="Tagge den User von dem du den Counter wissen möchtest!")
@app_commands.describe(counter_hinzufuegen="Ändere den Wert eines Counter um den gegebenen Wert.")
async def counter(interaction: discord.Interaction, counter: str, user: Member,
                  counter_hinzufuegen: int = None):
    """
    Calls the access name counter with the correct counter

    :param interaction: Interaction object of the call
    :param counter: Name of the chosen counter
    :param user: Tagged user to get information from
    :param counter_hinzufuegen: Optional parameter for Admins and Mods
    :return:
    """
    await commandService.runCommand(Commands.COUNTER,
                                    interaction,
                                    counterName=counter,
                                    requestedUser=user,
                                    requestingMember=interaction.user,
                                    param=counter_hinzufuegen, )


@tree.command(name='create_counter',
              description="Erstelle einen neuen Counter für alle.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(name="Name des neuen Counters.")
@app_commands.describe(description="Beschreibung des neuen Counters.")
@app_commands.describe(voiceline="TTS für den Counter. "
                                 "Mit {name} wird der Name des Users automatisch an der Stelle eingefügt.")
async def createNewCounter(interaction: discord.Interaction, name: str, description: str, voiceline: str = None):
    await commandService.runCommand(Commands.CREATE_COUNTER,
                                    interaction,
                                    member=interaction.user,
                                    name=name,
                                    description=description,
                                    voiceLine=voiceline,
                                    )


@tree.command(name='list_counters',
              description="Listet alle aktuell vorhandenen Counter auf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def listCounters(interaction: discord.Interaction):
    await commandService.runCommand(Commands.LIST_COUNTERS,
                                    interaction)


"""MANAGE WHATSAPP SETTINGS"""


@tree.command(name="whatsapp",
              description="Lässt dich deine Benachrichtigungseinstellungen ändern.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(typ=[
    Choice(name="Gaming", value="Gaming"),
    Choice(name="Uni", value="Uni"),
])
@app_commands.describe(typ="Kategorie der Nachrichten")
@app_commands.choices(aktion=[
    Choice(name="join", value="join"),
    Choice(name="leave", value="leave"),
])
@app_commands.describe(aktion="Benachrichtigungskategorie")
@app_commands.choices(einstellung=[
    Choice(name="an", value="on"),
    Choice(name="aus", value="off"),
])
@app_commands.describe(einstellung="Einstellung")
async def manageWhatsAppSettings(interaction: discord.Interaction, typ: Choice[str], aktion: Choice[str],
                                 einstellung: Choice[str]):
    """
    Calls the manage whatsapp settings from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :param typ: Type of the whatsapp messages
    :param aktion: Action for the type of messages
    :param einstellung: Switch on or off
    :return:
    """
    await commandService.runCommand(Commands.WHATSAPP,
                                    interaction,
                                    member=interaction.user,
                                    type=typ.value,
                                    action=aktion.value,
                                    switch=einstellung.value)


"""SEND LEADERBOARD"""


@tree.command(name="leaderboard",
              description="Listet dir unsere Bestenliste auf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def sendLeaderboard(interaction: discord.Interaction):
    """
    Calls the send leaderboard from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await commandService.runCommand(Commands.LEADERBOARD,
                                    interaction,
                                    member=interaction.user, )


"""SEND REGISTRATION"""

# @tree.command(name="registration",
#               description="Sendet dir einen Link um einen Account auf unserer Website erstellen zu können.",
#               guild=discord.Object(id=GuildId.GUILD_KVGG.value))
# async def sendRegistration(interaction: discord.Interaction):
#     """
#     Calls the send registration from ProcessUserInput from this interaction
#
#     :param interaction: Interaction object of the call
#     :return:
#     """
#     await commandService.runCommand(Commands.REGISTRATION, interaction, member=interaction.user)


"""XP SPIN"""


@tree.command(name="xp_spin",
              description="XP-Spin alle " + str(ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value) + " Tage.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def spinForXpBoost(interaction: discord.Interaction):
    """
    Calls the Xp-Boost spin from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await commandService.runCommand(Commands.XP_SPIN, interaction, member=interaction.user)


"""XP INVENTORY"""


@tree.command(name="xp_inventory",
              description="Listet dir dein XP-Boost Inventory auf oder wähle welche zum Benutzen.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(action=[
    Choice(name="auflisten", value="list"),
    Choice(name="benutzen", value="use"),
])
@app_commands.describe(action="Wähle die Aktion die du ausführen möchtest!")
@app_commands.describe(nummer="Wähle einen XP-Boost in Zeile x oder mit 'all' alle!")
async def handleXpInventory(interaction: discord.Interaction, action: Choice[str], nummer: str = None):
    """
    Calls the handle inventory from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :param action: Action that will be performed which is listing all boosts or use some
    :param nummer: Optional row number to choose a Xp-Boost
    :return:
    """
    await commandService.runCommand(Commands.XP_INVENTORY,
                                    interaction,
                                    member=interaction.user,
                                    action=action.value,
                                    row=nummer)


"""HANDLE XP REQUEST"""


@tree.command(name="xp",
              description="Gibt dir die XP eines Benutzers wieder.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
async def handleXpRequest(interaction: discord.Interaction, user: Member):
    """
    Calls the XP request from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :param user: Entered user to read XP from
    :return:
    """
    await commandService.runCommand(Commands.XP, interaction, member=interaction.user, user=user)


"""NOTIFICATIONS"""


@tree.command(name="notifications",
              description="Lässt dich deine Benachrichtigungen einstellen.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(kategorie=[
    Choice(name=NotificationType.DOUBLE_XP_SETTING_NAME.value, value=NotificationType.DOUBLE_XP.value),
    Choice(name=NotificationType.WELCOME_BACK_SETTING_NAME.value, value=NotificationType.WELCOME_BACK.value),
    Choice(name=NotificationType.NOTIFICATION_SETTING_NAME.value, value=NotificationType.NOTIFICATION.value),
    Choice(name=NotificationType.QUEST_SETTING_NAME.value, value=NotificationType.QUEST.value),
    Choice(name=NotificationType.XP_INVENTORY_SETTING_NAME.value, value=NotificationType.XP_INVENTORY.value),
    Choice(name=NotificationType.STATUS_SETTING_NAME.value, value=NotificationType.STATUS.value),
    Choice(name=NotificationType.RETROSPECT_SETTING_NAME.value, value=NotificationType.RETROSPECT.value),
    Choice(name=NotificationType.XP_SPIN_SETTING_NAME.value, value=NotificationType.XP_SPIN.value),
])
@app_commands.describe(kategorie="Wähle deine Nachrichten-Kategorie")
@app_commands.choices(action=[
    Choice(name="an", value="on"),
    Choice(name="aus", value="off"),
])
@app_commands.describe(action="Wähle deine Einstellung")
async def handleNotificationSettings(interaction: discord.Interaction, kategorie: Choice[str], action: Choice[str]):
    """
    Lets the member change their notification settings, such as double-xp-weekend or welcome back message

    :param interaction: Interaction from discord
    :param kategorie: Category of the notification
    :param action: On or off switch
    :return:
    """
    await commandService.runCommand(Commands.NOTIFICATION_SETTING,
                                    interaction,
                                    member=interaction.user,
                                    kind=kategorie.value,
                                    setting=1 if action.value == "on" else 0)


"""FELIX TIMER"""


@tree.command(name="felix-timer",
              description="Lässt dich einen Felix-Timer für einen User starten / stoppen",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(action=[
    Choice(name="start", value="start"),
    Choice(name="stop", value="stop"),
])
@app_commands.describe(action="Wähle eine Aktion aus!")
@app_commands.describe(user="Wähle einen User aus!")
@app_commands.describe(
    zeit="Optionale Uhrzeit oder Zeit ab jetzt in Minuten wenn du einen Felix-Timer starten möchtest"
)
async def handleFelixTimer(interaction: discord.Interaction, user: Member, action: Choice[str], zeit: str = None):
    await commandService.runCommand(Commands.FELIX_TIMER,
                                    interaction,
                                    member=interaction.user,
                                    user=user,
                                    action=action.value,
                                    time=zeit)


"""WHATSAPP SUSPEND SETTING"""


@tree.command(name="whatsapp_suspend_settings",
              description="Stelle einen Zeitraum ein in dem du keine WhatsApp-Nachrichten bekommen möchtest",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(day=[
    Choice(name="Montag", value="1"),
    Choice(name="Dienstag", value="2"),
    Choice(name="Mittwoch", value="3"),
    Choice(name="Donnerstag", value="4"),
    Choice(name="Freitag", value="5"),
    Choice(name="Samstag", value="6"),
    Choice(name="Sonntag", value="7"),
])
@app_commands.describe(start="Wähle die Startzeit, z.B. 09:08")
@app_commands.describe(end="Wähle die Endzeit, z.B. 09:08")
async def handleWhatsappSuspendSetting(interaction: discord.Interaction, day: Choice[str], start: str, end: str):
    await commandService.runCommand(Commands.WHATSAPP_SUSPEND_SETTINGS,
                                    interaction,
                                    member=interaction.user,
                                    weekday=day,
                                    start=start,
                                    end=end)


@tree.command(name="reset_message_suspend_setting",
              description="Wähle einen Tag um deine Suspend-Einstellung zurückzustellen",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value),
              )
@app_commands.choices(day=[
    Choice(name="Montag", value="1"),
    Choice(name="Dienstag", value="2"),
    Choice(name="Mittwoch", value="3"),
    Choice(name="Donnerstag", value="4"),
    Choice(name="Freitag", value="5"),
    Choice(name="Samstag", value="6"),
    Choice(name="Sonntag", value="7"),
])
async def resetWhatsAppSuspendSetting(interaction: discord.Interaction, day: Choice[str]):
    await commandService.runCommand(Commands.RESET_WHATSAPP_SUSPEND_SETTINGS,
                                    interaction,
                                    member=interaction.user,
                                    weekday=day)


@tree.command(name="list_message_suspend_settings",
              description="Listet dir deine Suspend-Zeiten auf",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def listSuspendSettings(interaction: discord.Interaction):
    await commandService.runCommand(Commands.LIST_WHATSAPP_SUSPEND_SETTINGS,
                                    interaction,
                                    member=interaction.user)


"""WEATHER"""


@tree.command(name="weather",
              description="Frag das Wetter von einem Ort in Deutschland an",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(stadt="Stadt / Ort in Deutschland")
async def getWeather(interaction: discord.interactions.Interaction, stadt: str):
    await commandService.runCommand(Commands.WEATHER, interaction, city=stadt)


"""CURRENCY"""


@tree.command(name="currency_converter",
              description="Konvertiere eine Währung in die andere",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(von="Startwährung: dreistelliger Währungscode, z.B. 'USD'")
@app_commands.describe(nach="Zielwährung: dreistelliger Währungscode, z.B. 'EUR'")
@app_commands.describe(betrag="Kommabeträge: 320,59")
async def convertCurrency(interaction: discord.interactions.Interaction, von: str, nach: str, betrag: float):
    await commandService.runCommand(Commands.CURRENCY_CONVERTER,
                                    interaction,
                                    have=von,
                                    want=nach,
                                    amount=betrag)


"""QR-CODE"""


@tree.command(name="qrcode",
              description="Dein Text als QRCode",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def generateQRCode(ctx: discord.interactions.Interaction, text: str):
    """
    Creates a QR-Code from the given text

    :param ctx: Interaction by discord
    :param text: Text that will be converted into a QR-Code
    :return:
    """
    logger.debug("received command qrcode: text = %s, by %d" % (text, ctx.user.id))

    await commandService.runCommand(Commands.QRCODE, ctx, text=text)


"""REMINDER"""


@tree.command(name="remind_me",
              description="Erstelle eine persönliche Erinnerung",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.choices(art_der_zeit=[
    Choice(name="Minuten", value="minutes"),
    Choice(name="Stunden", value="hours"),
    Choice(name="Tage", value="days"),
])
@app_commands.choices(auch_whatsapp=[
    Choice(name="ja", value="yes"),
])
@app_commands.describe(auch_whatsapp="wenn du den Reminder auch als Whatsapp erhalten möchtest")
@app_commands.describe(reminder="Inhalt des Reminders")
@app_commands.describe(art_der_zeit="Zeiteinheit deines Wertes für die Wiederholung")
@app_commands.describe(wiederhole_alle="Zahl an Zeiteinheiten - bitte benutze auch 'art_der_zeit'! Deaktivieren durch "
                                       "Löschen des Reminders.")
@app_commands.describe(datum="Datum der Erinnerung, z.B. 09.09.2023")
@app_commands.describe(uhrzeit="Uhrzeit der Erinnerung, z.B. 09:09")
async def createReminder(ctx: discord.interactions.Interaction,
                         reminder: str,
                         datum: str,
                         uhrzeit: str,
                         wiederhole_alle: int = None,
                         art_der_zeit: Choice[str] = None,
                         auch_whatsapp: Choice[str] = None):
    """
    Creates a Reminder for the given time

    :param wiederhole_alle:
    :param uhrzeit:
    :param datum:
    :param auch_whatsapp:
    :param ctx: Interaction from Discord
    :param reminder: Content of a reminder
    :param art_der_zeit: Time scope
    :return:
    """
    await commandService.runCommand(Commands.CREATE_REMINDER,
                                    ctx,
                                    member=ctx.user,
                                    content=reminder,
                                    date=datum,
                                    time=uhrzeit,
                                    whatsapp=auch_whatsapp.value if auch_whatsapp else None,
                                    repeatTime=wiederhole_alle if wiederhole_alle else None,
                                    repeatType=art_der_zeit.value if art_der_zeit else None, )


@tree.command(name="list_reminders",
              description="Listet dir deine Reminders auf",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def listReminders(ctx: discord.interactions.Interaction):
    """
    Calls the listing of the users reminders

    :param ctx:
    :return:
    """
    await commandService.runCommand(Commands.LIST_REMINDERS,
                                    ctx,
                                    member=ctx.user)


@tree.command(name="delete_reminder",
              description="Lösche einen aktiven Reminder",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def deleteReminder(ctx: discord.interactions.Interaction, id: int):
    """
    Calls the deletion of one reminder

    :param ctx:
    :param id:
    :return:
    """
    await commandService.runCommand(Commands.DELETE_REMINDER,
                                    ctx,
                                    member=ctx.user,
                                    id=id)


@tree.command(name="timer",
              description="Stellt einen Timer und erinnert dich bei Ablauf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(minuten="In wie vielen Minuten du erinnerst werden möchtest.")
@app_commands.describe(name="Name des Timers")
async def createTimer(ctx: discord.interactions.Interaction, name: str, minuten: int):
    """
    Creates a timer in the reminder database.
    """
    await commandService.runCommand(Commands.CREATE_TIMER,
                                    ctx,
                                    member=ctx.user,
                                    name=name,
                                    minutes=minuten, )


"""PLAY SOUND"""


async def getPersonalSounds(interaction: discord.Interaction, current: str) -> list[Choice[str]]:
    """
    Autocompletes the current input from the user with his / her own uploaded sounds

    :param interaction: Interaction
    :param current: Currently inputted string
    :return:
    """
    member = interaction.user.id
    basepath = os.path.dirname(__file__)
    path = os.path.abspath(os.path.join(basepath, "..", "..", f"{basepath}/data/sounds/{member}/"))
    choices = []
    # cap return to 25 results to comply to discord autocomplete limitations
    counter = 0

    for file in os.listdir(path):
        if counter == 25:
            break

        if not file[-4:] == '.mp3':
            continue

        if not current.lower() in file.lower():
            continue

        choices.append(Choice(name=file, value=file))
        counter += 1

    return choices


@tree.command(name="play",
              description="Spielt einen Sound aus deinen hochgeladenen Sounds.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.autocomplete(sound=getPersonalSounds)
async def playSound(ctx: discord.interactions.Interaction, sound: str):
    """
    Plays the given sound.

    :param ctx: Interaction
    :param sound: Chosen sound
    :return:
    """
    await commandService.runCommand(Commands.PLAY_SOUND,
                                    ctx,
                                    ctx=ctx,
                                    member=ctx.user,
                                    sound=sound, )


@tree.command(name="stop",
              description="Stoppt die Ausgabe des Bots wenn er sich in deinem Channel befindet.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def stopSound(ctx: discord.interactions.Interaction):
    await commandService.runCommand(Commands.STOP_SOUND,
                                    ctx,
                                    member=ctx.user, )


@tree.command(name="list_sounds",
              description="Listet dir all deine hochgeladenen Sounds auf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def listSounds(ctx: discord.interactions.Interaction):
    """
    Lists all sounds from a user

    :param ctx:
    :return:
    """
    await commandService.runCommand(Commands.LIST_SOUNDS, ctx, ctx=ctx)


@tree.command(name="delete_sound",
              description="Lösche einen Sound aus deinen Sounds. Tipp: Liste mir '/list_sounds' deine Sounds vorher "
                          "auf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
@app_commands.describe(nummer="Sound in dieser Zeile der Auflistung wird gelöscht.")
async def deleteSound(ctx: discord.interactions.Interaction, nummer: int):
    await commandService.runCommand(Commands.DELETE_SOUND, ctx, ctx=ctx, row=nummer)


"""KNEIPE"""


@tree.command(name="kneipe",
              description="Verschiebt Paul und Rene oder zwei beliebige Member in einen eigenen Voice-Channel.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def kneipe(ctx: discord.interactions.Interaction, member_1: Member = None, member_2: Member = None):
    await commandService.runCommand(Commands.KNEIPE, ctx, member=ctx.user, member_1=member_1, member_2=member_2)


"""QUESTS"""


@tree.command(name="list_quests",
              description="Liste deine aktuellen Quests auf.",
              guild=discord.Object(id=GuildId.GUILD_KVGG.value))
async def listQuests(ctx: discord.interactions.Interaction):
    await commandService.runCommand(Commands.LIST_QUESTS, ctx, member=ctx.user)


restartTrys = 5


def run():
    """
    Starts the bot initially and restarts him six times if he crashes

    :return:
    """
    global restartTrys

    try:
        client.run(token=token, reconnect=True, log_handler=clientHandler, log_level=logging.INFO)
    except Exception as error:
        logger.critical("\n\n----BOT CRASHED----\n\n", exc_info=error)

        if restartTrys > 0:
            restartTrys -= 1

            run()
        else:
            logger.error("BOT STOPPING, 5 RESTARTS ENCOUNTERED")
            sys.exit(1)


if __name__ == '__main__':
    run()
