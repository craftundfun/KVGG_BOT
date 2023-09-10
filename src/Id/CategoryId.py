from enum import Enum

from discord import Client, VoiceChannel

from src.Id.GuildId import GuildId


class CategoryWhatsappAndTrackingId(Enum):
    SERVERVERWALTUNG = 623227011422355526  # TODO change to Gaming

    LABERECKE = 693584839521206396

    GAMING = 623226859093491743

    UNIVERSITAETS_HUB = 803323466157129818

    BESONDERE_EVENTS = 915226265903050762

    @classmethod
    def getValues(cls) -> set:
        return set(channel.value for channel in CategoryWhatsappAndTrackingId)

    @classmethod
    def getChannelsFromCategories(cls, client: Client) -> list[VoiceChannel]:
        guildCategories = client.get_guild(GuildId.GUILD_KVGG.value).categories

        channels: list = []

        for category in guildCategories:
            if category.id in cls.getValues():
                channels.extend(category.voice_channels)

        return channels


class CategoryUniversityTrackingId(Enum):
    UNIVERSITY = 803323466157129818

    @classmethod
    def getValues(cls) -> set:
        return set(channel.value for channel in CategoryUniversityTrackingId)

    @classmethod
    def getChannelsFromCategories(cls, client: Client) -> list[VoiceChannel]:
        guildCategories = client.get_guild(GuildId.GUILD_KVGG.value).categories

        channels: list = []

        for category in guildCategories:
            if category.id in cls.getValues():
                channels.extend(category.voice_channels)

        return channels
