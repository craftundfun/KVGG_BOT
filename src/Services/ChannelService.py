import logging

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

        await channel.delete(reason="no one in channel anymore")

    async def createKneipe(self) -> str:
        """
        Fetches Paul and Rene specifically from the guild to move them into a new channel.

        :return:
        """
        rene = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(DiscordUserId.RENE.value)
        paul = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(DiscordUserId.PAUL.value)

        if not rene or not paul:
            logger.warning("couldn't fetch paul or rene from the guild")

            return "Es ist ein Fehler aufgetreten."

        if not (reneVoice := rene.voice) or not (paulVoice := paul.voice):
            logger.debug("Paul or Rene has no voice-state")

            return "Paul und / oder Rene sind nicht online."

        if reneVoice.channel != paulVoice.channel:
            logger.debug("Rene and Paul are not within the same channel")

            return "Paul und Rene sind nicht im gleichen Channel."

        if reneVoice.channel.category.id not in TrackedCategories.getValues():
            logger.debug("category was not withing gaming / quatschen / besondere events")

            return "Dieser Command funktioniert nicht in deiner aktuellen Kategorie."

        if voiceChannel := await self.__createNewChannel(reneVoice.channel.category):
            try:
                await paul.move_to(voiceChannel)
                await rene.move_to(voiceChannel)
            except Exception as error:
                logger.error("couldn't move Paul and Rene into newly created channel", exc_info=error)

                return "Es ist ein Fehler aufgetreten."
            else:
                return "Paul und René wurden erfolgreich verschoben."
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
