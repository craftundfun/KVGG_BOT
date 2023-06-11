import discord
import mysql.connector
from src.Helper import ReadParameters
from src.Services import ProcessUserInput


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


token = ReadParameters.getParameter(ReadParameters.Parameters.TOKEN)
print(token)
intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
print(token)
client.run(token)
