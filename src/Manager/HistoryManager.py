import logging

from discord import Client, Member
from sqlalchemy import select, null

from src.DiscordParameters.HistoryEvent import HistoryEvent
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.History.Entity.Event import Event
from src.Entities.History.Entity.EventHistory import EventHistory
from src.Entities.History.Repository.HistoryRepository import getEvent
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger("KVGG_BOT")


class HistoryManager:

    def __init__(self, client: Client):
        self.client = client

    @DeprecationWarning
    # noinspection PyMethodMayBeStatic
    async def addHistory(self, member: Member, event: HistoryEvent, additionalData: dict | None = None):
        # TODO fix this
        return

        if member.bot:
            return

        with getSession() as session:
            discordUserDatabase = getDiscordUser(member, session)
            eventDatabase = getEvent(event, session)

            if not discordUserDatabase or not eventDatabase:
                logger.error(f"Can't add history, missing discord user or event for {member, event}")

                return

            eventHistory = EventHistory(
                discord_id=discordUserDatabase.id,
                event_id=eventDatabase.id,
                additional_data=additionalData if additionalData else null(),
            )

            try:
                session.add(eventHistory)
                session.commit()

                logger.debug(f"Added history {event} for {member}")
            except Exception as error:
                logger.error(f"Couldn't add event history for {member.display_name}, {event}", exc_info=error)

                session.rollback()
