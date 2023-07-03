from __future__ import annotations

import mysql.connector
import logging

from mysql.connector import MySQLConnection
from src.Helper.ReadParameters import Parameters as parameters
from src.Helper import ReadParameters as rp

logger = logging.getLogger("KVGG_BOT")


def getDatabaseConnection() -> MySQLConnection | None:
    """
    :return: New database connection
    :raise: TypeError if connection could not be established
    """
    databaseConnection = None

    try:
        databaseConnection = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )
    except Exception as e:
        logger.critical("DatabaseConnection couldn't be established!", exc_info=e)
        raise TypeError

    if databaseConnection is None:
        logger.critical("DatabaseConnection couldn't be established!")
        raise TypeError("DatabaseConnection couldn't be established, return was None!")
    return databaseConnection
