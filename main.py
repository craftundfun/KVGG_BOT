from __future__ import unicode_literals

import asyncio
import logging
import multiprocessing
from asyncio import sleep

import discord
import os
from discord import RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, app_commands
from discord.app_commands import Choice
from typing import List
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper import ReadParameters
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.Id.RoleId import RoleId
from src.InheritedCommands.NameCounter import ReneCounter, FelixCounter, PaulCounter, BjarneCounter, \
    OlegCounter, JjCounter, CookieCounter, CarlCounter
from src.InheritedCommands.Times import OnlineTime, StreamTime, UniversityTime
from src.Services import ExperienceService
from src.Services import ProcessUserInput, QuotesManager, VoiceStateUpdateService, BotStartUpService
from src.Services.ProcessUserInput import hasUserWantedRoles
from mutagen.mp3 import MP3


class MyClient(discord.Client):
    async def on_ready(self):
        """
        NOT THE FIRST THING TO BE EXECUTED

        Runs all (important) start scripts, such as the BotStartUpService or syncing the commands
        to the guild.

        :return:
        """
        print('Logged on as', self.user)

        botStartUpService = BotStartUpService.BotStartUpService()

        await botStartUpService.startUp(self)
        print("Users fetched and updated")

        await tree.sync(guild=discord.Object(int(GuildId.GUILD_KVGG.value)))
        print("Commands updated and uploaded")

        # https://stackoverflow.com/questions/59126137/how-to-change-activity-of-a-discord-py-bot
        await client.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="auf deine Aktivität")
        )
        print('Activity set')

    async def on_message(self, message: discord.Message):
        """
        TO BE FILLED # TODO

        :param message:
        :return:
        """

        return  # TODO
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content:
            pui = ProcessUserInput.ProcessUserInput(self)
            # try:
            await pui.processMessage(message)
            # TODO do something useful
            # except Exception as e:
            #    var = traceback.format_exc()
            #   print(var)

    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        """
        Calls the QuotesManager to check if a quote was deleted

        :param message: RawMessageDeleteEvent
        :return:
        """
        qm = QuotesManager.QuotesManager(self)

        await qm.deleteQuote(message)

    async def on_raw_message_edit(self, message: RawMessageUpdateEvent):
        """
        Calls the QuotesManager to check if a quote was edited

        :param message: RawMessageUpdateEvent
        :return:
        """
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
        vsus = VoiceStateUpdateService.VoiceStateUpdateService(self)

        await vsus.handleVoiceStateUpdate(member, voiceStateBefore, voiceStateAfter)


# reads the token
token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)
# sets the intents of the client to the default ones
intents = discord.Intents.default()

# enables the client to read messages
intents.message_content = True

# instantiates the client
client = MyClient(intents=intents)
# creates the command tree
tree = app_commands.CommandTree(client)

"""SEND LOGS"""


