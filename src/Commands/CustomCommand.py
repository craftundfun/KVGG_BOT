import logging

import discord.app_commands
from discord.ext import commands
from discord import app_commands

from src.Helper.SendDM import sendDM
from src.Helper.SplitStringAtMaxLength import splitStringAtMaxLength
from src.Services.QuestService import QuestService
from src.Services.ProcessUserInput import ProcessUserInput

logger = logging.getLogger("KVGG_BOT")

class CustomCommand:
    tree: discord.app_commands.CommandTree
    client: discord.Client

    def __int__(self, client: discord.Client):
        # creates the command tree
        self.tree = app_commands.CommandTree(client)


    async def __send_message(self, member: discord.Member, content: str) -> bool:
        """
        Sends a DM to the user and handles errors.

        :param member: C.F. sendDM
        :param content: C.F. sendDM
        :return: Bool about the success of the operation
        """
        try:
            await sendDM(member, content)

            return True
        except discord.Forbidden:
            logger.warning(f"couldn't send DM to {member.name}: Forbidden")
        except Exception as error:
            logger.error(f"couldn't send DM to {member.name}", exc_info=error)

            return False


    async def __set_loading(self, ctx: discord.interactions.Interaction) -> bool:
        """
        Sets the interaction to thinking

        :param ctx: Interaction to think about
        :return: bool, True if success, false if failure
        """
        try:
            await ctx.response.defer(thinking=True)
        except discord.errors.NotFound as error:
            logger.error("too late :(", exc_info=error)

            return False
        except discord.errors.HTTPException as e:
            logger.error("received HTTPException", exc_info=e)

            return False
        except discord.errors.InteractionResponded as e:
            logger.error("interaction was answered before", exc_info=e)

            return False

        logger.debug("set interaction to thinking")

        return True


    async def __send_answer(self, ctx: discord.interactions.Interaction | commands.Context, answer: str):
        """
        Sends the specified answer to the interaction

        :param ctx: Interaction to answer
        :param answer: Answer that will be sent
        :return:
        """
        try:
            await ProcessUserInput(self.client).raiseMessageCounter(ctx.user, ctx.channel, True)
        except ConnectionError as error:
            logger.error("failure to start ProcessUserInput", exc_info=error)

        try:
            for part in splitStringAtMaxLength(answer):
                await ctx.followup.send(part)
        except Exception as e:
            logger.error("couldn't send answer to command", exc_info=e)

        logger.debug("sent webhook-answer")

        try:
            questService = QuestService(self.client)
        except ConnectionError as error:
            logger.error("failure to start QuestService", exc_info=error)
        else:
            await questService.addProgressToQuest(ctx.user, QuestType.COMMAND_COUNT)