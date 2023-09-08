from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord import Member, VoiceState

from src.Services.Database import Database
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.InheritedCommands.NameCounter.FelixCounter import FelixCounter
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.NotificationService import NotificationService
from src.Services.RelationService import RelationService
from src.Services.WhatsAppHelper import WhatsAppHelper

logger = logging.getLogger("KVGG_BOT")


class VoiceStateUpdateService:
    """
    Handles every VoiceState and keeps the database up to date
    """

    def __init__(self, client: discord.Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client
        self.waHelper = WhatsAppHelper()
        self.notificationService = NotificationService(self.client)
        self.felixCounter = FelixCounter()

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
            logger.error("couldn't fetch DiscordUser for %s!" % member.name)

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

            await self.notificationService.runNotificationsForMember(member, dcUserDb)
            await self.felixCounter.checkFelixCounterAndSendStopMessage(member, dcUserDb)

            # save user so a whatsapp message can be sent properly
            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOnlineNotification(member, voiceStateAfter)

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

                dcUserDb['username'] = member.nick if member.nick else member.name

                self.__saveDiscordUser(dcUserDb)
            # channel changed
            else:
                logger.debug("%s changed channel" % member.name)

                dcUserDb['channel_id'] = voiceStateAfter.channel.id

                self.__saveDiscordUser(dcUserDb)
                self.waHelper.switchChannelFromOutstandingMessages(dcUserDb, voiceStateAfter.channel.name)

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

            try:
                rs = RelationService(self.client)
            except ConnectionError as error:
                logger.error("failure to start RelationService", exc_info=error)
            else:
                await rs.manageLeavingMember(member, voiceStateBefore)
        else:
            logger.warning("unexpected voice state update from %s" % member.name)

    def __saveDiscordUser(self, dcUserDb: dict):
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

        if not self.database.runQueryOnDatabase(query, nones):
            logger.critical("couldnt save DiscordUser to database")
        else:
            logger.debug("updated %s" % dcUserDb['username'])
