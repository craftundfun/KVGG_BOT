import logging

import discord
from discord import Member

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Repository.DiscordUserRepository import getDiscordUser

logger = logging.getLogger("KVGG_BOT")


class ReminderService:

    def __init__(self, client: discord.Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    @validateKeys
    def createReminder(self, member: Member, content: str, timeType: str, duration: int) -> str:
        """
        Creates a new Reminder in the database

        :param member: Member, whose reminder this is
        :param content: Content of the reminder
        :param timeType: Scala of time
        :param duration: Duration in scala
        :return:
        """
        if not (dcUserDb := getDiscordUser(self.databaseConnection, member)):
            logger.debug("cant proceed, no DiscordUser")

            return "Es gab ein Problem!"

        if len(content) > 2000:
            logger.debug("content is too long")

            return "Bitte gib einen kürzeren Text ein!"

        if (timeType == "days" and duration > 100) or (timeType == "hours" and duration > 2.400) or (
                timeType == "minutes" and duration > 144000):
            logger.debug("chosen duration was larger than 100 days")

            return "Bitte wähle eine kürzere Zeitspanne!"

        match timeType:
            case "minutes":
                minutesLeft = duration

            case "hours":
                minutesLeft = duration * 60

            case "days":
                minutesLeft = duration * 24 * 60

            case _:
                logger.warning("undefined enum-entry was used")

                return "Es gab ein Problem!"

        with self.databaseConnection.cursor() as cursor:
            query = "INSERT INTO reminder (discord_user_id, content, minutes_left, sent_at) " \
                    "VALUES (%s, %s, %s, %s)"

            cursor.execute(query, (dcUserDb['id'], content, minutesLeft, None,))
            self.databaseConnection.commit()

        logger.debug("saved new reminder to database")

        return "Deine Erinnerung wurde erfolgreich gespeichert!"
