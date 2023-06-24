from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any
from discord import Message, Member, User
from mysql.connector import MySQLConnection


@DeprecationWarning
def __createDiscordUser(message: Message) -> None | dict:
    """
    Returns a new DiscordUser Dict with the information given by the message

    :param message:
    :return:
    """
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


def getDiscordUser(databaseConnection: MySQLConnection, member: Member) -> dict | None:
    """
    Returns the user from the database.
    If he doesn't exist yet, a new entry is created (only if a member was given)

    :param databaseConnection: DatabaseConnection to execute the query
    :param member: Member to retrieve all data from
    :return: None | Dict[Any, Any] DiscordUser
    """
    if member is None or isinstance(member, User):
        return None
    elif member.bot:
        return None

    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM discord " \
                "WHERE user_id = %s"

        cursor.execute(query, (member.id,))

        data = cursor.fetchone()

        # user does not exist yet -> create new entry
        if not data:
            query = "INSERT INTO discord (guild_id, user_id, username, created_at, time_streamed) " \
                    "VALUES (%s, %s, %s, %s, %s)"

            if member.nick:
                username = member.nick
            else:
                username = member.name

            cursor.execute(query, (member.guild.id, member.id, username, datetime.now(), 0))
            databaseConnection.commit()

            # fetch the newly added DiscordUser
            query = "SELECT * " \
                    "FROM discord " \
                    "WHERE user_id = %s"

            cursor.execute(query, (member.id,))

            data = cursor.fetchone()

            if not data:
                return None

    dcUserDb = dict(zip(cursor.column_names, data))

    # update profile picture
    if member.display_avatar != dcUserDb['profile_picture_discord'] or dcUserDb['profile_picture_discord'] is None:
        dcUserDb['profile_picture_discord'] = member.display_avatar

    # update nick if a user has one, otherwise save name (everytime if user has no nick anymore)
    if member.nick:
        if member.nick != dcUserDb['username']:
            dcUserDb['username'] = member.nick
    else:
        dcUserDb['username'] = member.name

    return dcUserDb


def getDiscordUserById(databaseConnection: MySQLConnection, userId: int) -> dict | None:
    """
    Returns a discord user from the database.
    Doesn't create one if missing or else.

    :param databaseConnection: DatabaseConnection to execute the query
    :param userId: Id of the user
    :return: dict | None
    """
    with databaseConnection.cursor() as cursor:
        query = "SELECT * FROM discord WHERE user_id = %s"

        cursor.execute(query, (userId,))

        data = cursor.fetchone()

        if not data:
            return None

        return dict(zip(cursor.column_names, data))


def getOnlineUsers(databaseConnection: MySQLConnection) -> List[Dict[Any, Any]] | None:
    """
    Retrieves all current users that are online (according to our database)

    :param databaseConnection: DatabaseConnection to execute the query
    :return: None | List[Dict[Any, Any]] List of all DiscordUsers
    """
    with databaseConnection.cursor() as cursor:
        query = "SELECT * " \
                "FROM discord " \
                "WHERE channel_id IS NOT NULL"

        cursor.execute(query)

        data = cursor.fetchall()

        if not data:
            return None

        return [dict(zip(cursor.column_names, date)) for date in data]
