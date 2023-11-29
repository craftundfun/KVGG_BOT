import asyncio

from discord import Member, VoiceChannel


async def moveMembers(members: list[Member], channel: VoiceChannel):
    """
    Moves all the given members fast into the destination channel.

    :param members: List of members to move
    :param channel: Voice-Channel to move the members to
    :raise Forbidden: No permission to move members into the channel
    :raise HTTPException: Something bad happened
    """
    await asyncio.gather(*[member.move_to(channel) for member in members])
