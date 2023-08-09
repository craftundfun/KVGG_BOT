from discord import Member


async def sendDM(member: Member, content: str):
    """
    Handles the inconveniences to send a DM to a member

    :param member: Member, who will receive the DM
    :param content: Content of the DM
    :return:
    :raise discord.HTTPException: Sending the message failed
    :raise discord.Forbidden: You do not have the proper permissions to send the message.
    :raise ValueError: The ``files`` or ``embeds`` list is not of the appropriate size.
    :raise TypeError: /
    """
    if not member.dm_channel:
        await member.create_dm()

        if not member.dm_channel:
            raise Exception

    await member.dm_channel.send(content)
