import logging

from discord import Member

from src.Helper.SplitStringAtMaxLength import splitStringAtMaxLength

IN_DOCKER = False  # TODO environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
logger = logging.getLogger("KVGG_BOT")


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
    # if not in docker dont sent DMs
    if not IN_DOCKER:
        logger.debug("not in docker")
        # if user is Bjarne still send DMs
        if not member.id == 416967436617777163:  # and not member.id == 214465971576897536:
            return

        logger.debug("send exceptional DM to Bjarne, because we are in the IDE")

    if not member.dm_channel:
        await member.create_dm()

        if not member.dm_channel:
            raise Exception("couldn't create DM channel with %s" % member.name)

    for part in splitStringAtMaxLength(content):
        await member.dm_channel.send(part)


separator = "\n------------------------------------------------------------------------------------\n"
