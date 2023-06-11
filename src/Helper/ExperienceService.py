from __future__ import annotations
from mysql.connector import MySQLConnection, CMySQLConnection
from mysql.connector.pooling import PooledMySQLConnection


class ExperienceService:

    def __init__(self, databaseConnection:  PooledMySQLConnection | MySQLConnection | CMySQLConnection):
        self.databaseConnection = databaseConnection

    def getExperience(self, userId: int):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, last_spin_for_boost, " \
                        "active_xp_boosts " \
                    "FROM experience " \
                    "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                    "WHERE d.user_id = %s"

            cursor.execute(query, (userId, ))

            data = cursor.fetchone()

            if data:
                xp = dict(zip(cursor.column_names, list(data)))
                print(xp)


