from __future__ import annotations

import logging

import discord

from datetime import datetime, timedelta
from discord import Member, VoiceState
from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services import ExperienceService
from src.Services.RelationService import RelationService
from src.Services.WhatsAppHelper import WhatsAppHelper
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.SendDM import sendDM

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
        logger.debug("%s raised a VoiceStateUpdate" % member.name)

        if not member:
            logger.debug("member was not a member")

            return
        elif member.bot:
            logger.debug("member was a bot")

            return

        dcUserDb = getDiscordUser(self.databaseConnection, member)

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

            # must run before saving user
            await self.__checkFelixCounterAndSendStopMessage(dcUserDb)
            # save user so a whatsapp message can be sent properly
            self.__saveDiscordUser(dcUserDb)
            self.waHelper.sendOnlineNotification(member, voiceStateAfter)
            await ExperienceService.informAboutDoubleXpWeekend(dcUserDb, self.client)

            if not await self.__xDaysOfflineMessage(member, dcUserDb):
                await self.__welcomeBackMessage(member, dcUserDb)

        # user changed channel or changed status # TODO increase frequency for stream changes in RelationService
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

            await RelationService(self.client).manageLeavingMember(member, voiceStateBefore)

        else:
            logger.warning("unexpected voice state update from %s" % member.name)

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

        logger.debug("updated %s" % dcUserDb['username'])

    async def __checkFelixCounterAndSendStopMessage(self, dcUserDb: dict):
        """
        Check if the given DiscordUser had a Felix-Counter, if so it stops the timer

        :param dcUserDb:
        :return:
        """
        logger.debug("Checking Felix-Timer from %s" % dcUserDb['username'])

        if dcUserDb['felix_counter_start'] is not None:
            dcUserDb['felix_counter_start'] = None
        else:
            return

        await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(int(dcUserDb['user_id']))
        member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

        if not member.dm_channel:
            await member.create_dm()

            if not member.dm_channel:
                logger.warning("couldn't create DM!")

                return

        await member.dm_channel.send("Dein Felix-Counter wurde beendet!")
        logger.debug("sent dm to %s" % member.name)

    """You are finally awake GIF"""
    finallyAwake = "https://tenor.com/bwJvI.gif"

    async def __xDaysOfflineMessage(self, member: Member, dcUserDb) -> bool:
        """
        If the member was offline for longer than 30 days, he / she will receive a welcome back message

        :param member: Member, who the condition is tested against
        :param dcUserDb: DiscordUser from the database
        :return: Boolean if a message was sent
        """
        if not dcUserDb['last_online']:
            logger.debug("%s has no last_online status" % member.name)

            return False

        if (diff := (datetime.now() - dcUserDb['last_online'])).days >= 30:
            await sendDM(member, "Schön, dass du mal wieder da bist :)\n\nDu warst seit %d Tagen, %d Stunden "
                                 "und %d Minuten nicht mehr da." %
                         (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60))
            await sendDM(member, self.finallyAwake)

            logger.debug("sent dm to %s" % member.name)

            return True

        logger.debug("%s was less than %d days online ago" % (member.name, 30))

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
            logger.debug("%s is not opted in for welcome_back_notification" % member.name)

            return
        elif not dcUserDb['last_online']:
            logger.debug("%s has no last_online" % member.name)

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

        if days < 1 and hours < 1 and minutes < 30:
            logger.debug("%s was online less than 30 minutes ago" % member.name)

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

        if onlineTime and not streamTime:
            message += ". "

        if xp:
            message += "Außerdem hast du bereits %d XP gefarmt." % xp['xp_amount']

        message += "\n\nViel Spaß!"

        await sendDM(member, message)

        logger.debug("sent dm to %s" % member.name)

    def __del__(self):
        self.databaseConnection.close()
