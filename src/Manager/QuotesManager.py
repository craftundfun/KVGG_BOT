from __future__ import annotations

import logging

from discord import Message, RawMessageUpdateEvent, RawMessageDeleteEvent, Client, Member
from sqlalchemy import select, func, insert, delete
from sqlalchemy.orm.exc import NoResultFound

from src.Id.ChannelId import ChannelId
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Manager.NotificationManager import NotificationService
from src.Entities.Quote.Entity.Quote import Quote

logger = logging.getLogger("KVGG_BOT")


def getQuoteChannel(client: Client):
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

    def answerQuote(self, member: Member) -> str:
        """
        Returns a random quote from our database

        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        logger.debug(f"{member.display_name} requested a quote")

        if not (session := getSession()):  # TODO outside
            return "Es gab ein Problem!"

        # let SQL fetch a random quote
        getQuery = select(Quote).order_by(func.rand()).limit(1)

        try:
            quote = session.scalars(getQuery).one()
        except Exception as error:
            logger.error("no quotes found in database", exc_info=error)

            return "Es gab ein Problem!"
        finally:
            session.close()

        logger.debug("returning random quote")

        return quote.quote

    async def checkForNewQuote(self, message: Message):
        """
        Checks if a new quote was entered in the Quotes-Channel

        :param message:
        :return:
        """
        if message.channel.id != ChannelId.CHANNEL_QUOTES.value:
            logger.debug(f"message by {message.author.display_name} was not a quote")

            return

        logger.info("quote detected")

        if not (session := getSession()):
            return

        insertQuery = insert(Quote).values(quote=message.content,
                                           message_external_id=message.id, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't insert new Quote", exc_info=error)
            session.rollback()
        else:
            logger.debug("new Quote saved to database")
            await self.notificationService.sendStatusReport(message.author,
                                                            "Dein Zitat wurde gespeichert!", )
        finally:
            session.close()

    async def updateQuote(self, message: RawMessageUpdateEvent):
        """
        Updates an existing quote if it was edited

        :param message:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if message.channel_id != ChannelId.CHANNEL_QUOTES.value:
            return

        logger.debug("quote update detected")

        if not (session := getSession()):
            return

        # noinspection PyTypeChecker
        getQuery = select(Quote).where(Quote.message_external_id == message.message_id)

        try:
            quote: Quote = session.scalars(getQuery).one()
        except NoResultFound:
            logger.error("quote update couldn't be done -> no database results")
            session.close()

            return
        else:
            quote.quote = message.data['content']

            logger.debug("updated quote")

        try:
            session.commit()
            logger.debug("saved update Quote to database")
        except Exception as error:
            logger.error("couldn't update Quote", exc_info=error)
            session.rollback()
        finally:
            session.close()

        if authorId := message.data['author']['id']:
            if not (author := self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(authorId))):
                logger.error(f"couldn't fetch author with ID: {authorId} from guild")

                return

            await self.notificationService.sendStatusReport(author, "Dein überarbeitetes Zitat wurde gespeichert!")
            logger.debug(f"notified {author.display_name} about the updated quote")

    async def deleteQuote(self, message: RawMessageDeleteEvent):
        """
        If a quote is deleted, it also gets deleted from our database

        :param message:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if message.channel_id != ChannelId.CHANNEL_QUOTES.value:
            return

        logger.debug("deleted quote detected")

        if not (session := getSession()):
            return

        # noinspection PyTypeChecker
        deleteQuery = delete(Quote).where(Quote.message_external_id == message.message_id)

        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't delete Quote", exc_info=error)
            session.rollback()
        else:
            logger.debug("successfully deleted quote from database")
        finally:
            session.close()
