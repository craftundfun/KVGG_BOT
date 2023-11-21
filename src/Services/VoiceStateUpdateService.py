from __future__ import annotations

import logging
from datetime import datetime

from discord import Member, VoiceState, Client

from src.Helper.WriteSaveQuery import writeSaveQuery
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.ChannelService import ChannelService
from src.Services.Database import Database
from src.Services.LogService import Events, LogService
from src.Services.NotificationService import NotificationService
from src.Services.QuestService import QuestService, QuestType
from src.Services.WhatsAppHelper import WhatsAppHelper

logger = logging.getLogger("KVGG_BOT")


class VoiceStateUpdateService:
    """
    Handles every VoiceState and keeps the database up to date
    """

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client
        self.waHelper = WhatsAppHelper(self.client)
        self.logService = LogService(self.client)

    async def handleVoiceStateUpdate(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        logger.debug("%s raised a VoiceStateUpdate" % member.name)

        if not member:
            logger.debug("member was not a member")

            return
        elif member.bot:
            logger.debug("member was a bot")

            return

        dcUserDb = getDiscordUser(member)

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser for %s!" % member.name)

            return

        # user joined channel
        if not voiceStateBefore.channel and voiceStateAfter.channel:
            logger.debug("%s joined channel" % member.name)

            dcUserDb['channel_id'] = voiceStateAfter.channel.id
            dcUserDb['joined_at'] = datetime.now()

            # if user joined with (full) mute
            if voiceStateAfter.self_mute or voiceStateAfter.mute:
                dcUserDb['muted_at'] = datetime.now()
            elif not voiceStateAfter.self_mute and not voiceStateAfter.mute:
                dcUserDb['muted_at'] = None

            if voiceStateAfter.self_deaf or voiceStateAfter.deaf:
                dcUserDb['full_muted_at'] = datetime.now()
            elif not voiceStateAfter.self_deaf and not voiceStateAfter.self_deaf:
                dcUserDb['full_muted_at'] = None

            dcUserDb['started_stream_at'] = None
            dcUserDb['started_webcam_at'] = None

            try:
                notificationService = NotificationService(self.client)

                await notificationService.runNotificationsForMember(member, dcUserDb)
            except ConnectionError as error:
                logger.error("failure to start NotificationService", exc_info=error)
            except Exception as error:
                logger.error("a problem occurred in runNotificationsForMember", exc_info=error)

            try:
                felixCounter = FelixCounter()

                await felixCounter.checkFelixCounterAndSendStopMessage(member, dcUserDb)
            except ConnectionError as error:
                logger.error("failure to start FelixCounter", exc_info=error)
            except Exception as error:
                logger.error("a problem occurred in checkFelixCounterAndSendStopMessage", exc_info=error)

            # save user so a whatsapp message can be sent properly
            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOnlineNotification(member, voiceStateAfter)

            try:
                channelService = ChannelService(self.client)

                # move is the last step to avoid channel confusion
                await channelService.checkChannelForMoving(member)
            except ConnectionError as error:
                logger.error("failure to start ChannelService", exc_info=error)
            except Exception as error:
                logger.error("a problem occurred in checkChannelForMoving", exc_info=error)

            # create new quests and check the progress of existing ones
            try:
                questService = QuestService(self.client)

                await questService.checkQuestsForJoinedMember(member)
                await questService.addProgressToQuest(member, QuestType.DAYS_ONLINE)
                await questService.addProgressToQuest(member, QuestType.ONLINE_STREAK)
            except ConnectionError as error:
                logger.error("failure to start QuestService", exc_info=error)
            except Exception as error:
                logger.error("a problem occurred in checkQuestsForJoinedMember", exc_info=error)

            try:
                await self.logService.sendLog(member, (voiceStateBefore, voiceStateAfter), Events.JOINED_VOICE_CHAT)
            except Exception as error:
                logger.error("an error occurred while running logService", exc_info=error)

        # user changed channel or changed status
        elif voiceStateBefore.channel and voiceStateAfter.channel:
            logger.debug("member changes status or voice channel")

            # status changed
            if voiceStateBefore.channel == voiceStateAfter.channel:
                logger.debug("%s changed status" % member.name)

                now = datetime.now()

                # if a user is mute
                if voiceStateAfter.self_mute or voiceStateAfter.mute:
                    dcUserDb['muted_at'] = now
                elif not voiceStateAfter.self_mute and not voiceStateAfter.mute:
                    dcUserDb['muted_at'] = None

                # if a user is full mute
                if voiceStateAfter.self_deaf or voiceStateAfter.deaf:
                    dcUserDb['full_muted_at'] = now
                elif not voiceStateAfter.self_deaf and not voiceStateAfter.deaf:
                    dcUserDb['full_muted_at'] = None

                # if user started stream
                if not voiceStateBefore.self_stream and voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = now
                elif voiceStateBefore.self_stream and not voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = None

                # if user started webcam
                if not voiceStateBefore.self_video and voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = now
                elif voiceStateBefore.self_video and not voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = None

                dcUserDb['username'] = member.display_name

                self.__saveDiscordUser(dcUserDb)
            # channel changed
            else:
                logger.debug("%s changed channel" % member.name)

                dcUserDb['channel_id'] = voiceStateAfter.channel.id

                self.__saveDiscordUser(dcUserDb)
                self.waHelper.switchChannelFromOutstandingMessages(dcUserDb, voiceStateAfter.channel.name)

                await ChannelService.manageKneipe(voiceStateBefore.channel)

                try:
                    await self.logService.sendLog(member, (voiceStateBefore, voiceStateAfter),
                                                  Events.SWITCHED_VOICE_CHANNEL)
                except Exception as error:
                    logger.error("an error occurred while running logService", exc_info=error)

        # user left channel
        elif voiceStateBefore.channel and not voiceStateAfter.channel:
            logger.debug("%s left channel" % member.name)
            self.waHelper.sendOfflineNotification(dcUserDb, voiceStateBefore, member)

            dcUserDb['channel_id'] = None
            dcUserDb['joined_at'] = None
            dcUserDb['muted_at'] = None
            dcUserDb['full_muted_at'] = None
            dcUserDb['started_stream_at'] = None
            dcUserDb['started_webcam_at'] = None
            dcUserDb['last_online'] = datetime.now()

            self.__saveDiscordUser(dcUserDb)

            await ChannelService.manageKneipe(voiceStateBefore.channel)

            try:
                await self.logService.sendLog(member, (voiceStateBefore, voiceStateAfter), Events.LEFT_VOICE_CHANNEL)
            except Exception as error:
                logger.error("an error occurred while running logService", exc_info=error)
        else:
            logger.warning("unexpected voice state update from %s" % member.name)

    def __saveDiscordUser(self, dcUserDb: dict):
        """
        Saves the given DiscordUser to our database

        :param dcUserDb: DiscordUser to save
        :return:
        """
        try:
            database = Database()
        except ConnectionError as error:
            logger.error("couldn't establish database connection", exc_info=error)
        else:
            query, nones = writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            if not database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save DiscordUser to database")
            else:
                logger.debug("updated %s" % dcUserDb['username'])
