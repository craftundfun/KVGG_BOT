import asyncio
import logging

import discord.errors
from discord import Client, Member, VoiceChannel, CategoryChannel

from src.Helper.MoveMembesToVoicechannel import moveMembers
from src.Id.Categories import TrackedCategories
from src.Id.ChannelId import ChannelId
from src.Id.DiscordUserId import DiscordUserId
from src.Id.GuildId import GuildId
from src.Manager.NotificationManager import NotificationService

logger = logging.getLogger("KVGG_BOT")
lock = asyncio.Lock()


class ChannelService:

    def __init__(self, client: Client):
        self.client = client
        self.notificationService = NotificationService(self.client)

    @staticmethod
    async def manageKneipe(channel: VoiceChannel):
        """
        Deletes "Kneipe" if there are no members left in the channel.

        :param channel:
        :return:
        """
        if channel.name != "Kneipe":
            return

        if len(channel.members) != 0:
            return

        try:
            await channel.delete(reason="no one in channel anymore")
        except discord.errors.NotFound as error:
            logger.warning("channel not found - maybe because it was deleted beforehand", exc_info=error)

    async def createKneipe(self, member: Member, member_1: Member | None, member_2: Member | None) -> str:
        """
        Fetches Paul and Rene or both given members specifically from the guild to move them into a new channel.

        :return:
        """
        if not member_1 and not member_2:
            # overwrite both members to paul and rene
            member_1 = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(DiscordUserId.RENE.value)
            member_2 = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(DiscordUserId.PAUL.value)

            if not member_1 or not member_2:
                logger.warning("couldn't fetch paul or rene from the guild")

                return "Es ist ein Fehler aufgetreten."
        elif not member_1 or not member_2:
            logger.debug("user didnt choose two member to move in kneipe")

            return "Du musst zwei Benutzer angeben!"

        nameMember = member.nick if member.nick else member.name

        if not (member_1Voice := member_1.voice) or not (member_2Voice := member_2.voice):
            logger.debug(f"{member_1.display_name} or {member_2.display_name} has no voice-state")

            return f"<@{member_1.id}> und / oder <@{member_2.id}> sind nicht online."

        if member_1Voice.channel != member_2Voice.channel:
            logger.debug(f"{member_1.display_name} and {member_2.display_name} are not within the same channel")

            return f"<@{member_1.id}> und <@{member_2.id}> sind nicht im gleichen Channel."

        if not (memberVoice := member.voice):
            logger.debug(f"{nameMember} is not online -> cant use kneipe")

            return "Du bist aktuell in keinem VoiceChannel! Du kannst diesen Befehl nicht nutzen!"

        # check only with member_1, here it's safe they both are in the same channel
        if memberVoice.channel != member_1Voice.channel:
            logger.debug(f"{nameMember} is not in the same channel as {member_1.display_name} and "
                         f"{member_2.display_name}")

            return f"Du bist nicht im VoiceChannel von <@{member_1.id}> und <@{member_2.id}>."

        if member_1Voice.channel.category.id not in TrackedCategories.getValues():
            logger.debug("category was not withing gaming / quatschen / besondere events")

            return "Dieser Command funktioniert nicht in deiner aktuellen VoiceChannel-Kategorie."

        if voiceChannel := await self._createNewChannel(member_1Voice.channel.category):
            loop = asyncio.get_event_loop()

            try:
                loop.run_until_complete(moveMembers([member_1, member_2], voiceChannel))
            except Exception as error:
                logger.error(f"couldn't move {member_1.display_name} and {member_2.display_name} into new channel ",
                             exc_info=error, )

                return "Es ist ein Fehler aufgetreten."
            else:
                return f"<@{member_1.id}> und<@ {member_2.id}> wurden erfolgreich verschoben."
        else:
            return "Es ist ein Fehler aufgetreten."

    async def _createNewChannel(self,
                                category: CategoryChannel,
                                name: str = "Kneipe",
                                userLimit: int = 2) -> VoiceChannel | None:
        """
        Creates a voice-channel in the given category

        :param category: Category from the guild
        :param name: Name of the channel, standard value is "Kneipe"
        :param userLimit: Limits the channel users, standard is 2
        :return:
        """
        if not category:
            logger.critical("no category was given")

            return None

        try:
            voiceChannel = await category.create_voice_channel(name=name, user_limit=userLimit)
        except Exception as error:
            logger.error("couldn't create voice-channel", exc_info=error)

            return None
        else:
            return voiceChannel

    async def checkChannelForMoving(self, member: Member):
        """
        Checks if more than two users are connected to the 'wait for players' channel to move them into the next free
        channel.

        :param member:
        :return:
        """
        async with lock:
            # only move out of this channel
            if member.voice and member.voice.channel.id != ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value:
                return

            # ignore members who are alone
            if len(member.voice.channel.members) < 2:
                return

            if not (channelToMove := self._findFreeChannel()):
                logger.debug("no free channel was found")

                return

            members = member.voice.channel.members
            loop = asyncio.get_event_loop()

            try:
                loop.run_until_complete(moveMembers(members, channelToMove))
            except discord.Forbidden:
                logger.error("dont have rights move the users!")

                return
            except Exception as error:
                logger.error("couldn't move members into new channel", exc_info=error)

                return

            # send DMs after moving all users to prioritize and speed up the moving process
            for user in members:
                await self.notificationService.sendStatusReport(user,
                                                                "Du wurdest verschoben, da ihr mindestens zu "
                                                                "zweit in 'warte auf Mitspieler/innen' wart.")

            logger.debug("moved users out of 'warte auf Mitspieler/innen' due to more than 2 users")

    def _findFreeChannel(self) -> VoiceChannel | None:
        """
        Finds the next empty VoiceChannel in the Gaming-Category.

        :return:
        """
        # list comprehensions are faster than for-loops
        gaming_category = [category for category in self.client.get_guild(GuildId.GUILD_KVGG.value).categories
                           if category.id == TrackedCategories.GAMING.value][0]
        dont_use_channels = [ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value,
                             ChannelId.CHANNEL_GAMING_EIN_DREIVIERTEL.value,
                             ChannelId.CHANNEL_GAMING_ZWEI_LEAGUE_OF_LEGENDS.value,
                             ChannelId.CHANNEL_GAMING_SIEBEN_AMERICA.value, ]

        for channel in gaming_category.voice_channels:
            if channel.id in dont_use_channels:
                continue

            if len(channel.members) == 0:
                logger.debug(f"{channel.name} ({channel.id}) channel free to move")

                return channel

        logger.debug("all channels are occupied")

        return None
