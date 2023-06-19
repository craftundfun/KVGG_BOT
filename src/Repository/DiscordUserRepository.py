from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from discord import Message, Member, User
from mysql.connector import MySQLConnection


def __createDiscordUser(message: Message) -> None | dict:
    if message.author.bot:
        return None

    if username := not message.author.nick:
        username = message.author.name

    return {
        'guild_id': message.guild.id,
        'user_id': message.author.id,
        'username': username,
        'created_at': datetime.now().date(),
        'time_streamed': 0
    }


# TODO test creation of new DiscordUser and save him
def getDiscordUser(databaseConnection: MySQLConnection, member: Member) -> dict | None:
    if member is None or isinstance(member, User):  # TODO treat User
        return None
    elif member.bot:
        return None

    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        cursor.execute(query, (member.id,))

        data = cursor.fetchone()

        if not data:
            query = "INSERT INTO discord (guild_id, user_id, username, created_at, time_streamed) " \
                    "VALUES (%s, %s, %s, %s, %s)"

            if member.nick:
                username = member.nick
            else:
                username = member.name

            cursor.execute(query, (
                member.guild.id, member.id, username, datetime.now(), 0)
                           )
            databaseConnection.commit()

            # fetch the newly added DiscordUser
            query = "SELECT * " \
                    "FROM discord " \
                    "WHERE user_id = %s"

            cursor.execute(query, (member.id,))

            data = cursor.fetchone()
    # TODO update nickname here (and maybe avatar)
    return dict(zip(cursor.column_names, data))


def getOnlineUsers(databaseConnection: MySQLConnection) -> List[Dict[Any, Any]] | None:
    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM discord " \
                "WHERE channel_id IS NOT NULL"

        cursor.execute(query)

        data = cursor.fetchall()

        if not data:
            return None

        return [dict(zip(cursor.column_names, date)) for date in data]
