import logging
from datetime import datetime

import dateutil.relativedelta
from discord import Message, Client

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.SendDM import sendDM, separator
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelId import ChannelId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import getTagStringFromId

logger = logging.getLogger("KVGG_BOT")


class MemeService:
    UPVOTE = "🔼"
    DOWNVOTE = "🔽"

    def __init__(self, client: Client):
        self.client = client
        self.experienceService = ExperienceService(self.client)

    async def checkIfMemeAndPrepareReactions(self, message: Message):
        """
        If the message is a meme, it will be saved in the database and reactions from the bot will be added.

        :param message: Message that was written
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database()

        if message.channel.id != ChannelId.CHANNEL_MEMES.value:
            return

        # only delete non-picture messages from members
        if message.content != "" and not message.attachments and not message.author.bot:
            try:
                await message.delete()
            except Exception as error:
                logger.error("couldn't delete only-text message from meme channel", exc_info=error)

            try:
                await sendDM(message.author, "Bitte sende nur Bilder in den Meme-Channel!"
                             + separator)
            except Exception as error:
                logger.error(f"couldn't send DM to {message.author}", exc_info=error)

            return

        try:
            await message.add_reaction(self.UPVOTE)
            await message.add_reaction(self.DOWNVOTE)
        except Exception as error:
            logger.error("couldn't add reaction to message", exc_info=error)
        else:
            logger.debug("added reactions to meme")

        dcUserDb = getDiscordUser(message.author, database)

        if not dcUserDb:
            logger.warning("no dcUserDb, cant save meme to database")

        query = "INSERT INTO meme (message_id, discord_id, created_at) VALUES (%s, %s, %s)"

        if not database.runQueryOnDatabase(query, (message.id, dcUserDb['id'], datetime.now(),)):
            logger.error("couldn't save meme to database")
        else:
            logger.debug("saved new meme to database")

        try:
            await sendDM(message.author, "Dein Meme wurde für den monatlichen Contest eingetragen!"
                         + separator)
        except Exception as error:
            logger.error(f"couldn't send DM to {message.author.name}", exc_info=error)

    async def changeLikeCounterOfMessage(self, message: Message):
        """
        Updates the counter of likes in the corresponding database field.

        :param message: Message that was reacted to
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database()

        query = "SELECT * FROM meme WHERE message_id = %s"

        if not (meme := database.fetchOneResult(query, (message.id,))):
            logger.warning("couldn't fetch meme from database")

            return

        upvotes = 0
        downvotes = 0

        for reaction in message.reactions:
            if reaction.emoji == self.UPVOTE:
                upvotes = reaction.count
            elif reaction.emoji == self.DOWNVOTE:
                downvotes = reaction.count
            else:
                logger.warning("unknown reaction found - ignoring")

                continue

        meme['likes'] = upvotes - downvotes

        query, nones = writeSaveQuery('meme', meme['id'], meme)

        if not database.runQueryOnDatabase(query, nones):
            logger.error("couldn't update meme to database")
        else:
            logger.debug("updated meme to database")

    async def chooseWinner(self, offset: int = 0):
        """
        Chooses a winner for the last month, notifies, pins and grants an XP-Boost.

        :param offset: Offset in the database results, increase if we couldn't get a message previously
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database()

        query = "SELECT * FROM meme WHERE created_at > %s ORDER BY likes DESC LIMIT 1 OFFSET %s"

        now = datetime.now()
        firstOfMonth = now - dateutil.relativedelta.relativedelta(month=1)
        firstOfMonthCorrectTime = firstOfMonth.replace(hour=0, minute=0, second=0, microsecond=0)

        if not (meme := database.fetchOneResult(query, (firstOfMonthCorrectTime, offset,))):
            logger.error("couldn't fetch any memes from database")

            return

        channel = self.client.get_channel(ChannelId.CHANNEL_MEMES.value)

        if not channel:
            logger.error("couldn't fetch channel to get message")

            return

        message = await channel.fetch_message(meme['message_id'])

        if not message:
            logger.error("couldn't fetch message from channel, trying next one")

            await self.chooseWinner(offset + 1)

            return

        await message.reply(
            f"__**Herzlichen Glückwunsch {getTagStringFromId(str(message.author.id))}, dein Meme war das am besten "
            f"bewertete des Monats!**__\n\nAls Belohnung hast du einen XP-Boost bekommen!"
        )

        try:
            await message.pin(reason="best meme of the month")
        except Exception as error:
            logger.error("couldn't pin meme to channel", exc_info=error)

        await self.experienceService.grantXpBoost(message.author, AchievementParameter.BEST_MEME_OF_THE_MONTH)

        logger.debug("choose meme winner and granted boost")
