from __future__ import annotations

import mysql.connector

from mysql.connector import MySQLConnection
from src.Helper.ReadParameters import Parameters as parameters
from src.Helper import ReadParameters as rp


def getDatabaseConnection() -> MySQLConnection | None:
    """
    :return: New database connection
    :raise: TypeError if connection could not be established
    """
    databaseConnection = mysql.connector.connect(
        user=rp.getParameter(parameters.USER),
        password=rp.getParameter(parameters.PASSWORD),
        host=rp.getParameter(parameters.HOST),
        database=rp.getParameter(parameters.NAME),
    )

    if databaseConnection is None:
        raise TypeError("DatabaseConnection couldn't be established, return was None!")
    return databaseConnection
