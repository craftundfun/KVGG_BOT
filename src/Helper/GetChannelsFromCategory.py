from discord import Client, VoiceChannel

from src.Id import Categories
from src.Id.Categories import TrackedCategories, UniversityCategory
from src.Id.GuildId import GuildId


def getVoiceChannelsFromCategory(client: Client, *wantedCategories: TrackedCategories | UniversityCategory) \
        -> list[VoiceChannel] | None:
    serverCategories = client.get_guild(GuildId.GUILD_KVGG.value).categories
    channels = []

    for category in serverCategories:
        if category.id in wantedCategories:
            channels.extend(category.voice_channels)

    return channels if len(channels) != 0 else None


def getVoiceChannelsFromCategoryEnum(client: Client, enum: Categories) -> list[VoiceChannel] | None:
    serverCategories = client.get_guild(GuildId.GUILD_KVGG.value).categories
    channels = []

    for category in serverCategories:
        if category.id in enum.getValues():
            channels.extend(category.voice_channels)

    return channels if len(channels) != 0 else None
