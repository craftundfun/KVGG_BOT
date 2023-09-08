from __future__ import annotations

import logging
from datetime import datetime

from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def getUnsentMessagesFromTriggerUser(dcUserDb: dict, isJoinMessage: bool) -> list | None:
    """
    Returns all messages from the message queue which weren't sent yet.

    :param dcUserDb:
    :param isJoinMessage:
    :return:
    """
    try:
        database = Database()
    except ConnectionError as error:
        logger.error("couldn't connect to MySQL, aborting task", exc_info=error)

        return None

    query = "SELECT * " \
            "FROM message_queue " \
            "WHERE sent_at IS NULL and trigger_user_id = %s and time_to_sent IS NOT NULL and time_to_sent > %s " \
            "and is_join_message IS NOT NULL and is_join_message = %s"

    return database.fetchAllResults(query, (dcUserDb['id'], datetime.now(), isJoinMessage,))
