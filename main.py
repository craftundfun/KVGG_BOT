from signal import SIGINT, signal

import discord
import mysql.connector
from discord import Message, RawMessageDeleteEvent, RawMessageUpdateEvent
from src.Helper import ReadParameters as rp
from src.Helper import ReadParameters
from src.Services import ProcessUserInput, QuotesManager
from src.Helper.ReadParameters import Parameters as parameters


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):

        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content:
            pui = ProcessUserInput.ProcessUserInput(self)
            await pui.processMessage(message)

    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        print("delete: " + str(message.cached_message.content))

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

    async def on_bulk_message_delete(self, message):
        print("bulk: " + str(message.content))


token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)
intents = discord.Intents.default()

intents.message_content = True

client = MyClient(intents=intents)

client.run(token)
