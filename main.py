from __future__ import unicode_literals

import asyncio
import logging.handlers
import os
import sys
import time
import traceback
from typing import List, Tuple

from discord import RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, app_commands, Webhook, \
    VoiceChannel
import discord
import nest_asyncio
from discord import RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, app_commands
from discord.app_commands import Choice, commands

from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper import ReadParameters
from src.Helper.CustomFormatter import CustomFormatter
from src.Helper.CustomFormatterFile import CustomFormatterFile
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import ReneCounter, FelixCounter, PaulCounter, BjarneCounter, \
    OlegCounter, JjCounter, CookieCounter, CarlCounter
from src.InheritedCommands.Times import OnlineTime, StreamTime, UniversityTime
from src.Services import ApiServices
from src.Services import BackgroundServices
from src.Services import ExperienceService, WhatsAppHelper
from src.Services import ProcessUserInput, QuotesManager, VoiceStateUpdateService, DatabaseRefreshService
from src.Services.EmailService import send_exception_mail
from src.Services.ProcessUserInput import hasUserWantedRoles
from src.Services.CommandService import CommandService, Commands

os.environ['TZ'] = 'Europe/Berlin'
time.tzset()
nest_asyncio.apply()

logger = logging.getLogger("KVGG_BOT")

# creates up to 5 log files, every day at midnight a new one is created - if 5 was reached logs will be overwritten
fileHandler = logging.handlers.TimedRotatingFileHandler(filename='Logs/log.txt', when='midnight', backupCount=5)
fileHandler.setFormatter(CustomFormatterFile())

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


@DeprecationWarning
def thread_wrapper(func, args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(func(args))
    loop.close()


@DeprecationWarning
async def some_thread(client: discord.Client):
    """
    JUST FOR TESTING PURPOSES

    :param client:
    :return:
    """
    while True:
        # await client.fetch_guild(int(GuildId.GUILD_KVGG.value))
        # await client.fetch_user(555430341389844500)
        for mem in client.get_all_members():
            if mem.id == 555430341389844500:
                member = mem
                break

        print(member.status)
        await asyncio.sleep(2)


class MyClient(discord.Client):
    backgroundServices = None

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

    async def on_ready(self):
        """
        NOT THE FIRST THING TO BE EXECUTED

        Runs all (important) start scripts, such as the BotStartUpService or syncing the commands
        to the guild.

        :return:
        """
        logger.info("Logged in as: " + str(self.user))

        botStartUpService = DatabaseRefreshService.DatabaseRefreshService(self)

        await botStartUpService.startUp()
        logger.info("Users fetched and updated")

        if len(sys.argv) > 1 and sys.argv[1] == "-clean":
            logger.debug("Removing commands from guild")
            commandsTree = []

            for command in tree.walk_commands(guild=discord.Object(id=int(GuildId.GUILD_KVGG.value))):
                if isinstance(command, commands.Command):
                    commandsTree.append(command)

            for command in commandsTree:
                tree.remove_command(command.name, guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))

            await tree.sync(guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
            logger.critical("Removed commands from tree. You can end the bot now!")
        else:
            try:
                logger.debug("Trying to sync commands to guild")
                await tree.sync(guild=discord.Object(int(GuildId.GUILD_KVGG.value)))
            except Exception as e:
                logger.critical("Commands couldn't be synced to Guild!", exc_info=e)
            else:
                logger.info("Commands synced to Guild")

        # https://stackoverflow.com/questions/59126137/how-to-change-activity-of-a-discord-py-bot
        try:
            logger.debug("Trying to set activity")
            if os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False):
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name="auf deine Aktivität")
                )
            else:
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name=", dass alles läuft")
                )
        except Exception as e:
            logger.warning("Activity couldn't be set!", exc_info=e)
        else:
            logger.info("Activity set")

        await self.fetch_guild(int(GuildId.GUILD_KVGG.value))
        logger.debug("Fetched guild")

        global backgroundServices

        backgroundServices = BackgroundServices.BackgroundServices(self)

    async def on_message(self, message: discord.Message):
        """
        Checks for new Quote

        :param message:
        :return:
        """
        logger.debug("received new message")

        if not message.author.bot and not message.content == "":
            pui = ProcessUserInput.ProcessUserInput(self)

            pui.raiseMessageCounter(message.author, message.channel)

            qm = QuotesManager.QuotesManager(self)

            await qm.checkForNewQuote(message)
        else:
            logger.debug("message empty or from a bot")

    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        """
        Calls the QuotesManager to check if a quote was deleted

        :param message: RawMessageDeleteEvent
        :return:
        """
        logger.debug("received deleted message")

        qm = QuotesManager.QuotesManager(self)

        await qm.deleteQuote(message)

    async def on_raw_message_edit(self, message: RawMessageUpdateEvent):
        """
        Calls the QuotesManager to check if a quote was edited

        :param message: RawMessageUpdateEvent
        :return:
        """
        logger.debug("received edited message")

        qm = QuotesManager.QuotesManager(self)

        await qm.updateQuote(message)

    async def on_voice_state_update(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        """
        Calls the VoiceStateUpdateService on a voice event

        :param member: Member that caused the event
        :param voiceStateBefore: VoiceState before the member triggered the event
        :param voiceStateAfter: VoiceState after the member triggered the event
        :return:
        """
        logger.debug("received voicestate update")

        vsus = VoiceStateUpdateService.VoiceStateUpdateService(self)

        await vsus.handleVoiceStateUpdate(member, voiceStateBefore, voiceStateAfter)


# reads the token
token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)
# sets the intents of the client to the default ones
intents = discord.Intents.default()

