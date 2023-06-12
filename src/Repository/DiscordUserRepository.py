from __future__ import annotations

from datetime import datetime, date

from mysql.connector import MySQLConnection
from discord import Message
from src.Helper import WriteSaveQuery


def createDiscordUser(message: Message) -> None | dict:
    if message.author.bot:
        return None

    if username := not message.author.nick:
        username = message.author.name

    return {
        'guild_id': message.guild.id,
        'user_id:': message.author.id,
        'username': username,
        'created_at': datetime.now().date(),
        'time_online': None
    }


# TODO accept voice things too
def getDiscordUser(databaseConnection: MySQLConnection, message: Message) -> dict | None:
    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        cursor.execute(query, (message.author.id,))

        data = cursor.fetchone()

        if not data:
            # create new DiscordUser
            data = createDiscordUser(message)

            if not data:
                return None

            # save new DiscordUser
            query, nones = WriteSaveQuery.writeSaveQuery(
                "discord",
                message.author.id,
                data
            )

            cursor.execute(query, nones)
            databaseConnection.commit()

            # fetch the newly added DiscordUser
            query = "SELECT * " \
                    "FROM discord " \
                    "WHERE user_id = %s"

            cursor.execute(query, (message.author.id,))

            data = cursor.fetchone()

    return dict(zip(cursor.column_names, data))
