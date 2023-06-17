from datetime import datetime

import discord
from discord import Member, VoiceState
from mysql.connector import MySQLConnection

from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services import ExperienceService
from src.Services.WhatsAppHelper import WhatsAppHelper


class VoiceStateUpdateService:

    def __init__(self, databaseConnection: MySQLConnection, client: discord.Client):
        self.databaseConnection = databaseConnection
        self.client = client
        self.waHelper = WhatsAppHelper(self.databaseConnection)

    async def handleVoiceStateUpdate(self, member: Member, voiceStateBefore: VoiceState, voiceStateAfter: VoiceState):
        if not member:
            return
        elif member.bot:
            return

        # TODO insert VoiceState
        dcUserDb = getDiscordUser(self.databaseConnection, member)

        if not dcUserDb:
            return

        # look for new avatar
        if dcUserDb['profile_picture_discord'] != member.display_avatar:
            dcUserDb['profile_picture_discord'] = member.display_avatar

        # only needed for console print
        if member.nick:
            username = member.nick
        else:
            username = member.name

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
                # TODO create one variable for now()
                # if user is mute
                if voiceStateAfter.self_mute:
                    dcUserDb['muted_at'] = datetime.now()
                elif not voiceStateAfter.self_mute:
                    dcUserDb['muted_at'] = None

                # if a user is full mute
                if voiceStateAfter.self_deaf:
                    dcUserDb['full_muted_at'] = datetime.now()
                elif not voiceStateAfter.self_deaf:
                    dcUserDb['full_muted_at'] = None

                # if user started stream
                if not voiceStateBefore.self_stream and voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = datetime.now()
                elif voiceStateBefore.self_stream and not voiceStateAfter.self_stream:
                    dcUserDb['started_stream_at'] = None

                # if user started webcam
                if not voiceStateBefore.self_video and voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = datetime.now()
                elif voiceStateBefore.self_video and not voiceStateAfter.self_video:
                    dcUserDb['started_webcam_at'] = None

                self.__saveDiscordUser(dcUserDb)
            # channel changed
            else:
                dcUserDb['channel_id'] = voiceStateAfter.channel

                self.__saveDiscordUser(dcUserDb)
                self.waHelper.switchChannelFromOutstandingMessages(dcUserDb, voiceStateAfter.channel.name)

        # user left channel
        elif voiceStateBefore.channel and not voiceStateAfter.channel:
            dcUserDb['channel_id'] = None
            dcUserDb['joined_at'] = None
            dcUserDb['muted_at'] = None
            dcUserDb['full_muted_at'] = None
            dcUserDb['started_stream_at'] = None
            dcUserDb['started_webcam_at'] = None
            dcUserDb['last_online'] = datetime.now()

            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOfflineNotification(dcUserDb, voiceStateBefore)

    def __saveDiscordUser(self, dcUserDb: dict):
        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            cursor.execute(query, nones)
        self.databaseConnection.commit()

    async def __checkFelixCounterAndSendStopMessage(self, dcUserDb: dict):
        if dcUserDb['felix_counter_start'] is not None:
            dcUserDb['felix_counter_start'] = None
        else:
            return

        await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(int(dcUserDb['user_id']))
        member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

        if not member.dm_channel:
            await member.create_dm()

            if not member.dm_channel:
                return

        await member.dm_channel.send("Dein Felix-Counter wurde beendet!")