@tree.command(name="logs", description="Sendet die von dir gewählte Menge von Logs.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(amount=[Choice(name="1", value=1), Choice(name="5", value=5), Choice(name="10", value=10)])
async def sendLogs(interaction: discord.interactions.Interaction, amount: Choice[int]):
    """
    Calls the send logs function from ProcessUserInput from this interaction

    :param interaction: Interaction object from this call
    :param amount: Number of logs to be returned
    :return:
    """
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.sendLogs(interaction.user, amount.value)

    await interaction.response.send_message(answer)


"""ANSWER JOKE"""


@tree.command(name="joke", description="Antwortet dir einen (lustigen) Witz!",
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
async def answerJoke(interaction: discord.interactions.Interaction, kategorie: Choice[str] = None):
    """
    Calls the answer joke function in ProcessUserInput from this interaction

    :param interaction: Interaction object from this call
    :param kategorie: Optional choice of the category
    :return:
    """

    pui = ProcessUserInput.ProcessUserInput(client)
    if kategorie is None:
        category = "flachwitze"
    else:
        category = kategorie.value
    answer = await pui.answerJoke(category)
    await interaction.response.send_message(answer)


"""MOVE ALL USERS"""


async def channel_choices(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    """
    Returns the matching autocomplete results

    :param interaction: Interaction, but gets ignored
    :param current: Current input from the user to filter autocomplete
    :return: List of Choices excluding forbidden channels  # TODO maybe change
    """
    channels = client.get_all_channels()
    voiceChannels: List[str] = []
    exclusiveChannels = [
        ChannelIdWhatsAppAndTracking.CHANNEL_STAFF.value,
        ChannelIdWhatsAppAndTracking.CHANNEL_GOLF.value,
        ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_EINS.value,
        ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_ZWEI.value,
        ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_DREI.value,
        ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_VIER.value,
    ]

    # for every channel from the guild
    for channel in channels:
        # if voice channel
        if isinstance(channel, discord.VoiceChannel):
            # if a voice channel is a "public" one
            if str(channel.id) in ChannelIdWhatsAppAndTracking.getValues():
                # if a channel is restricted for normal users check if MOD or ADMIN uses the command
                if str(channel.id) in exclusiveChannels:
                    if hasUserWantedRoles(interaction.user, RoleId.ADMIN, RoleId.MOD):
                        voiceChannels.append(channel.name)
                else:
                    voiceChannels.append(channel.name)

    return [
        Choice(name=name, value=name) for name in voiceChannels if current.lower() in name.lower()
    ]


@tree.command(name="move", description="Moved alle User aus deinem Channel in den von dir angegebenen.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.autocomplete(channel=channel_choices)
async def moveUsers(interaction: discord.Interaction, channel: str):
    """
    Calls the move users from ProcessUserInput from this function

    :param interaction: Interaction object of the call
    :param channel: Destination channel
    :return:
    """
    answer = await ProcessUserInput.ProcessUserInput(client).moveUsers(channel, interaction.user)
    await interaction.response.send_message(answer)


"""ANSWER QUOTE"""


@tree.command(name="zitat", description="Antwortet die ein zufälliges Zitat aus unserem Zitat-Channel.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def answerQuote(interaction: discord.Interaction):
    """
    Calls the answer quote fuction from QuotesManager from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    answer = await QuotesManager.QuotesManager(client).answerQuote()

    if answer:
        await interaction.response.send_message(answer)
    else:
        await interaction.response.send_message("Es ist etwas schief gelaufen!")


"""ANSWER TIME / STREAMTIME / UNITIME"""


@tree.command(name="zeit", description="Frage die Online-, Stream- oder Uni-Zeit an!",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(zeit=[
    Choice(name="Online-Zeit", value="online"),
    Choice(name="Stream-Zeit", value="stream"),
    Choice(name="Uni-Zeit", value="uni"),
])
@app_commands.describe(zeit="Wähle die Zeit aus!")
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
@app_commands.describe(param="Ändere den Wert eines Counter um den gegebenen Wert.")
async def answerTimes(interaction: discord.Interaction, zeit: Choice[str], user: str, param: str = None):
    """
    Calls the access time function in ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :param zeit: Chosen time to look / edit
    :param user: Tagged user to access time from
    :param param: Optional parameter for Admins and Mods
    :return:
    """

    time = None

    if zeit.value == "online":
        time = OnlineTime.OnlineTime()
    elif zeit.value == "stream":
        time = StreamTime.StreamTime()
    elif zeit.value == "uni":
        time = UniversityTime.UniversityTime()

    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.accessTimeAndEdit(time, user, interaction.user, param)

    await interaction.response.send_message(answer)


"""NAME COUNTER"""


@tree.command(name='counter', description="Frag einen beliebigen Counter von einem User an.",
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
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
@app_commands.describe(param="Ändere den Wert eines Counter um den gegebenen Wert.")
async def counter(interaction: discord.Interaction, counter: Choice[str], user: str, param: str = None):
    """
    Calls the access name counter with the correct counter

    :param interaction: Interaction object of the call
    :param counter: Name of the chosen counter
    :param user: Tagged user to get information from
    :param param: Optional parameter for Admins and Mods
    :return:
    """
    nameCounter = None

    if "Bjarne" == counter.value:
        nameCounter = BjarneCounter.BjarneCounter()
    elif "Carl" == counter.value:
        nameCounter = CarlCounter.CarlCounter()
    elif "Cookie" == counter.value:
        nameCounter = CookieCounter.CookieCounter()
    elif "Felix" == counter.value:
        nameCounter = FelixCounter.FelixCounter()  # TODO felix timer
    elif "JJ" == counter.value:
        nameCounter = JjCounter.JjCounter()
    elif "Oleg" == counter.value:
        nameCounter = OlegCounter.OlegCounter()
    elif "Paul" == counter.value:
        nameCounter = PaulCounter.PaulCounter()
    elif "Rene" == counter.value:
        nameCounter = ReneCounter.ReneCounter()

    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.accessNameCounterAndEdit(nameCounter, user, interaction.user, param)

    await interaction.response.send_message(answer)


"""MANAGE WHATSAPP SETTINGS"""


@tree.command(name="whatsapp", description="Lässt dich deine Benachrichtigunseinstellungen ändern.",
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
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.manageWhatsAppSettings(interaction.user, type.value, action.value, switch.value)

    await interaction.response.send_message(answer)


"""SEND LEADERBOARD"""


@tree.command(name="leaderboard", description="Listet dir unsere Bestenliste auf.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def sendLeaderboard(interaction: discord.Interaction):
    """
    Calls the send leaderboard from ProcessUserInput from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.sendLeaderboard()

    await interaction.response.send_message(answer)


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
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.sendRegistrationLink(interaction.user)

    await interaction.response.send_message(answer)


"""XP SPIN"""


@tree.command(name="xp_spin", description="XP-Spin alle " + str(
    ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value) + " Tage.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def spinForXpBoost(interaction: discord.Interaction):
    """
    Calls the Xp-Boost spin from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :return:
    """
    xpService = ExperienceService.ExperienceService(client)
    answer = await xpService.spinForXpBoost(interaction.user)

    await interaction.response.send_message(answer)


"""XP INVENTORY"""


@tree.command(name="xp_inventory", description="Listet dir dein XP-Boost Inventory auf oder wähle welche zum Benutzen.",
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
    :param zeile: Optional row number to choose an Xp-Boost
    :return:
    """
    xpService = ExperienceService.ExperienceService(client)
    answer = await xpService.handleXpInventory(interaction.user, action.value, zeile)

    await interaction.response.send_message(answer)


"""HANDLE XP REQUEST"""


@tree.command(name="xp", description="Gibt dir die XP eines Benutzers wieder.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
async def handleXpRequest(interaction: discord.Interaction, user: str):
    """
    Calls the XP request from ExperienceService from this interaction

    :param interaction: Interaction object of the call
    :param user: Entered user to read XP from
    :return:
    """
    xpService = ExperienceService.ExperienceService(client)
    answer = await xpService.handleXpRequest(userTag=user)

    await interaction.response.send_message(answer)


"""XP LEADERBOARD"""


@tree.command(name="xp_leaderboard", description="Listet dir unsere XP-Bestenliste auf.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def getXpLeaderboard(interaction: discord.Interaction):
    exp = ExperienceService.ExperienceService(client)
    answer = exp.sendXpLeaderboard()
    await interaction.response.send_message(answer)


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

# starts the client
client.run(token)
