import logging
from datetime import datetime

import dateutil.relativedelta
from discord import Message, Client, RawMessageUpdateEvent, RawMessageDeleteEvent, Member
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Meme.Entity.Meme import Meme
from src.Id.ChannelId import ChannelId
from src.Manager.DatabaseManager import getSession
from src.Manager.NotificationManager import NotificationService
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

        if not (session := getSession()):
            return

        if not (dcUserDb := getDiscordUser(message.author, session)):
            logger.error(f"couldn't fetch DiscordUser for {message.author.display_name} from database")

        insertQuery = insert(Meme).values(message_id=message.id,
                                          discord_id=dcUserDb.id,
                                          created_at=datetime.now(),
                                          media_link=message.attachments[0].url, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't insert Meme into database", exc_info=error)
            session.rollback()

            await self.notificationService.sendStatusReport(message.author,
                                                            "Es gab einen Fehler dein Meme zu speichern! "
                                                            "Bitte lade es später noch einmal hoch.")
            return
        else:
            logger.debug("saved new meme to database")
        finally:
            session.close()

        await self.notificationService.sendStatusReport(message.author,
                                                        "Dein Meme wurde für den monatlichen Contest eingetragen!", )
        await self.questService.addProgressToQuest(message.author, QuestType.MEME_COUNT)

    async def changeLikeCounterOfMeme(self, message: Message, memberWhoLiked: Member | None):
        """
        Updates the counter of likes in the corresponding database field.

        :param message: Message that was reacted to
        :param memberWhoLiked: Member who liked the meme, but only if he added a like / dislike
        """
        if message.channel.id != ChannelId.CHANNEL_MEMES.value:
            return

        if not (session := getSession()):
            return

        # noinspection PyTypeChecker
        getQuery = select(Meme).where(Meme.message_id == message.id)

        try:
            meme = session.scalars(getQuery).one()
        except NoResultFound:
            logger.debug(f"no meme with id {message.id} found in database")
            session.close()

            return
        except Exception as error:
            logger.error("couldn't fetch meme from database", exc_info=error)
            session.close()

            return

        likesBefore = meme.likes
        upvotes = 0
        downvotes = 0

        for reaction in message.reactions:
            if reaction.emoji == self.UPVOTE:
                upvotes = reaction.count
            elif reaction.emoji == self.DOWNVOTE:
                downvotes = reaction.count
            else:
                logger.warning(f"unknown reaction found: {reaction.emoji} - ignoring")

                continue

        # noinspection PyTypeChecker
        updateQuery = update(Meme).where(Meme.message_id == message.id).values(likes=upvotes - downvotes)

        try:
            session.execute(updateQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't update {meme} in database", exc_info=error)
            session.rollback()
        else:
            logger.debug(f"updated {meme} to database")

            # dont sent likes from bots to bots
            if memberWhoLiked:
                if memberWhoLiked.bot:
                    return

            notification = (
                f"{f'<@{memberWhoLiked.id}> ({memberWhoLiked.display_name})' if memberWhoLiked else 'Jemand'} "
                f"hat folgendes deiner Memes "
                f"{'geliked' if memberWhoLiked and likesBefore < (upvotes - downvotes) else 'disliked'}: "
                f"{message.jump_url} "
                f"! Dein Meme hat nun {upvotes - downvotes} Likes!"
            )

            if memberWhoLiked != message.author:
                await self.notificationService.sendMemeLikesNotification(message.author, notification)

            if memberWhoLiked != message.author:
                await (self.notificationService
                       .notifyAboutAcceptedLike(memberWhoLiked,
                                                f"Dein {'Like' if likesBefore < (upvotes - downvotes) else 'Dislike'} "
                                                f"für folgendes Meme wurde gezählt: {message.jump_url} ! "
                                                f"<@{(author := message.author).id}> ({author.display_name}) "
                                                f"wurde darüber benachrichtigt."))
            else:
                await (self.notificationService
                       .notifyAboutAcceptedLike(memberWhoLiked,
                                                f"Dein {'Like' if likesBefore < (upvotes - downvotes) else 'Dislike'} "
                                                f"wurde gezählt!"))
        finally:
            session.close()

    async def chooseWinnerAndLoser(self):
        """
        Chooses both winner and loser for meme.
        """
        if not (session := getSession()):
            logger.error("couldn't choose winner of memes, no database connection")

            return

        lastMonth = datetime.now() - dateutil.relativedelta.relativedelta(months=1)
        sinceTime = lastMonth.replace(hour=0, minute=0, second=0, microsecond=0)

        if not (channel := self.client.get_channel(ChannelId.CHANNEL_MEMES.value)):
            logger.error("couldn't fetch channel to get message")

            return

        await self._chooseLoser(session, sinceTime, channel)
        await self._chooseWinner(session, sinceTime, channel)

    async def _chooseWinner(self, session: Session, sinceTime: datetime, channel, offset: int = 0):
        """
        Chooses a winner for the last month, notifies, pins and grants an XP-Boost.

        :param session: Database instance
        :param sinceTime: Timestamp of the earliest meme to take in consideration, usually one month ago
        :param channel: Meme-Channel
        :param offset: Offset in the database results, increase if we couldn't get a message previously
        """
        getQuery = (select(Meme)
                    .where(Meme.created_at > sinceTime,
                           Meme.deleted_at.is_(None))
                    .order_by(Meme.likes.desc())
                    .limit(1)
                    .offset(offset))

        try:
            meme = session.scalars(getQuery).one()
        except NoResultFound:
            logger.error("no meme found in database")

            return
        except Exception as error:
            logger.error("couldn't fetch meme from database", exc_info=error)

            return

        if not meme:
            logger.error("no meme found in database")

            return

        try:
            message = await channel.fetch_message(meme.message_id)
        except Exception as error:
            logger.warning("couldn't fetch message from channel, trying next one", exc_info=error)

            await self._chooseWinner(session, sinceTime, channel, offset + 1)

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

        # noinspection PyTypeChecker
        updateQuery = update(Meme).where(Meme.id == meme.id).values(winner=True)

        try:
            session.execute(updateQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't update meme to database", exc_info=error)
            session.rollback()
        finally:
            session.close()

    async def _chooseLoser(self, session: Session, sinceTime: datetime, channel, offset: int = 0):
        """
        Chooses a loser for the last month, notifies and grants an XP-Boost.
        :param session: Database instance
        :param sinceTime: Timestamp of the earliest meme to take in consideration, usually one month ago
        :param channel: Meme-Channel
        :param offset: Offset in the database results, increase if we couldn't get a message previously
        """
        getQuery = (select(Meme)
                    .where(Meme.created_at > sinceTime)
                    .order_by(Meme.likes)
                    .limit(1)
                    .offset(offset))

        try:
            meme = session.scalars(getQuery).one()
        except NoResultFound:
            logger.error("no meme found in database")

            return
        except Exception as error:
            logger.error("couldn't fetch meme from database", exc_info=error)

            return

        if not meme:
            logger.error("no meme found in database")

            return

        try:
            message = await channel.fetch_message(meme.message_id)
        except Exception as error:
            logger.warning("couldn't fetch message from channel, trying next one", exc_info=error)

            await self._chooseLoser(session, sinceTime, channel, offset + 1)

            return

        await message.reply(
            f":x: __**Wow {getTagStringFromId(str(message.author.id))}, dein Meme muss echt schlecht gewesen sein. "
            f"Deins ist das am schlechtesten bewertete Meme des Monats!**__ :x:\n\nAls Belohnung hast du einen genauso "
            f"schlechten XP-Boost bekommen!"
        )

        await self.experienceService.grantXpBoost(message.author, AchievementParameter.WORST_MEME_OF_THE_MONTH)
        logger.debug(f"choose meme loser and granted boost for {meme}")

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
            logger.warning("couldn't fetch message", exc_info=error)

            return

        if len(message.attachments) != 0:
            return

        if not (session := getSession()):
            return

        logger.debug(f"removing meme from {message.author.display_name}")

        # noinspection PyTypeChecker
        updateQuery = update(Meme).where(Meme.message_id == message.id).values(deleted_at=datetime.now())

        try:
            session.execute(updateQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't update meme to database", exc_info=error)
        else:
            logger.debug("set deleted_at for meme in database")

        try:
            await message.delete()
        except Exception as error:
            logger.error("couldn't delete meme from database", exc_info=error)
        else:
            logger.debug("deleted meme from channel")

        await self.notificationService.sendStatusReport(message.author,
                                                        "Dein Meme wurde wieder entfernt, da du deinen Anhang "
                                                        "gelöscht hast!")

    # noinspection PyMethodMayBeStatic
    async def deleteMeme(self, message: RawMessageDeleteEvent):
        if message.channel_id != ChannelId.CHANNEL_MEMES.value:
            return

        if not (session := getSession()):
            return

        # noinspection PyTypeChecker
        updateQuery = update(Meme).where(Meme.message_id == message.message_id).values(deleted_at=datetime.now())

        try:
            session.execute(updateQuery)
            session.commit()
        except Exception as error:
            logger.error("couldn't update meme to database", exc_info=error)
            session.rollback()
        else:
            logger.debug("updated meme in database")
        finally:
            session.close()

    async def midnightJob(self):
        if datetime.now().day != 1:
            logger.debug("not the first day of the month, skipping meme winner and loser selection")

            return

        await self.chooseWinnerAndLoser()