# enables the client to read messages
intents.message_content = True
intents.members = True

# instantiates the client
client = MyClient(intents=intents)
# creates the command tree
tree = app_commands.CommandTree(client)
backgroundServices = None

"""SEND LOGS"""


@tree.command(name="logs",
              description="Sendet die von dir gewählte Menge von Logs.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(amount=[Choice(name="1", value=1), Choice(name="5", value=5), Choice(name="10", value=10)])
async def sendLogs(interaction: discord.interactions.Interaction, amount: Choice[int]):
    """
    Calls the send logs function from ProcessUserInput from this interaction

    :param interaction: Interaction object from this call
    :param amount: Number of logs to be returned
    :return:
    """
    await CommandService(client).runCommand(Commands.LOGS, interaction, member=interaction.user, amount=amount.value)


"""ANSWER JOKE"""


@tree.command(name="joke",
              description="Antwortet dir einen (lustigen) Witz!",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
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
    await CommandService(client).runCommand(Commands.JOKE,
                                            interaction,
                                            member=interaction.user,
                                            category=kategorie.value)


"""MOVE ALL USERS"""


@tree.command(name="move",
              description="Moved alle User aus deinem Channel in den von dir angegebenen.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def moveUsers(interaction: discord.Interaction, channel: VoiceChannel):
    """
    Calls the move users from ProcessUserInput from this function

    :param interaction: Interaction object of the call
    :param channel: Destination channel
    :return:
    """
    await CommandService(client).runCommand(Commands.MOVE, interaction, channel=channel, member=interaction.user)


"""ANSWER QUOTE"""


@tree.command(name="zitat",
              description="Antwortet die ein zufälliges Zitat aus unserem Zitat-Channel.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def answerQuote(interaction: discord.Interaction):
    """
    Calls the answer quote fuction from QuotesManager from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await CommandService(client).runCommand(Commands.QUOTE, interaction, member=interaction.user)


"""ANSWER TIME / STREAMTIME / UNITIME"""


@tree.command(name="zeit",
              description="Frage die Online-, Stream- oder Uni-Zeit an!",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(zeit=[
    Choice(name="Online-Zeit", value="online"),
    Choice(name="Stream-Zeit", value="stream"),
    Choice(name="Uni-Zeit", value="uni"),
])
@app_commands.describe(zeit="Wähle die Zeit aus!")
@app_commands.describe(user="Tagge den User von dem du den Counter wissen möchtest!")
@app_commands.describe(param="Ändere den Wert eines Counter um den gegebenen Wert.")
async def answerTimes(interaction: discord.Interaction, zeit: Choice[str], user: Member, param: int = None):
    """
    Calls the access time function in ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :param zeit: Chosen time to look / edit
    :param user: Tagged user to access time from
    :param param: Optional parameter for Admins and Mods
    :return:
    """
    await CommandService(client).runCommand(Commands.TIME,
                                            interaction,
                                            timeName=zeit.value,
                                            user=user,
                                            member=interaction.user,
                                            param=param)


"""NAME COUNTER"""


@tree.command(name='counter',
              description="Frag einen beliebigen Counter von einem User an.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(counter=[
    Choice(name="Bjarne", value="Bjarne"),
    Choice(name="Carl", value="Carl"),
    Choice(name="Cookie", value="Cookie"),
    Choice(name="Felix", value="Felix"),
    Choice(name="JJ", value="JJ"),
    Choice(name="Oleg", value="Oleg"),
    Choice(name="Paul", value="Paul"),
    Choice(name="Rene", value="Rene"),
])
@app_commands.describe(counter="Wähle den Name-Counter aus!")
@app_commands.describe(user="Tagge den User von dem du den Counter wissen möchtest!")
@app_commands.describe(param="Ändere den Wert eines Counter um den gegebenen Wert.")
async def counter(interaction: discord.Interaction, counter: Choice[str], user: Member, param: int = None):
    """
    Calls the access name counter with the correct counter

    :param interaction: Interaction object of the call
    :param counter: Name of the chosen counter
    :param user: Tagged user to get information from
    :param param: Optional parameter for Admins and Mods
    :return:
    """
    await CommandService(client).runCommand(Commands.COUNTER,
                                            interaction,
                                            counterName=counter.value,
                                            user=user,
                                            member=interaction.user,
                                            param=param)


"""MANAGE WHATSAPP SETTINGS"""


@tree.command(name="whatsapp",
              description="Lässt dich deine Benachrichtigunseinstellungen ändern.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(type=[
    Choice(name="Gaming", value="Gaming"),
    Choice(name="Uni", value="Uni"),
])
@app_commands.describe(type="Kategorie der Nachrichten")
@app_commands.choices(action=[
    Choice(name="join", value="join"),
    Choice(name="leave", value="leave"),
])
@app_commands.describe(action="Benachrichtigungskategorie")
@app_commands.choices(switch=[
    Choice(name="on", value="on"),
    Choice(name="off", value="off"),
])
@app_commands.describe(switch="Einstellung")
async def manageWhatsAppSettings(interaction: discord.Interaction, type: Choice[str], action: Choice[str],
                                 switch: Choice[str]):
    """
    Calls the manage whatsapp settings from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :param type: Type of the whatsapp messages
    :param action: Action for the type of messages
    :param switch: Switch on or off
    :return:
    """
    await CommandService(client).runCommand(Commands.WHATSAPP,
                                            interaction,
                                            member=interaction.user,
                                            type=type.value,
                                            action=action.value,
                                            switch=switch.value)


"""SEND LEADERBOARD"""


@tree.command(name="leaderboard",
              description="Listet dir unsere Bestenliste auf.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def sendLeaderboard(interaction: discord.Interaction):
    """
    Calls the send leaderboard from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await CommandService(client).runCommand(Commands.LEADERBOARD, interaction, member=interaction.user)


"""SEND REGISTRATION"""


@tree.command(name="registration",
              description="Sendet dir einen Link um einen Account auf unserer Website erstellen zu können.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def sendRegistration(interaction: discord.Interaction):
    """
    Calls the send registration from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await CommandService(client).runCommand(Commands.REGISTRATION, interaction, member=interaction.user)


"""XP SPIN"""


@tree.command(name="xp_spin",
              description="XP-Spin alle " + str(ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value) + " Tage.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def spinForXpBoost(interaction: discord.Interaction):
    """
    Calls the Xp-Boost spin from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    await CommandService(client).runCommand(Commands.XP_SPIN, interaction, member=interaction.user)


"""XP INVENTORY"""


@tree.command(name="xp_inventory",
              description="Listet dir dein XP-Boost Inventory auf oder wähle welche zum Benutzen.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(action=[
    Choice(name="list", value="list"),
    Choice(name="use", value="use"),
])
@app_commands.describe(action="Wähle die Aktion die du ausführen möchtest!")
@app_commands.describe(zeile="Wähle einen XP-Boost in Zeile x oder mit 'all' alle!")
async def handleXpInventory(interaction: discord.Interaction, action: Choice[str], zeile: str = None):
    """
    Calls the handle inventory from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :param action: Action that will be performed which is listing all boosts or use some
    :param zeile: Optional row number to choose a Xp-Boost
    :return:
    """
    await CommandService(client).runCommand(Commands.XP_INVENTORY,
                                            interaction,
                                            member=interaction.user,
                                            action=action.value,
                                            row=zeile)


"""HANDLE XP REQUEST"""


@tree.command(name="xp",
              description="Gibt dir die XP eines Benutzers wieder.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
async def handleXpRequest(interaction: discord.Interaction, user: Member):
    """
    Calls the XP request from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :param user: Entered user to read XP from
    :return:
    """
    await CommandService(client).runCommand(Commands.XP, interaction, member=interaction.user, user=user)


"""XP LEADERBOARD"""


@tree.command(name="xp_leaderboard",
              description="Listet dir unsere XP-Bestenliste auf.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def getXpLeaderboard(interaction: discord.Interaction):
    await CommandService(client).runCommand(Commands.XP_LEADERBOARD, interaction, member=interaction.user)


"""XP NOTIFICATION"""


@tree.command(name="notifications",
              description="Lässt dich deine Benachrichtigungen einstellen.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(category=[
    Choice(name="xp", value="xp"),
    Choice(name="welcome", value="welcome"),
])
@app_commands.describe(category="Wähle deine Nachrichten-Kategorie")
@app_commands.choices(action=[
    Choice(name="on", value="on"),
    Choice(name="off", value="off"),
])
@app_commands.describe(action="Wähle deine Einstellung")
async def handleNotificationSettings(interaction: discord.Interaction, category: Choice[str], action: Choice[str]):
    """
    Lets the member change their notification settings, such as double-xp-weekend or welcome back message

    :param interaction: Interaction from discord
    :param category: Category of the notification
    :param action: On or off switch
    :return:
    """
    logger.debug("received command notification: category = %s, action = %s, by %d" % (category.value, action.value,
                                                                                       interaction.user.id))

    if category.value == "xp":
        await CommandService(client).runCommand(Commands.NOTIFICATIONS_XP,
                                                interaction,
                                                member=interaction.user,
                                                setting=action.value)
    elif category.value == "welcome":
        await CommandService(client).runCommand(Commands.NOTIFICATIONS_BACK,
                                                interaction,
                                                member=interaction.user,
                                                setting=True if action.value == "on" else False)
    else:
        logger.warning("User reached unreachable code!")


"""FELIX TIMER"""


@tree.command(name="felix-timer",
              description="Lässt dich einen Felix-Timer für einen User starten / stoppen",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
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
    await CommandService(client).runCommand(Commands.FELIX_TIMER,
                                            interaction,
                                            member=interaction.user,
                                            user=user,
                                            action=action.value,
                                            time=zeit)


"""OVERWRITE COGS"""


@tree.command(name="disable_cogs",
              description="Stellt die Achievement-Loops aus",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def shutdownCogs(interaction: discord.Interaction):
    """
    Disable the background services of the bot

    :param interaction: Interaction by discord
    :return:
    """
    logger.warning("received command disable_cogs by %d" % (interaction.user.id))

    member = interaction.user

    if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
        await interaction.response.send_message("Du hast dazu keine Berechtigung!")

    if backgroundServices:
        backgroundServices.cog_unload()
        logger.warning("Cogs were ended!")
        await interaction.response.send_message("Alle Cogs wurden beendet!")
    else:
        await interaction.response.send_message("Es gab keine Loops zum beenden!")


@tree.command(name="enable_cogs",
              description="Stellt die Achievement-Loops an",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def startCogs(interaction: discord.Interaction):
    """
    Starts the background services of the bot

    :param interaction: Interaction by discordf
    :return:
    """
    logger.warning("received command enable_cogs, by %d" % (interaction.user.id))

    member = interaction.user

    if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
        await interaction.response.send_message("Du hast dazu keine Berechtigung!")

    if backgroundServices:
        await backgroundServices.cog_load()
        logger.warning("Cogs were started!")
        await interaction.response.send_message("Alle Cogs wurden gestartet!")
    else:
        await interaction.response.send_message("Es gab keine Loops zum starten!")


"""WHATSAPP SUSPEND SETTING"""


@tree.command(name="whatsapp_suspend_settings",
              description="Stelle einen Zeitraum ein in dem du keine WhatsApp-Nachrichten bekommen möchtest",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
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
    await CommandService(client).runCommand(Commands.WHATSAPP_SUSPEND_SETTINGS,
                                            interaction,
                                            member=interaction.user,
                                            weekday=day,
                                            start=start,
                                            end=end)


@tree.command(name="reset_message_suspend_setting",
              description="Wähle einen Tag um deine Suspend-Einstellung zurückzustellen",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)),
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
    await CommandService(client).runCommand(Commands.RESET_WHATSAPP_SUSPEND_SETTINGS,
                                            interaction,
                                            member=interaction.user,
                                            weekday=day)


@tree.command(name="list_message_suspend_settings",
              description="Listet dir deine Suspend-Zeiten auf",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def listSuspendSettings(interaction: discord.Interaction):
    await CommandService(client).runCommand(Commands.LIST_WHATSAPP_SUSPEND_SETTINGS,
                                            interaction,
                                            member=interaction.user)


"""WEATHER"""


@tree.command(name="weather",
              description="Frag das Wetter von einem Ort in Deutschland an",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.describe(stadt="Stadt / Ort in Deutschland")
async def getWeather(interaction: discord.interactions.Interaction, stadt: str):
    await CommandService(client).runCommand(Commands.WEATHER, interaction, city=stadt)


"""CURRENCY"""


@tree.command(name="currency_converter",
              description="Konvertiere eine Währung in die andere",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.describe(von="Startwährung: dreistelliger Währungscode, z.B. 'USD'")
@app_commands.describe(nach="Zielwährung: dreistelliger Währungscode, z.B. 'EUR'")
@app_commands.describe(betrag="Kommabeträge: 320,59")
async def convertCurrency(interaction: discord.interactions.Interaction, von: str, nach: str, betrag: float):
    await CommandService(client).runCommand(Commands.CURRENCY_CONVERTER,
                                            interaction,
                                            have=von,
                                            want=nach,
                                            amount=betrag)


"""QR-CODE"""


@tree.command(name="qrcode",
              description="Dein Text als QRCode",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def generateQRCode(ctx: discord.interactions.Interaction, text: str):
    """
    Creates a QR-Code from the given text

    :param ctx: Interaction by discord
    :param text: Text that will be converted into a QR-Code
    :return:
    """
    logger.debug("received command qrcode: text = %s, by %d" % (text, ctx.user.id))

    await CommandService(client).runCommand(Commands.QRCODE, ctx, text=text)


"""REMINDER"""


@tree.command(name="remind_me",
              description="Erstelle eine persönliche Erinnerung",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(art_der_zeit=[
    Choice(name="Minuten", value="minutes"),
    Choice(name="Stunden", value="hours"),
    Choice(name="Tage", value="days"),
])
@app_commands.choices(auch_whatsapp=[
    Choice(name="ja", value="yes"),
])
@app_commands.describe(auch_whatsapp="wenn du den Reminder auch als Whatsapp erhalten möchtest")
@app_commands.choices(wiederholen=[
    Choice(name="ja", value="yes"),
])
@app_commands.describe(wiederholen="wenn der Reminder nach der Zeit jedes Mal erneut ausgeführt werden soll - " \
                                   "stoppen durch Löschen des Reminders")
@app_commands.describe(reminder="Inhalt des Reminders")
@app_commands.describe(art_der_zeit="Zeitintervall")
async def createReminder(ctx: discord.interactions.Interaction,
                         reminder: str,
                         art_der_zeit: Choice[str],
                         dauer: int,
                         auch_whatsapp: Choice[str] = None,
                         wiederholen: Choice[str] = None):
    """
    Creates a Reminder for the given time

    :param auch_whatsapp:
    :param wiederholen:
    :param ctx: Interaction from Discord
    :param reminder: Content of a reminder
    :param art_der_zeit: Time scope
    :param dauer: Duration
    :return:
    """
    await CommandService(client).runCommand(Commands.CREATE_REMINDER,
                                            ctx,
                                            member=ctx.user,
                                            content=reminder,
                                            timeType=art_der_zeit.value,
                                            duration=dauer,
                                            whatsapp=auch_whatsapp.value if auch_whatsapp else None,
                                            repeat=wiederholen.value if wiederholen else None, )


@tree.command(name="list_reminders",
              description="Listet dir deine Reminders auf",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def listReminders(ctx: discord.interactions.Interaction):
    """
    Calls the listing of the users reminders

    :param ctx:
    :return:
    """
    await CommandService(client).runCommand(Commands.LIST_REMINDERS, ctx, member=ctx.user)


@tree.command(name="delete_reminder",
              description="Lösche einen aktiven Reminder",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def deleteReminder(ctx: discord.interactions.Interaction, id: int):
    """
    Calls the deletion of one reminder

    :param ctx:
    :param id:
    :return:
    """
    await CommandService(client).runCommand(Commands.DELETE_REMINDER, ctx, member=ctx.user, id=id)


# FUCK YOU


"""
@tree.command(name="beta-feature", description="Just dont use it",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def beta(ctx: discord.interactions.Interaction, src: str):
    channel: discord.VoiceChannel = ctx.guild.get_channel(int(ChannelIdWhatsAppAndTracking.CHANNEL_STAFF.value))
    await channel.connect()
    # await sleep(1)
    voice_client = ctx.guild.voice_client
    # await voice_client.connect(reconnect=False, timeout=5)
    if voice_client.is_playing():
        voice_client.stop()
    # audio = MP3(new_file)
    voice_client.play(discord.FFmpegPCMAudio(source='./f.mp3'))
    # voice_client.stop()
    # await sleep(audio.info.length)
    if voice_client.is_connected():
        # await voice_client.disconnect()
        print('disconnected')
        pass

    out_file = None

"""

restartTrys = 5


def run():
    """
    Starts the bot initially and restarts him 6 times if he crashes

    :return:
    """
    global restartTrys

    try:
        client.run(token=token, reconnect=True)
    except Exception as e:
        logger.critical("\n\n----BOT CRASHED----\n\n", exc_info=e)

        send_exception_mail(traceback.format_exc())

        if restartTrys > 0:
            restartTrys -= 1

            run()
        else:
            logger.critical("BOT STOPPING, 5 RESTARTS ENCOUNTERED")
            sys.exit(1)


if __name__ == '__main__':
    run()
