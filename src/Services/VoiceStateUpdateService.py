import logging

import discord

from datetime import datetime
from discord import Member, VoiceState
from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services import ExperienceService
from src.Services.WhatsAppHelper import WhatsAppHelper
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection

logger = logging.getLogger("KVGG_BOT")


class VoiceStateUpdateService:
    """
    Handles every VoiceState and keeps the database up to date
    """
    def __init__(self, client: discord.Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client
        self.waHelper = WhatsAppHelper()

    async def handleVoiceStateUpdate(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        logger.info("%s raised a VoiceStateUpdate" % member.name)

        if not member:
            return
        elif member.bot:
            return

        dcUserDb = getDiscordUser(self.databaseConnection, member)

        if not dcUserDb:
            logger.error("Couldn't fetch DiscordUser from %s!" % member.name)

            return

        # user joined channel
        if not voiceStateBefore.channel and voiceStateAfter.channel:
            dcUserDb['channel_id'] = voiceStateAfter.channel.id
            dcUserDb['joined_at'] = datetime.now()

            # if user joined with (full) mute
            if voiceStateAfter.self_mute:
                dcUserDb['muted_at'] = datetime.now()
            elif not voiceStateAfter.self_mute:
                dcUserDb['muted_at'] = None

            if voiceStateAfter.self_deaf:
                dcUserDb['full_muted_at'] = datetime.now()
            elif not voiceStateAfter.self_deaf:
                dcUserDb['full_muted_at'] = None

            # must run before saving user
            await self.__checkFelixCounterAndSendStopMessage(dcUserDb)
            # save user so a whatsapp message can be sent properly
            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOnlineNotification(member, voiceStateAfter)
            await ExperienceService.informAboutDoubleXpWeekend(dcUserDb, self.client)

        # user changed channel or changed status
        elif voiceStateBefore.channel and voiceStateAfter.channel:
            # status changed
            if voiceStateBefore.channel == voiceStateAfter.channel:
                now = datetime.now()

                # if a user is mute
                if voiceStateAfter.self_mute:
                    dcUserDb['muted_at'] = now
                elif not voiceStateAfter.self_mute:
                    dcUserDb['muted_at'] = None

                # if a user is full mute
                if voiceStateAfter.self_deaf:
                    dcUserDb['full_muted_at'] = now
                elif not voiceStateAfter.self_deaf:
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
                dcUserDb['channel_id'] = voiceStateAfter.channel.id

                self.__saveDiscordUser(dcUserDb)
                self.waHelper.switchChannelFromOutstandingMessages(dcUserDb, voiceStateAfter.channel.name)

        # user left channel
        elif voiceStateBefore.channel and not voiceStateAfter.channel:
            self.waHelper.sendOfflineNotification(dcUserDb, voiceStateBefore, member)

            dcUserDb['channel_id'] = None
            dcUserDb['joined_at'] = None
            dcUserDb['muted_at'] = None
            dcUserDb['full_muted_at'] = None
            dcUserDb['started_stream_at'] = None
            dcUserDb['started_webcam_at'] = None
            dcUserDb['last_online'] = datetime.now()

            self.__saveDiscordUser(dcUserDb)


    def __saveDiscordUser(self, dcUserDb: dict):
        """
        Saves the given DiscordUser to our database

        :param dcUserDb: DiscordUser to save
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

    async def __checkFelixCounterAndSendStopMessage(self, dcUserDb: dict):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param dcUserDb:
        :return:
        """
        logger.info("Checking Felix-Timer from %s" % dcUserDb['username'])

        if dcUserDb['felix_counter_start'] is not None:
            dcUserDb['felix_counter_start'] = None
        else:
            return

        await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(int(dcUserDb['user_id']))
        member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

        if not member.dm_channel:
            await member.create_dm()

            if not member.dm_channel:
                logger.warning("Couldn't create DM!")

                return

        await member.dm_channel.send("Dein Felix-Counter wurde beendet!")

    def __del__(self):
        self.databaseConnection.close()
