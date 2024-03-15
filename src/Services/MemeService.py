import logging
from datetime import datetime

import dateutil.relativedelta
from discord import Message, Client, RawMessageUpdateEvent

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.ChannelId import ChannelId
from src.Manager.NotificationManager import NotificationService
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database_Old import Database_Old
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import getTagStringFromId
from src.Services.QuestService import QuestService, QuestType

logger = logging.getLogger("KVGG_BOT")


class MemeService:
    UPVOTE = "🔼"
    DOWNVOTE = "🔽"

    def __init__(self, client: Client):
        self.client = client
        self.experienceService = ExperienceService(self.client)
        self.questService = QuestService(self.client)
        self.notificationService = NotificationService(self.client)

    async def checkIfMemeAndPrepareReactions(self, message: Message):
        """
        If the message is a meme, it will be saved in the database and reactions from the bot will be added.

        :param message: Message that was written
        :raise ConnectionError: If the database connection cant be established
        """
        if message.channel.id != ChannelId.CHANNEL_MEMES.value:
            return

        # only delete non-picture messages from members
        if message.content != "" and not message.attachments and not message.author.bot:
            try:
                await message.delete()
            except Exception as error:
                logger.error("couldn't delete only-text message from meme channel", exc_info=error)

            await self.notificationService.sendStatusReport(message.author,
                                                            "Bitte sende nur Bilder in den Meme-Channel!")

            return

        try:
            await message.add_reaction(self.UPVOTE)
            await message.add_reaction(self.DOWNVOTE)
        except Exception as error:
            logger.error("couldn't add reaction to message", exc_info=error)
        else:
            logger.debug("added reactions to meme")

        database = Database_Old()
        dcUserDb = getDiscordUser(message.author, database)

        if not dcUserDb:
            logger.warning("no dcUserDb, cant save meme to database")

        query = "INSERT INTO meme (message_id, discord_id, created_at) VALUES (%s, %s, %s)"

        if not database.runQueryOnDatabase(query, (message.id, dcUserDb['id'], datetime.now(),)):
            logger.error("couldn't save meme to database")

            await self.notificationService.sendStatusReport(message.author,
                                                            "Es gab einen Fehler dein Meme zu speichern! "
                                                            "Bitte lade es später noch einmal hoch.")

            return
        else:
            logger.debug("saved new meme to database")

        await self.notificationService.sendStatusReport(message.author,
                                                        "Dein Meme wurde für den monatlichen Contest eingetragen!")
        await self.questService.addProgressToQuest(message.author, QuestType.MEME_COUNT)

    async def changeLikeCounterOfMessage(self, message: Message):
        """
        Updates the counter of likes in the corresponding database field.

        :param message: Message that was reacted to
        :raise ConnectionError: If the database connection cant be established
        """
        database = Database_Old()
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

    async def chooseWinnerAndLoser(self):
        """
        Chooses both winner and loser for meme.
        """
        database = Database_Old()
        lastMonth = datetime.now() - dateutil.relativedelta.relativedelta(months=1)
        sinceTime = lastMonth.replace(hour=0, minute=0, second=0, microsecond=0)

        if not (channel := self.client.get_channel(ChannelId.CHANNEL_MEMES.value)):
            logger.error("couldn't fetch channel to get message")

            return

        await self._chooseLoser(database, sinceTime, channel)
        await self._chooseWinner(database, sinceTime, channel)

    async def _chooseWinner(self, database: Database_Old, sinceTime: datetime, channel, offset: int = 0):
        """
        Chooses a winner for the last month, notifies, pins and grants an XP-Boost.

        :param database: Database instance
        :param sinceTime: Timestamp of the earliest meme to take in consideration, usually one month ago
        :param channel: Meme-Channel
        :param offset: Offset in the database results, increase if we couldn't get a message previously
        """
        query = ("SELECT * "
                 "FROM meme "
                 "WHERE created_at > %s "
                 "ORDER BY likes DESC "
                 "LIMIT 1 "
                 "OFFSET %s")

        if not (meme := database.fetchOneResult(query, (sinceTime, offset,))):
            logger.error("couldn't fetch any memes from database")

            return

        if not (message := await channel.fetch_message(meme['message_id'])):
            logger.error("couldn't fetch message from channel, trying next one")

            await self._chooseWinner(database, sinceTime, channel, offset + 1)

            return

        await message.reply(
            f":white_check_mark: __**Herzlichen Glückwunsch {getTagStringFromId(str(message.author.id))}, dein Meme"
            f" war das am besten bewertete des Monats!**__ :white_check_mark:\n\nAls Belohnung hast du einen XP-Boost "
            f"bekommen!"
        )

        try:
            await message.pin(reason="best meme of the month")
        except Exception as error:
            logger.error("couldn't pin meme to channel", exc_info=error)

        await self.experienceService.grantXpBoost(message.author, AchievementParameter.BEST_MEME_OF_THE_MONTH)
        logger.debug("choose meme winner and granted boost")

    async def _chooseLoser(self, database: Database_Old, sinceTime: datetime, channel, offset: int = 0):
        """
        Chooses a loser for the last month, notifies and grants an XP-Boost.
        :param database: Database instance
        :param sinceTime: Timestamp of the earliest meme to take in consideration, usually one month ago
        :param channel: Meme-Channel
        :param offset: Offset in the database results, increase if we couldn't get a message previously
        """
        query = ("SELECT * "
                 "FROM meme "
                 "WHERE created_at > %s "
                 "ORDER BY likes "
                 "LIMIT 1 "
                 "OFFSET %s")

        if not (meme := database.fetchOneResult(query, (sinceTime, offset,))):
            logger.error("couldn't fetch any memes from database")

            return

        if not (message := await channel.fetch_message(meme['message_id'])):
            logger.error("couldn't fetch message from channel, trying next one")

            await self._chooseLoser(database, sinceTime, channel, offset + 1)

            return

        await message.reply(
            f":x: __**Wow {getTagStringFromId(str(message.author.id))}, dein Meme muss echt schlecht gewesen sein. "
            f"Deins ist das am schlechtesten bewertete Meme des Monats!**__ :x:\n\nAls Belohnung hast du einen genauso "
            f"schlechten XP-Boost bekommen!"
        )

        await self.experienceService.grantXpBoost(message.author, AchievementParameter.WORST_MEME_OF_THE_MONTH)
        logger.debug("choose meme loser and granted boost")

    async def updateMeme(self, message: RawMessageUpdateEvent):
        """
        If the meme was edited to not have an attachment anymore, delete it.

        :param message: RawMessageUpdateEvent to get the updated message
        """
        if message.channel_id != ChannelId.CHANNEL_MEMES.value:
            return

        try:
            message = await self.client.get_channel(ChannelId.CHANNEL_MEMES.value).fetch_message(message.message_id)
        except Exception as error:
            logger.error("couldn't fetch message", exc_info=error)

            return

        database = Database_Old()

        if len(message.attachments) == 0:
            logger.debug(f"removing meme from {message.author.display_name}")

            query = "DELETE FROM meme WHERE message_id = %s"

            if not database.runQueryOnDatabase(query, (message.id,)):
                logger.error("couldn't delete meme")

            try:
                await message.delete()
            except Exception as error:
                logger.error("couldn't delete meme", exc_info=error)

            await self.notificationService.sendStatusReport(message.author,
                                                            "Dein Meme wurde wieder entfernt, da du deinen Anhang "
                                                            "gelöscht hast!")
