from __future__ import annotations

import logging

import discord

from datetime import datetime, timedelta
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

            # must run before saving user
            await self.__checkFelixCounterAndSendStopMessage(dcUserDb)
            # save user so a whatsapp message can be sent properly
            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOnlineNotification(member, voiceStateAfter)
            await ExperienceService.informAboutDoubleXpWeekend(dcUserDb, self.client)

            if not await self.__xDaysOfflineMessage(member, dcUserDb):
                await self.__welcomeBackMessage(member, dcUserDb)

        # user changed channel or changed status
        elif voiceStateBefore.channel and voiceStateAfter.channel:
            # status changed
            if voiceStateBefore.channel == voiceStateAfter.channel:
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

    """You are finally awake GIF"""
    finallyAwake = "https://tenor.com/bwJvI.gif"

    async def __xDaysOfflineMessage(self, member: Member, dcUserDb) -> bool:
        """
        If the member was offline for longer than 30 days, he / she will receive a welcome back message

        :param member:
        :param dcUserDb:
        :return: Boolean if a message was sent
        """
        if not dcUserDb['last_online']:
            return False

        if (diff := (datetime.now() - dcUserDb['last_online'])).days >= 30:
            if not member.dm_channel:
                await member.create_dm()

                if not member.dm_channel:
                    return False

            await member.dm_channel.send("Schön, dass du mal wieder da bist :)\n\nDu warst seit %d Tagen, %d Stunden "
                                         "und %d Minuten nicht mehr da." %
                                         (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60))
            await member.dm_channel.send(self.finallyAwake)

            return True

        return False

    async def __welcomeBackMessage(self, member: Member, dcUserDb):
        """
        Sends a welcome back notification for users who opted in

        :param member: Member, who joined
        :param dcUserDb: Discord User from our database
        :return:
        """
        optedIn = dcUserDb['welcome_back_notification']

        if not optedIn or optedIn is False:
            return
        elif not dcUserDb['last_online']:
            return

        now = datetime.now()

        if 0 <= now.hour <= 11:
            daytime = "Morgen"
        elif 12 <= now.hour <= 14:
            daytime = "Mittag"
        elif 15 <= now.hour <= 17:
            daytime = "Nachmittag"
        else:
            daytime = "Abend"

        lastOnlineDiff: timedelta = now - dcUserDb['last_online']
        days: int = lastOnlineDiff.days
        hours: int = lastOnlineDiff.seconds // 3600
        minutes: int = (lastOnlineDiff.seconds // 60) % 60

        if minutes < 30:
            return

        onlineTime: str | None = dcUserDb['formated_time']
        streamTime: str | None = dcUserDb['formatted_stream_time']

        xpService = ExperienceService.ExperienceService(self.client)
        xp: dict | None = xpService.getXpValue(dcUserDb)

        message = "Hey, guten %s. Du warst vor %d Tagen, %d Stunden und %d Minuten zuletzt online. " % (
            daytime, days, hours, minutes
        )

        if onlineTime:
            message += "Deine Online-Zeit beträgt %s Stunden" % onlineTime

        if streamTime:
            message += ", deine Stream-Zeit %s Stunden. " % streamTime
        else:
            message += ". "

        if xp:
            message += "Außerdem hast du bereits %d XP gefarmt." % xp['xp_amount']

        message += "\n\nViel Spaß!"

        if not member.dm_channel:
            await member.create_dm()

            if not member.dm_channel:
                logger.warning("Couldnt create DM-Channel with %s" % member.name)
                
                return

        await member.dm_channel.send(message)

    def __del__(self):
        self.databaseConnection.close()
