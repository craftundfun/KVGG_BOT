import logging
import traceback
from typing import Tuple

import mysql
from mysql.connector import MySQLConnection

from src.Helper.EmailService import send_exception_mail
from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("KVGG_BOT")


class Database:

    def __init__(self):
        self.connection = self._createConnection()

        if not self.connection:
            raise ConnectionError("no connection to mysql")

    def fetchOneResult(self, query: str, parameters: Tuple = None) -> dict | None:
        """
        Tries to run the query. If errors occur, they will be caught and None is getting returned.

        :param query: MySQL Query
        :param parameters: Parameters for the query
        :return:
        """
        with self.connection.cursor() as cursor:
            try:
                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)

                data = cursor.fetchone()
            except Exception as error:
                logger.error("there was a problem processing the following query: %s" % query, exc_info=error)
                send_exception_mail("there was a problem processing the following query: %s" % query
                                    + "\n\n" + traceback.format_exc())

                return None
            else:
                if not data:
                    return None

                return dict(zip(cursor.column_names, data))

    def fetchAllResults(self, query: str, parameters: Tuple = None) -> list[dict] | None:
        """
        Tries to run the query. If errors occur, they will be caught and None is getting returned.

        :param query: MySQL Query
        :param parameters: Parameters for the query
        :return:
        """
        with self.connection.cursor() as cursor:
            try:
                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)

                data = cursor.fetchall()
            except Exception as error:
                logger.error("there was a problem processing the following query: %s" % query, exc_info=error)
                send_exception_mail("there was a problem processing the following query: %s" % query
                                    + "\n\n" + traceback.format_exc())

                return None
            else:
                if not data:
                    logger.debug("fetching data from database was successful, but no result were found")

                    return []

                logger.debug("fetching data from database was successful")

                return [dict(zip(cursor.column_names, date)) for date in data]

    def runQueryOnDatabase(self, query: str, parameters: Tuple = None) -> bool:
        """
        Saves the given changes to the database. Returns a bool for knowing if the query was successful.

        :param query: Query to save
        :param parameters: Parameters for the query
        :return:
        """
        with self.connection.cursor() as cursor:
            # true if a query was successful, false otherwise
            success: bool = False

            try:
                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)
            except Exception as error:
                logger.error("couldn't run changes on database, query: %s, param: %s" % (query, parameters), exc_info=error)
                send_exception_mail(traceback.format_exc())
            else:
                success = True
            finally:
                self.connection.commit()

                return success

    def _createConnection(self) -> MySQLConnection | None:
        """
        Creates a connection to our database

        :return:
        """
        connection = None

        try:
            connection = mysql.connector.connect(
                user=getParameter(Parameters.USER),
                password=getParameter(Parameters.PASSWORD),
                host=getParameter(Parameters.HOST),
                database=getParameter(Parameters.NAME),
            )
        except Exception as error:
            logger.error("COULDN'T ESTABLISH CONNECTION TO DATABASE", exc_info=error)
            send_exception_mail(traceback.format_exc())

            return None

        if connection is None:
            logger.error("COULDN'T ESTABLISH CONNECTION TO DATABASE: connection is None")
            send_exception_mail("couldn't establish connection to database, returns from MySQL was None")

            return None

        return connection

    def __del__(self):
        if self.connection:
            self.connection.close()
