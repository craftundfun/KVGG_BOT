from asyncio import sleep

import discord
import mysql.connector

from typing import List
from discord import RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, app_commands
from discord.app_commands import Choice
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper import ReadParameters
from src.Helper import ReadParameters as rp
from src.Helper.ReadParameters import Parameters as parameters
from src.Id import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId
from src.InheritedCommands.NameCounter import ReneCounter, FelixCounter, PaulCounter, BjarneCounter, \
    OlegCounter, JjCounter, CookieCounter, CarlCounter
from src.InheritedCommands.Times import OnlineTime, StreamTime, UniversityTime
from src.Services import ExperienceService
from src.Services import ProcessUserInput, QuotesManager, VoiceStateUpdateService, BotStartUpService


class MyClient(discord.Client):
    async def on_ready(self):
        # TODO manage connections better
        botStartUpService = BotStartUpService.BotStartUpService(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            )
        )
        await botStartUpService.startUp(self)
        await tree.sync(guild=discord.Object(int(GuildId.GUILD_KVGG.value)))
        print('Logged on as', self.user)

        # https://stackoverflow.com/questions/59126137/how-to-change-activity-of-a-discord-py-bot
        await client.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="auf deine Aktivität")
        )
        print('Activity set!')

    async def on_message(self, message):
        return
        print("message")
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

    # TODO close Connector
    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        qm = QuotesManager.QuotesManager(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            ),
            self,
        )
        await qm.deleteQuote(message)

    async def on_raw_message_edit(self, message: RawMessageUpdateEvent):
        qm = QuotesManager.QuotesManager(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            ),
            self,
        )
        await qm.updateQuote(message)

    async def on_voice_state_update(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        vsus = VoiceStateUpdateService.VoiceStateUpdateService(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            ),
            self,
        )
        await vsus.handleVoiceStateUpdate(member, voiceStateBefore, voiceStateAfter)


token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)
intents = discord.Intents.default()

intents.message_content = True

client = MyClient(intents=intents)
tree = app_commands.CommandTree(client)

"""SEND LOGS"""


