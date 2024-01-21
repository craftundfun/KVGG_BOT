from __future__ import annotations

import logging
import random

from discord import Message, RawMessageUpdateEvent, RawMessageDeleteEvent, Client, Member

from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelId import ChannelId
from src.Id.GuildId import GuildId
from src.Manager.NotificationManager import NotificationService
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getQuotesChannel(client: Client):
    """
    Returns the Quotes-Channel

    :param client: Discord-Client
    :return: Channel | None - Quotes-Channel
    """
    return client.get_guild(GuildId.GUILD_KVGG.value).get_channel(ChannelId.CHANNEL_QUOTES.value)


class QuotesManager:
    """
    Manages quotes in the Qoutes-Channel
    """

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client
        self.notificationService = NotificationService(self.client)

    def answerQuote(self, member: Member) -> str | None:
        """
        Returns a random quote from our database

        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug("%s requested a quote" % member.name)

        database = Database()

        query = "SELECT quote FROM quotes"

        quotes = database.fetchAllResults(query)

        if not quotes:
            logger.critical("no qoutes were found in the database")

            return "Ich habe kein Zitat für dich :/"

        logger.debug("random quote returned")

        return quotes[random.randint(0, len(quotes) - 1)]['quote']

    async def checkForNewQuote(self, message: Message):
        """
        Checks if a new quote was entered in the Quotes-Channel

        :param message:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database()
        channel = getQuotesChannel(self.client)

        if channel is not None and (channel.id == message.channel.id):
            logger.info("quote detected")

            query = "INSERT INTO quotes (quote, message_external_id) VALUES (%s, %s)"

            if database.runQueryOnDatabase(query, (message.content, message.id,)):
                await self.notificationService.sendStatusReport(message.author,
                                                                "Dein Zitat wurde in unserer Datenbank gespeichert!")

                logger.debug("sent dm to %s" % message.author.name)

    async def updateQuote(self, message: RawMessageUpdateEvent):
        """
        Updates an existing quote if it was edited

        :param message:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        channel = getQuotesChannel(self.client)
        database = Database()

        if channel is not None and channel.id == message.channel_id:
            logger.debug("new quote detected")

            query = "SELECT * FROM quotes WHERE message_external_id = %s"

            quote = database.fetchOneResult(query, (message.message_id,))

            if not quote:
                logger.critical("quote update couldn't be fetched -> no database results")

                return

            quote['quote'] = message.data['content']
            query, nones = writeSaveQuery(
                'quotes',
                quote['id'],
                quote,
            )

            database.runQueryOnDatabase(query, nones)

            logger.debug("saved new quote to database")

            authorId = message.data['author']['id']

            if authorId:
                author = await self.client.get_guild(GuildId.GUILD_KVGG.value).fetch_member(authorId)

                if author:
                    try:
                        await self.notificationService.sendStatusReport(author,
                                                                        "Dein überarbeitetes Zitat wurde gespeichert!")

                        logger.debug("sent dm to %s" % author.name)
                    except Exception as error:
                        logger.error("couldn't send DM to %s" % author.name, exc_info=error)

    async def deleteQuote(self, message: RawMessageDeleteEvent):
        """
        If a quote is deleted, it also gets deleted from our database

        :param message:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        channel = getQuotesChannel(self.client)
        database = Database()

        if channel is not None and channel.id == message.channel_id:
            logger.debug("delete quote from database")

            query = "DELETE FROM quotes WHERE message_external_id = %s"

            database.runQueryOnDatabase(query, (message.message_id,))
