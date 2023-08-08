import logging
from datetime import datetime

import discord
from discord import Member

from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.SendDM import sendDM
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
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
        try:
            duration = int(duration)
        except ValueError:
            logger.debug("the given string was not a number")

            return "Bitte gib eine (korrekte) Zahl ein!"

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

    @validateKeys
    def listReminders(self, member: Member) -> str:
        """
        Lists all active reminders from the user

        :param member: Member, who asked for his / her remainders
        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT * " \
                    "FROM reminder " \
                    "WHERE (SELECT id FROM discord WHERE user_id = %s) = discord_user_id " \
                    "and minutes_left >= 0 and sent_at IS NULL and error = FALSE"

            cursor.execute(query, (int(member.id),))

            if not (data := cursor.fetchall()):
                logger.debug("reminders for %s were empty" % member.name)

                return "Du hast keine aktiven Reminders."

            reminders = [dict(zip(cursor.column_names, date)) for date in data]

        answer = "Du hast folgende Reminder: (die vorderen Zahlen sind die individuellen IDs)\n\n"

        for reminder in reminders:
            answer += "%d: '%s' in %d Minuten\n" % (reminder['id'], reminder['content'], reminder['minutes_left'])

        logger.debug("listed all reminders from %s" % member.name)
        return answer

    async def manageReminders(self):
        """
        Reduces all outstanding reminders times and initiates the sending process

        :return:
        """
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT r.*, d.user_id " \
                    "FROM reminder r INNER JOIN discord d on r.discord_user_id = d.id " \
                    "WHERE r.sent_at IS NULL and r.minutes_left >= 0 and r.error is FALSE"

            cursor.execute(query)

            if not (data := cursor.fetchall()):
                logger.debug("no reminders were found")

                return

            reminders = [dict(zip(cursor.column_names, date)) for date in data]

        tempReminders = []

        for reminder in reminders:
            reminder['minutes_left'] = reminder['minutes_left'] - 1

            if reminder['minutes_left'] <= 0:
                reminder = await self.__sendReminder(reminder)

            tempReminders.append(reminder)

        reminders = tempReminders

        with self.databaseConnection.cursor() as cursor:
            for reminder in reminders:
                # remove column that does not exist in the reminder field list
                reminder.pop('user_id', None)

                query, nones = writeSaveQuery("reminder", reminder['id'], reminder)

                cursor.execute(query, nones)

            self.databaseConnection.commit()

    @validateKeys
    def deleteReminder(self, member: Member, id: int) -> str:
        """
        Deletes the wanted reminder from the database, but only if the user has outstanding ones and the id belongs to
        the specific user

        :param member:
        :param id:
        :return:
        """
        try:
            id = int(id)
        except ValueError:
            logger.debug("the given string was not a number")

            return "Bitte gib eine korrekte ID ein!"

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT r.* " \
                    "FROM reminder r INNER JOIN discord d ON r.discord_user_id = d.id " \
                    "WHERE d.user_id = %s and r.minutes_left > 0 and r.sent_at IS NULL AND r.error IS FALSE"

            cursor.execute(query, (member.id,))

            if not (data := cursor.fetchall()):
                logger.debug("no entries to delete")

                return "Du hast keine aktiven Reminders!"

            reminders = [dict(zip(cursor.column_names, date)) for date in data]

        if not any(reminder['id'] == id for reminder in reminders):
            logger.debug("id was not found in personal reminders")

            return "Du hast keinen Reminder mit dieser ID!"

        with self.databaseConnection.cursor() as cursor:
            query = "DELETE FROM reminder WHERE id = %s"

            cursor.execute(query, (id,))
            self.databaseConnection.commit()

        logger.debug("deleted entry from database")
        return "Dein Reminder wurde erfolgreich gelöscht."

    async def __sendReminder(self, reminder: dict) -> dict:
        """
        Sends the remainder per DM to the user

        :param reminder: Remainder entry from the database
        :return:
        """
        member = self.client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(reminder["user_id"]))

        if not member:
            logger.warning("couldn't fetch member with userId from Guild")

            return reminder

        try:
            await sendDM(member, "Hier ist deine Erinnerung:\n\n" + reminder['content'])

            reminder['minutes_left'] = None
            reminder['sent_at'] = datetime.now()

            logger.debug("send remainder to %s" % member.name)
        except discord.HTTPException as e:
            logger.error("there was a problem sending the DM", exc_info=e)

            reminder['minutes_left'] = None
            reminder['error'] = True
        except Exception as e:
            logger.error("there was a problem sending the message")

            reminder['minutes_left'] = None
            reminder['error'] = True

        return reminder
