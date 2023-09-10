import logging

from discord import Member, VoiceState, Client, CategoryChannel

from src.Id.CategoryId import CategoryId
from src.Id.GuildId import GuildId
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class ChannelService:
    HUB_ID: int = 1119775027034849330
    CATEGORY: int = CategoryId.SERVERVERWALTUNG.value  # TODO change to Gaming

    def __init__(self, client: Client):
        """
        :raise ConnectionError:
        """
        self.database = Database()
        self.client = client

    def __getCategory(self) -> CategoryChannel | None:
        """
        Returns the category for the hub to create a voice channel in.

        :return:
        """
        categories = self.client.get_guild(GuildId.GUILD_KVGG.value).categories

        for category in categories:
            if category.id == self.CATEGORY:
                return category

        return None

    async def memberJoinedAVoiceChat(self, member: Member, voiceState: VoiceState):
        """
        Checks if the newly joined member joined into Hub. If so, he / she will be moved into a newly created channel.

        :param _: To be ignored
        :param member: Member, who joined a voice channel
        :param voiceState: State of the member after joining a voice channel
        :return:
        """
        # filter out non hub channels
        if not voiceState.channel.id == self.HUB_ID:
            return

        if not (category := self.__getCategory()):
            logger.critical("couldn't fetch category -> couldn't create new channel")

            return

        # +1 to ignore hub, -1 because hub has no number = +/-0
        name = "Gaming #%d" % len(category.voice_channels)

        try:
            voiceChannel = await category.create_voice_channel(name)
        except Exception as error:
            logger.error("encountered error while creating voice channel", exc_info=error)
        else:
            try:
                await member.move_to(voiceChannel)
            except Exception as error:
                logger.error("couldn't move %s to newly created channel" % member.name, exc_info=error)

    async def memberLeftVoiceChannel(self, member: Member, voiceStateBefore: VoiceState):
        if voiceStateBefore.channel not in self.__getCategory().voice_channels:
            logger.debug("channel was not in Gaming category")

            return

        if len(voiceStateBefore.channel.members) > 0:
            return
        else:
            try:
                await voiceStateBefore.channel.delete(reason="no more users in this channel")
            except Exception as error:
                logger.error("couldn't delete channel", exc_info=error)

                return
