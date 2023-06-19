from __future__ import annotations

import random
import string

from discord import Message, RawMessageUpdateEvent, RawMessageDeleteEvent, Client
from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Id.ChannelId import ChannelId
from src.Helper.createNewDatabaseConnection import getDatabaseConnection


def getQuotesChannel(client: Client):
    return client.get_guild(int(GuildId.GUILD_KVGG.value)).get_channel(int(ChannelId.CHANNEL_QUOTES.value))


class QuotesManager:
    def __init__(self, client: Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    async def answerQuote(self) -> string | None:
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT quote FROM quotes"

            cursor.execute(query)

            data = cursor.fetchall()

            if not data:
                return None

            quotes = [quote[0] for quote in data]

        return quotes[random.randint(0, len(quotes) - 1)]

    async def checkForNewQuote(self, message: Message):
        channel = getQuotesChannel(self.client)

        if channel is not None and (channel.id == message.channel.id):
            with self.databaseConnection.cursor() as cursor:
                query = "INSERT INTO quotes (quote, message_external_id) VALUES (%s, %s)"

                cursor.execute(query, (message.content, message.id,))
                self.databaseConnection.commit()

            # TODO write dm in own helper
            member = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(message.author.id)

            if member.dm_channel is None:
                await member.create_dm()

            await member.dm_channel.send("Dein Zitat wurde in unserer Datenbank gespeichert!")

    async def updateQuote(self, message: RawMessageUpdateEvent):
        channel = getQuotesChannel(self.client)

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
                    author = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(authorId)

                    if not author.dm_channel:
                        await author.create_dm()

                        # check if dm_channel was really created
                        if not author.dm_channel:
                            return

                    await author.dm_channel.send("Dein überarbeitetes Zitat wurde gespeichert!")

    async def deleteQuote(self, message: RawMessageDeleteEvent):
        channel = getQuotesChannel(self.client)

        if channel is not None and channel.id == message.channel_id:
            with self.databaseConnection.cursor() as cursor:
                query = "DELETE FROM quotes WHERE message_external_id = %s"

                cursor.execute(query, (message.message_id,))
                self.databaseConnection.commit()

    def __del__(self):
        self.databaseConnection.close()
