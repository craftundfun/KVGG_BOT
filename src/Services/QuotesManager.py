import random

import discord
from discord import Message, RawMessageUpdateEvent
from mysql.connector import MySQLConnection

from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Id.ChannelId import ChannelId


class QuotesManager:

    # TODO get discord client in constructor
    def __init__(self, databaseConnection: MySQLConnection):
        self.databaseConnection = databaseConnection

    async def answerQuote(self, message: Message):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT quote FROM quotes"

            cursor.execute(query)

            data = cursor.fetchall()
            quotes = [quote[0] for quote in data]

        await message.reply(quotes[random.randint(0, len(quotes) - 1)])

    def checkForNewQuote(self, message: Message, client: discord.Client):
        channel = self.getQuotesChannel(client)

        if channel is not None and (channel.id == message.channel.id):
            with self.databaseConnection.cursor() as cursor:
                query = "INSERT INTO quotes (quote, message_external_id) VALUES (%s, %s)"
                cursor.execute(query, (message.content, message.id,))
                self.databaseConnection.commit()

    async def updateQuote(self, message: RawMessageUpdateEvent, client: discord.Client):
        channel = self.getQuotesChannel(client)

        if channel is not None and channel.id == message.channel_id:
            with self.databaseConnection.cursor() as cursor:
                query = "SELECT * FROM quotes WHERE message_external_id = %s"

                cursor.execute(query, (message.message_id,))

                data = cursor.fetchone()

                if not data:
                    return

                quote = dict(zip(cursor.column_names, data))
                quote['quote'] = message.data['content']
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'quotes',
                    quote['id'],
                    quote,
                )

                cursor.execute(query, nones)
                self.databaseConnection.commit()

                authorId = message.data['author']['id']

                if authorId:
                    author = await client.get_guild(438689788585967616).fetch_member(416967436617777163)

                    if not author.dm_channel:
                        await author.create_dm()

                        # check if dm_channel was really created
                        if not author.dm_channel:
                            return

                    await author.dm_channel.send("Dein überarbeitetes Zitat wurde gespeichert!")

    def getQuotesChannel(self, client: discord.Client):
        return client.get_guild(int(GuildId.GUILD_KVGG.value)).get_channel(int(ChannelId.CHANNEL_QUOTES.value))
