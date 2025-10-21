import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.DiscordParameters.HistoryEvent import HistoryEvent
from src.Entities.History.Entity.Event import Event

logger = logging.getLogger("KVGG_BOT")


def getEvent(event: HistoryEvent, session: Session) -> Event | None:
    """
    Fetches the corresponding Event from the database.

    :param event: HistoryEvent to fetch
    :param session: Session of the database connection
    :return: None | Event
    """
    getQuery = select(Event).where(Event.value == event.name, )

    try:
        eventDb = session.scalars(getQuery).one()
        return eventDb
    except Exception as error:
        logger.error("couldn't fetch Event from database", exc_info=error)

        return None
