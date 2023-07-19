from __future__ import annotations

import logging
from datetime import datetime

from mysql.connector import MySQLConnection

logger = logging.getLogger("KVGG_BOT")


def getUnsentMessagesFromTriggerUser(databaseConnection: MySQLConnection, dcUserDb: dict,
                                     isJoinMessage: bool) -> list | None:
    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM message_queue " \
                "WHERE sent_at IS NULL and trigger_user_id = %s and time_to_sent IS NOT NULL and time_to_sent > %s " \
                "and is_join_message IS NOT NULL and is_join_message = %s"

        cursor.execute(query, (dcUserDb['id'], datetime.now(), isJoinMessage))

        data = cursor.fetchall()
        logger.debug("fetched data from database")

        if not data:
            return None

        return [dict(zip(cursor.column_names, date)) for date in data]
