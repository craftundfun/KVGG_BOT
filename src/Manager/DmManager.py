import logging
from asyncio import Lock, Queue
from datetime import datetime
from typing import Tuple

import discord
from discord import Member

from src.Helper.SendDM import sendDM

logger = logging.getLogger("KVGG_BOT")


class DmManager:
    """
    Bundle simultaneous messages to the same user and send them in a batch
    """

    _self = None
    messageList: dict[Member, Tuple[Queue[str], datetime,]] = {}
    waitingTime = 5  # seconds

    def __init__(self):
        self.lock = Lock()

    def __new__(cls, *args, **kwargs):
        """
        Singleton-Pattern
        """
        if not cls._self:
            cls._self = super().__new__(cls)

        return cls._self

    async def addMessage(self, member: Member, message: str):
        async with self.lock:
            queue, timeOfLastMessage = self.messageList.get(member, (Queue(), None,))

            await queue.put(message)
            timeOfLastMessage = datetime.now()

            self.messageList[member] = (queue, timeOfLastMessage,)

    async def sendMessages(self):
        """
        Traverses the messageList and sends the messages to the members if the waiting time is reached
        """
        membersToRemove = []

        async with self.lock:
            for member, (queue, timeOfLastMessage,) in self.messageList.items():
                # declare types for IDE
                member: Member
                queue: Queue
                timeOfLastMessage: datetime

                if (datetime.now() - timeOfLastMessage).seconds <= self.waitingTime:
                    logger.debug(f"waiting time not reached yet for messages for {member}")

                    continue

                message = ""

                while not queue.empty():
                    message += await queue.get()

                try:
                    await sendDM(member, message)
                except discord.Forbidden:
                    logger.warning(f"couldn't send DM to {member.name}: Forbidden")
                except Exception as error:
                    logger.error(f"couldn't send DM to {member.name}", exc_info=error)

                membersToRemove.append(member)
            else:
                logger.debug("no messages to send")

            for member in membersToRemove:
                del self.messageList[member]

                logger.debug(f"removed {member} from messageList")
