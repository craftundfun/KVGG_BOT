import logging

from discord import Client, Member, VoiceChannel

from src.Helper.SendDM import sendDM
from src.Id.Categories import Categories
from src.Id.ChannelIdWhatsAppAndTracking import ChannelIdWhatsAppAndTracking
from src.Id.GuildId import GuildId

logger = logging.getLogger("KVGG_BOT")


class ChannelService:

    def __init__(self, client: Client):
        self.client = client

    async def checkChannelForMoving(self, member: Member):
        """
        Checks if more than two users are connected to the 'wait for players' channel to move them into the next free
        channel.

        :param member:
        :return:
        """
        # only move out of this channel
        if member.voice.channel.id != int(ChannelIdWhatsAppAndTracking.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value):
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
                await sendDM(user, "Du wurdest verschoben da ihr mind. zu zweit in 'warte auf Mitspieler/innen' wart.")
            except Exception as error:
                logger.error("couldn't send DM to %s (%d)" % (user.name, user.id), exc_info=error)

        logger.debug("moved users out of 'warte auf Mitspieler/innen' due to more than 2 users")

    def __findFreeChannel(self) -> VoiceChannel | None:
        """
        Finds the next empty VoiceChannel in the Gaming-Category.

        :return:
        """
        categories = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).categories

        for category in categories:
            if category.id != Categories.GAMING.value:
                continue

            channels = category.voice_channels
            # return value from guild.categories already sorted them by position
            # channels = sorted(channels, key=lambda channel: channel.position)
            dontUseChannels = [int(ChannelIdWhatsAppAndTracking.CHANNEL_WARTE_AUF_MITSPIELER_INNEN.value),
                               int(ChannelIdWhatsAppAndTracking.CHANNEL_GAMING_EIN_DREIVIERTEL.value),
                               int(ChannelIdWhatsAppAndTracking.CHANNEL_GAMING_ZWEI_LEAGUE_OF_LEGENDS.value),
                               int(ChannelIdWhatsAppAndTracking.CHANNEL_GAMING_SIEBEN_AMERICA.value), ]

            for i in range(1, len(channels) - 1):
                if channels[i].id in dontUseChannels:
                    continue

                if len(channels[i].members) == 0:
                    logger.debug("%s (%d) channel free to move" % (channels[i].name, channels[i].id))

                    return channels[i]

            logger.debug("all voice channels are full")

            return None
