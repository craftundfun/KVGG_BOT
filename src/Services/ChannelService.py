import logging

import discord.errors
from discord import Client, Member, VoiceChannel, CategoryChannel

from src.Helper.SendDM import sendDM
from src.Id.Categories import TrackedCategories
from src.Id.ChannelId import ChannelId
from src.Id.DiscordUserId import DiscordUserId
from src.Id.GuildId import GuildId

logger = logging.getLogger("KVGG_BOT")


class ChannelService:

    def __init__(self, client: Client):
        self.client = client

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
        nameMember_1 = member_1.nick if member_1.nick else member_1.name
        nameMember_2 = member_2.nick if member_2.nick else member_2.name

        if not (member_1Voice := member_1.voice) or not (member_2Voice := member_2.voice):
            logger.debug(f"{nameMember_1} or {nameMember_2} has no voice-state")

            return f"{nameMember_1} und / oder {nameMember_2} sind nicht online."

        if member_1Voice.channel != member_2Voice.channel:
            logger.debug(f"{nameMember_1} and {nameMember_2} are not within the same channel")

            return f"{nameMember_1} und {nameMember_2} sind nicht im gleichen Channel."

        if not (memberVoice := member.voice):
            logger.debug(f"{nameMember} is not online -> cant use kneipe")

            return "Du bist aktuell in keinem VoiceChannel! Du kannst diesen Befehl nicht nutzen!"

        # check only with member_1, here it's safe they both are in the same channel
        if memberVoice.channel != member_1Voice.channel:
            logger.debug(f"{nameMember} is not in the same channel as {nameMember_1} and {nameMember_2}")

            return f"Du bist nicht im VoiceChannel von {nameMember_1} und {nameMember_2}."

        if member_1Voice.channel.category.id not in TrackedCategories.getValues():
            logger.debug("category was not withing gaming / quatschen / besondere events")

            return "Dieser Command funktioniert nicht in deiner aktuellen VoiceChannel-Kategorie."

        if voiceChannel := await self.__createNewChannel(member_1Voice.channel.category):
            try:
                await member_2.move_to(voiceChannel)
                await member_1.move_to(voiceChannel)
            except Exception as error:
                logger.error("couldn't move Paul and Rene into newly created channel", exc_info=error)

                return "Es ist ein Fehler aufgetreten."
            else:
                return f"{nameMember_1} und {nameMember_2} wurden erfolgreich verschoben."
        else:
            return "Es ist ein Fehler aufgetreten."

    async def __createNewChannel(self, category: CategoryChannel,
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
        # only move out of this channel
        if member.voice.channel.id != ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value:
            return

        # ignore members who are alone
        if len(member.voice.channel.members) < 2:
            return

        channel: VoiceChannel | None = self.__findFreeChannel()

        if not channel:
            return

        members = member.voice.channel.members

        for user in members:
            try:
                await user.move_to(channel, reason="moved due to 2+ users in waiting for players")
            except Exception as error:
                logger.error("couldn't move %s (%d) into new channel (%d)" % (user.name, user.id, channel.id),
                             exc_info=error)

        # send DMs after moving all users to prioritize and speed up the moving process
        for user in members:
            try:
                await sendDM(user, "Du wurdest verschoben, da ihr mind. zu zweit in 'warte auf Mitspieler/innen' wart.")
            except Exception as error:
                logger.error("couldn't send DM to %s (%d)" % (user.name, user.id), exc_info=error)

        logger.debug("moved users out of 'warte auf Mitspieler/innen' due to more than 2 users")

    def __findFreeChannel(self) -> VoiceChannel | None:
        """
        Finds the next empty VoiceChannel in the Gaming-Category.

        :return:
        """
        categories = self.client.get_guild(GuildId.GUILD_KVGG.value).categories

        for category in categories:
            if category.id != TrackedCategories.GAMING.value:
                continue

            channels = category.voice_channels
            # return value from guild.categories already sorted them by position
            # channels = sorted(channels, key=lambda channel: channel.position)
            dontUseChannels = [ChannelId.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value,
                               ChannelId.CHANNEL_GAMING_EIN_DREIVIERTEL.value,
                               ChannelId.CHANNEL_GAMING_ZWEI_LEAGUE_OF_LEGENDS.value,
                               ChannelId.CHANNEL_GAMING_SIEBEN_AMERICA.value, ]

            for channel in channels:
                if channel.id in dontUseChannels:
                    continue

                if len(channel.members) == 0:
                    logger.debug("%s (%d) channel free to move" % (channel.name, channel.id))

                    return channel

            logger.debug("all voice channels are full")

            return None