@tree.command(name="logs", description="Sendet die von dir gewählte Menge von Logs.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.choices(amount=[Choice(name="1", value=1), Choice(name="5", value=5), Choice(name="10", value=10)])
async def sendLogs(interaction: discord.interactions.Interaction, amount: Choice[int]):
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
    pui = ProcessUserInput.ProcessUserInput(client)
    if kategorie is None:
        category = "flachwitze"
    else:
        category = kategorie.value
    answer = await pui.answerJoke(category)
    await interaction.response.send_message(answer)


"""MOVE ALL USERS"""


async def channel_choices(_: discord.Interaction, current: str) -> List[Choice[str]]:
    channels = client.get_all_channels()
    voiceChannels: List[str] = []

    for channel in channels:
        if isinstance(channel, discord.VoiceChannel):
            if str(channel.id) in ChannelIdWhatsAppAndTracking.getValues() and str(channel.id) not in [
                # ChannelIdWhatsAppAndTracking.ChannelIdWhatsAppAndTracking.CHANNEL_STAFF.value,  # TODO reinnehmen
                ChannelIdWhatsAppAndTracking.ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_EINS.value,
                ChannelIdWhatsAppAndTracking.ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_ZWEI.value,
                ChannelIdWhatsAppAndTracking.ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_DREI.value,
                ChannelIdWhatsAppAndTracking.ChannelIdWhatsAppAndTracking.CHANNEL_EVENT_VIER.value,
            ]:
                voiceChannels.append(channel.name)

    return [
        Choice(name=name, value=name) for name in voiceChannels if current.lower() in name.lower()
    ]


@tree.command(name="move", description="Moved alle User aus deinem Channel in den von dir angegebenen.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.autocomplete(channel=channel_choices)  # TODO maybe change to choise instead
async def moveUsers(interaction: discord.Interaction, channel: str):
    answer = await ProcessUserInput.ProcessUserInput(client).moveUsers(channel, interaction.user)
    await interaction.response.send_message(answer)


"""ANSWER QUOTE"""


@tree.command(name="zitat", description="Antwortet die ein zufälliges Zitat aus unserem Zitat-Channel.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def answerQuote(interaction: discord.Interaction):
    answer = await QuotesManager.QuotesManager(
        mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        ),
        client,
    ).answerQuote()

    if answer:
        await interaction.response.send_message(answer)
    else:
        await interaction.response.send_message("Es ist etwas schief gelaufen!")


"""ANSWER TIME / STREAMTIME / UNITIME"""


async def timeAutocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    times = ['online', 'stream', 'uni']

    return [
        Choice(name=time, value=time) for time in times if current.lower() in time.lower()
    ]


@tree.command(name="zeit", description="Frage die Online-, Stream- oder Uni-Zeit an!",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.autocomplete(zeit=timeAutocomplete)  # TODO choices # TODO user description # TODO param description
async def answerTimes(interaction: discord.Interaction, zeit: str, user: str, param: str = None):
    time = None

    if zeit == "online":
        time = OnlineTime.OnlineTime()
    elif zeit == "stream":
        time = StreamTime.StreamTime()
    elif zeit == "uni":
        time = UniversityTime.UniversityTime()

    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.accessTimeAndEdit(time, user, interaction.user, param)
    await interaction.response.send_message(answer)


"""NAME COUNTER"""


async def counterAutocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    counters = ['Bjarne', 'Carl', 'Cookie', 'Felix', 'JJ', 'Oleg', 'Paul', 'Rene']

    return [
        Choice(name=counter, value=counter) for counter in counters if current.lower() in counter.lower()
    ]


@tree.command(name='counter', description="Frag einen beliebigen Counter von einem User an.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.autocomplete(
    counter=counterAutocomplete)  # TODO choices, # TODO description user, # TODO param description
async def counter(interaction: discord.Interaction, counter: str, user: str, param: str = None):
    nameCounter = None

    if "Bjarne" == counter:
        nameCounter = BjarneCounter.BjarneCounter()
    elif "Carl" == counter:
        nameCounter = CarlCounter.CarlCounter()
    elif "Cookie" == counter:
        nameCounter = CookieCounter.CookieCounter()
    elif "Felix" == counter:
        nameCounter = FelixCounter.FelixCounter()  # TODO felix timer
    elif "JJ" == counter:
        nameCounter = JjCounter.JjCounter()
    elif "Oleg" == counter:
        nameCounter = OlegCounter.OlegCounter()
    elif "Paul" == counter:
        nameCounter = PaulCounter.PaulCounter()
    elif "Rene" == counter:
        nameCounter = ReneCounter.ReneCounter()

    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.accessNameCounterAndEdit(nameCounter, user, interaction.user, param)
    await interaction.response.send_message(answer)


"""MANAGE WHATSAPP SETTINGS"""


async def autocompleteWhatsAppType(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    types = ['Gaming', 'Uni']

    return [Choice(name=type, value=type) for type in types if current.lower() in type.lower()]


async def autocompleteWhatsAppAction(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    actions = ['join', 'leave']

    return [Choice(name=action, value=action) for action in actions if current.lower() in action.lower()]


async def autocompleteWhatsAppSwitch(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    switches = ['on', 'off']

    return [Choice(name=switch, value=switch) for switch in switches if current.lower() in switch.lower()]


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
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.manageWhatsAppSettings(interaction.user, type.value, action.value, switch.value)
    await interaction.response.send_message(answer)


"""SEND LEADERBOARD"""


@tree.command(name="leaderboard", description="Listet dir unsere Bestenliste auf.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def sendLeaderboard(interaction: discord.Interaction):
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.sendLeaderboard()
    await interaction.response.send_message(answer)


"""SEND REGISTRATION"""


@tree.command(name="registration",
              description="Sendet dir einen Link um einen Account auf unserer Website erstellen zu können.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def sendRegistration(interaction: discord.Interaction):
    pui = ProcessUserInput.ProcessUserInput(client)
    answer = await pui.sendRegistrationLink(interaction.user)
    await interaction.response.send_message(answer)


"""XP SPIN"""


@tree.command(name="xp_spin", description="XP-Spin alle " + str(
    ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value) + " Tage.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
async def spinForXpBoost(interaction: discord.Interaction):
    xpService = ExperienceService.ExperienceService(
        mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        ),
        client,
    )
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
    xpService = ExperienceService.ExperienceService(
        mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        ),
        client,
    )
    answer = await xpService.handleXpInventory(interaction.user, action.value, zeile)
    await interaction.response.send_message(answer)


"""HANDLE XP REQUEST"""


@tree.command(name="xp", description="Gibt dir die XP eines Benutzers wieder.",
              guild=discord.Object(id=int(GuildId.GUILD_KVGG.value)))
@app_commands.describe(user="Tagge den User von dem du die XP wissen möchtest!")
async def handleXpRequest(interaction: discord.Interaction, user: str):
    xpService = ExperienceService.ExperienceService(
        mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        ),
        client,
    )
    answer = await xpService.handleXpRequest(userTag=user)

    await interaction.response.send_message(answer)


client.run(token)
