from __future__ import annotations

import logging
from datetime import datetime

from discord import Member, VoiceState, Client
from sqlalchemy import null

from src.Helper.WriteSaveQuery import writeSaveQuery
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Manager.ChannelManager import ChannelService
from src.Manager.DatabaseManager import getSession
from src.Manager.LogManager import Events, LogService
from src.Manager.NotificationManager import NotificationService
from src.Repository.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database_Old import Database_Old
from src.Services.QuestService import QuestService, QuestType
from src.Services.WhatsAppService import WhatsAppHelper

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
        self.notificationService = NotificationService(self.client)
        self.felixCounter = FelixCounter()
        self.channelService = ChannelService(self.client)
        self.questService = QuestService(self.client)

    async def handleVoiceStateUpdate(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        """
        Handles the VoiceStateUpdate and updates the database accordingly

        :param member: Member, who raised the VoiceStateUpdate
        :param voiceStateBefore: VoiceState before the update
        :param voiceStateAfter: VoiceState after the update
        :return:
        """
        voiceStates = (voiceStateBefore, voiceStateAfter)

        logger.debug(f"{member.display_name} raised a VoiceStateUpdate")

        if not member:
            logger.debug(f"{member.display_name} was not a member")

            return
        elif member.bot:
            logger.debug(f"{member.display_name} was a bot")

            return

        if not (session := getSession()):
            return

        if not (dcUserDb := getDiscordUser(member, session)):
            logger.error(f"couldn't fetch DiscordUser for {member.display_name}")
            session.close()

            return

        async def runLogService(event: Events):
            # runs the log service, so we don't need the exception handling all the time
            try:
                await self.logService.sendLog(member, voiceStates, event)
            except Exception as e:
                logger.error("failure to run LogService", exc_info=e)

        # user joined channel
        if not voiceStateBefore.channel and voiceStateAfter.channel:
            logger.debug(f"{member.display_name} joined channel")

            dcUserDb.channel_id = str(voiceStateAfter.channel.id)
            dcUserDb.joined_at = datetime.now()

            # if user joined with (full) mute
            if voiceStateAfter.self_mute or voiceStateAfter.mute:
                dcUserDb.muted_at = datetime.now()
            elif not voiceStateAfter.self_mute and not voiceStateAfter.mute:
                dcUserDb.muted_at = null()

            if voiceStateAfter.self_deaf or voiceStateAfter.deaf:
                dcUserDb.full_muted_at = datetime.now()
            elif not voiceStateAfter.self_deaf and not voiceStateAfter.self_deaf:
                dcUserDb.full_muted_at = null()

            dcUserDb.started_stream_at = null()
            dcUserDb.started_webcam_at = null()

            try:
                await self.notificationService.runNotificationsForMember(member, dcUserDb, session)  # TODO create repository for QuestDiscordMapping
            except Exception as error:
                logger.error(f"failure while running notifications for {dcUserDb}", exc_info=error)

            try:
                await self.felixCounter.checkFelixCounterAndSendStopMessage(member, dcUserDb)
            except Exception as error:
                logger.error(f"failure while running felix timer for {dcUserDb}", exc_info=error)

            # save user so a whatsapp message can be sent properly
            try:
                session.commit()
            except Exception as error:
                logger.error(f"couldn't commit changes for {dcUserDb}", exc_info=error)
                session.close()

                return

            try:
                self.waHelper.sendOnlineNotification(dcUserDb, voiceStateAfter, session)
            except Exception as error:
                logger.error(f"failure while running sendOnlineNotification for {dcUserDb}", exc_info=error)

            try:
                # move is the last step to avoid channel confusion
                await self.channelService.checkChannelForMoving(member)
            except Exception as error:
                logger.error(f"failure while running checkChannelForMoving for {member}", exc_info=error)

            # create new quests and check the progress of existing ones
            try:
                await self.questService.checkQuestsForJoinedMember(member, session)
                await self.questService.addProgressToQuest(member, QuestType.DAYS_ONLINE)
                await self.questService.addProgressToQuest(member, QuestType.ONLINE_STREAK)
            except Exception as error:
                logger.error(f"failure while running addProgressToQuest for {member}", exc_info=error)

            await runLogService(Events.JOINED_VOICE_CHAT)

        # user changed channel or changed status
        elif voiceStateBefore.channel and voiceStateAfter.channel:  # TODO
            logger.debug("member changes status or voice channel")

            # status changed
            if voiceStateBefore.channel == voiceStateAfter.channel:
                logger.debug("%s changed status" % member.name)

                now = datetime.now()

                # self mute
                if not voiceStateBefore.self_mute and voiceStateAfter.self_mute:
                    # dont overwrite previous existing value
                    if not dcUserDb['muted_at']:
                        dcUserDb['muted_at'] = now

                    await runLogService(Events.SELF_MUTE)
                # not self mute
                elif voiceStateBefore.self_mute and not voiceStateAfter.self_mute:
                    # dont go over server mute
                    if not voiceStateAfter.mute:
                        dcUserDb['muted_at'] = None

                    await runLogService(Events.SELF_NOT_MUTE)

                # server mute
                if not voiceStateBefore.mute and voiceStateAfter.mute:
                    # dont overwrite previous existing value
                    if not dcUserDb['muted_at']:
                        dcUserDb['muted_at'] = now

                    await runLogService(Events.MUTE)
                # not server mute
                elif voiceStateBefore.mute and not voiceStateAfter.mute:
                    # dont go over self mute
                    if not voiceStateAfter.self_mute:
                        dcUserDb['muted_at'] = None

                    await runLogService(Events.NOT_MUTE)

                # self deaf
                if not voiceStateBefore.self_deaf and voiceStateAfter.self_deaf:
                    # dont overwrite previous existing value
                    if not dcUserDb['full_muted_at']:
                        dcUserDb['full_muted_at'] = now

                    await runLogService(Events.SELF_DEAF)
                # not self deaf
                elif voiceStateBefore.self_deaf and not voiceStateAfter.self_deaf:
                    # dont go over server deaf
                    if not voiceStateAfter.deaf:
                        dcUserDb['full_muted_at'] = None

                    await runLogService(Events.SELF_NOT_DEAF)

                # server deaf
                if not voiceStateBefore.deaf and voiceStateAfter.deaf:
                    # dont overwrite previous existing value
                    if not dcUserDb['full_muted_at']:
                        dcUserDb['full_muted_at'] = now

                    await runLogService(Events.DEAF)
                # not server deaf
                elif voiceStateBefore.deaf and not voiceStateAfter.deaf:
                    # dont go over server deaf
                    if not voiceStateAfter.self_deaf:
                        dcUserDb['full_muted_at'] = None

                    await runLogService(Events.NOT_DEAF)

                # if user started stream
                if not voiceStateBefore.self_stream and voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = now

                    await runLogService(Events.START_STREAM)
                elif voiceStateBefore.self_stream and not voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = None

                    await runLogService(Events.END_STREAM)

                # if user started webcam
                if not voiceStateBefore.self_video and voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = now

                    await runLogService(Events.START_WEBCAM)
                elif voiceStateBefore.self_video and not voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = None

                    await runLogService(Events.END_WEBCAM)

                dcUserDb['username'] = member.display_name

                self._saveDiscordUser(dcUserDb, database)
            # channel changed
            else:
                logger.debug("%s changed channel" % member.name)

                dcUserDb['channel_id'] = voiceStateAfter.channel.id

                self._saveDiscordUser(dcUserDb, database)

                try:
                    self.waHelper.switchChannelFromOutstandingMessages(dcUserDb, voiceStateAfter.channel.name, member)
                except Exception as error:
                    logger.error(f"failure while running switchChannelFromOutstandingMessages for {member}",
                                 exc_info=error)

                await ChannelService.manageKneipe(voiceStateBefore.channel)

                try:
                    await self.logService.sendLog(member, (voiceStateBefore, voiceStateAfter),
                                                  Events.SWITCHED_VOICE_CHANNEL)
                except Exception as error:
                    logger.error("an error occurred while running logService", exc_info=error)

        # user left channel
        elif voiceStateBefore.channel and not voiceStateAfter.channel:  # TODO
            logger.debug("%s left channel" % member.name)

            try:
                self.waHelper.sendOfflineNotification(dcUserDb, voiceStateBefore, member)
            except Exception as error:
                logger.error(f"failure while running switchChannelFromOutstandingMessages for {member}", exc_info=error)

            dcUserDb['channel_id'] = None
            dcUserDb['joined_at'] = None
            dcUserDb['muted_at'] = None
            dcUserDb['full_muted_at'] = None
            dcUserDb['started_stream_at'] = None
            dcUserDb['started_webcam_at'] = None
            dcUserDb['last_online'] = datetime.now()

            self._saveDiscordUser(dcUserDb, database)

            await ChannelService.manageKneipe(voiceStateBefore.channel)

            try:
                await self.logService.sendLog(member, (voiceStateBefore, voiceStateAfter), Events.LEFT_VOICE_CHANNEL)
            except Exception as error:
                logger.error("an error occurred while running logService", exc_info=error)
        else:
            logger.warning("unexpected voice state update from %s" % member.name)  # TODO

        try:
            session.commit()
        except Exception as error:
            logger.error("couldn't commit changes", exc_info=error)
        finally:
            session.close()

    def _saveDiscordUser(self, dcUserDb: dict, database: Database_Old):
        """
        Saves the given DiscordUser to our database

        :param dcUserDb: DiscordUser to save
        :return:
        """
        query, nones = writeSaveQuery(
            'discord',
            dcUserDb['id'],
            dcUserDb
        )

        if not database.runQueryOnDatabase(query, nones):
            logger.critical("couldn't save DiscordUser to database")
        else:
            logger.debug("updated %s" % dcUserDb['username'])
