import traceback
from signal import SIGINT, signal

import discord
import mysql.connector
from discord import Message, RawMessageDeleteEvent, RawMessageUpdateEvent, VoiceState, Member, User
from src.Helper import ReadParameters as rp
from src.Helper import ReadParameters
from src.Services import ProcessUserInput, QuotesManager, VoiceStateUpdateService, BotStartUpService
from src.Helper.ReadParameters import Parameters as parameters
from src.Repository.DiscordUserRepository import getDiscordUser


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

        print('Logged on as', self.user)

        # https://stackoverflow.com/questions/59126137/how-to-change-activity-of-a-discord-py-bot
        await client.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="auf deine Aktivität")
        )
        print('Activity set!')

    async def on_message(self, message):

        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content:
            pui = ProcessUserInput.ProcessUserInput(self)
            try:
                await pui.processMessage(message)
            # TODO do something useful
            except Exception as e:
                var = traceback.format_exc()
                print(var)

    # TODO close Connector
    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        qm = QuotesManager.QuotesManager(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            )
        )
        qm.deleteQuote(message, self)

    async def on_raw_message_edit(self, message: RawMessageUpdateEvent):
        qm = QuotesManager.QuotesManager(
            mysql.connector.connect(
                user=rp.getParameter(parameters.USER),
                password=rp.getParameter(parameters.PASSWORD),
                host=rp.getParameter(parameters.HOST),
                database=rp.getParameter(parameters.NAME),
            )
        )
        await qm.updateQuote(message, self)

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

client.run(token)
