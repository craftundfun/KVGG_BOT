import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.MessageQueue.Entity.MessageQueue import MessageQueue

logger = logging.getLogger("KVGG_BOT")


def getUnsentMessagesFromTriggerUser(dcUserDb: DiscordUser,
                                     isJoinMessage: bool,
                                     session: Session) -> list[MessageQueue] | None:
    """
    Returns all messages from the message queue which weren't sent yet.

    :param dcUserDb: The DiscordUser
    :param isJoinMessage: Whether the message was a join message
    :param session: Session of the database connection
    :return:
    """
    # compare None with == and != because of SQLAlchemy
    query = select(MessageQueue).where(MessageQueue.sent_at.is_(None),
                                       MessageQueue.trigger_user_id == dcUserDb.id,
                                       MessageQueue.time_to_sent.is_not(None),
                                       MessageQueue.time_to_sent > datetime.now(),
                                       MessageQueue.is_join_message.is_not(None),
                                       MessageQueue.is_join_message == isJoinMessage, )

    try:
        messages = session.scalars(query).all()
    except Exception as error:
        logger.error(f"couldn't fetch messages from database, dcUserDb:{dcUserDb}", exc_info=error)

        return None

    return list(messages)
