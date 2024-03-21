from __future__ import annotations

import logging
from datetime import datetime, timedelta

import discord
from discord import Member

from src.Helper.CheckDateAgainstRegex import checkDateAgainstRegex, checkTimeAgainstRegex
from src.Helper.SendDM import sendDM, separator
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUserOld
from src.Services.Database_Old import Database_Old
from src.View.PaginationView import PaginationViewDataItem

logger = logging.getLogger("KVGG_BOT")


class ReminderService:

    def __init__(self, client: discord.Client):
        """
        :param client:
        """
        self.client = client

    def createTimer(self, member: Member, name: str, minutes: int) -> str:
        database = Database_Old()

        if not (dcUserDb := getDiscordUserOld(member, database)):
            logger.debug("cant proceed, no DiscordUser")

            return "Es gab ein Problem!"

        if len(name) > 1000:
            logger.debug("name for timer is too long")

            return "Bitte gib einen kürzeren Namen ein!"

        if minutes <= 0:
            logger.debug(f"negative number of minutes given by {member.display_name}")

            return "Deine angegebene Zeit muss sich in der Zukunft befinden!"
        elif minutes > 525960:
            logger.debug(f"{member.display_name} wanted to time a timer for over a year in the future")

            return "Bitte stell deinen Timer auf unter ein Jahr ein!"

        now = datetime.now()
        timeToSent = now + timedelta(minutes=minutes)

        query = ("INSERT INTO reminder (discord_user_id, content, time_to_sent, sent_at, whatsapp, repeat_in_minutes,"
                 " is_timer) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s)")

        if not database.runQueryOnDatabase(query, (dcUserDb['id'],
                                                   name,
                                                   timeToSent,
                                                   None,
                                                   False,
                                                   None,
                                                   True,)):
            logger.error(f"couldn't save timer for {member.display_name}")

            return "Es gab einen Fehler!"

        return "Dein Timer wurde gespeichert. Du kannst ihn über `/list_reminder` oder `/delete_reminder` verwalten."

    def createReminder(self,
                       member: Member,
                       content: str,
                       date: str,
                       time: str,
                       whatsapp: str | None,
                       repeatTime: str | None,
                       repeatType: str | None, ) -> str:
        """
        Creates a new Reminder in the database

        :param repeatType:
        :param repeatTime:
        :param whatsapp:
        :param member: Member, whose reminder this is
        :param content: Content of the reminder
        :param date: Date of the Remider
        :param time: Time of the Reminder
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()

        if not checkDateAgainstRegex(date):
            logger.debug("the given date had a incorrect format")

            return ("Dein Datum war falsch! Bitte halte dich an das korrekt Format: 'dd/mm/yyyy', 'dd-mm-yyyy' oder "
                    "'dd.mm.yyyy'.")

        if not checkTimeAgainstRegex(time):
            logger.debug("the given time had a incorrect format")

            return "Deine Uhrzeit war falsch! Bitte halte dich an das korrekte Format: 'HH:MM' oder 'H:MM'."

        # replace / with .
        date = date.replace("/", ".")
        # replace - with . incase the user didn't use /
        date = date.replace("-", ".")
        completeDate = date + " " + time

        try:
            date = datetime.strptime(completeDate, "%d.%m.%Y %H:%M")
        except ValueError:
            logger.debug("%s couldn't be translated to a datetime object" % completeDate)

            return "Es ist ein Fehler beim konvertieren des Datums aufgetreten!"

        def __getMinutesLeft() -> int | None:
            if repeatTime and repeatType:
                match repeatType:
                    case 'minutes':
                        minutesLeft = int(repeatTime)
                    case 'hours':
                        minutesLeft = repeatTime * 60
                    case 'days':
                        minutesLeft = repeatTime * 60 * 24
                    case _:
                        logger.debug("unexpected enum entry encountered!")

                        return None

                return minutesLeft
            return None

        if date < datetime.now():
            logger.debug("user chose a date in the past")

            if minutes := __getMinutesLeft():
                date = date + timedelta(minutes=minutes)

                if date < datetime.now():
                    logger.debug("user chose a date in the past and repetition was also in past")

                    return ("Dein Zeitpunkt inklusive der Wiederholung liegt in der Vergangenheit! "
                            "Bitte wähle einen in der Zukunft!")
            elif repeatTime and not repeatType:
                return "Du hast die Zeit mit angeben (wiederhole_alle), aber nicht die Art der Zeit!"
            elif repeatType and not repeatTime:
                return "Du hast die Art mit angeben (art_der_zeit), aber nicht die Menge an Zeit!"
            else:
                return "Dein Zeitpunkt liegt in der Vergangenheit! Bitte wähle einen in der Zukunft!"

        if len(content) > 1000:
            logger.debug("content is too long")

            return "Bitte gib einen kürzeren Text ein!"

        minutesLeft = __getMinutesLeft()

        if not (dcUserDb := getDiscordUserOld(member, database)):
            logger.debug("cant proceed, no DiscordUser")

            return "Es gab ein Problem!"

        if whatsapp:
            query = "SELECT * " \
                    "FROM whatsapp_setting " \
                    "WHERE discord_user_id = %s"
            data = database.fetchOneResult(query, (dcUserDb['id'],))

            if not data:
                logger.debug("User cannot receive whatsapp notifications")

                answerAppendix = "Allerdings kannst du keine Whatsapp-Benachrichtigungen bekommen."
                whatsapp = False
            else:
                logger.debug("user registered for whatsapp reminder as well")

                whatsapp = True

            # delete unnecessary data overhead
            del data
        else:
            whatsapp = False

        query = "INSERT INTO reminder " \
                "(discord_user_id, content, time_to_sent, sent_at, whatsapp, repeat_in_minutes) " \
                "VALUES (%s, %s, %s, %s, %s, %s)"

        if database.runQueryOnDatabase(query, (dcUserDb['id'],
                                               content,
                                               date,
                                               None,
                                               whatsapp,
                                               minutesLeft,)):
            logger.debug("saved new reminder to database")
        else:
            return "Es gab ein Problem beim speicher des Reminders."

        return "Deine Erinnerung wurde erfolgreich gespeichert! " + \
            (answerAppendix if 'answerAppendix' in locals() else "")

    def listReminders(self, member: Member) -> [PaginationViewDataItem]:
        """
        Lists all active reminders from the user

        :param member: Member, who asked for his / her remainders
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()
        query = "SELECT * " \
                "FROM reminder " \
                "WHERE (SELECT id FROM discord WHERE user_id = %s) = discord_user_id " \
                "and time_to_sent IS NOT NULL"
        reminders = database.fetchAllResults(query, (int(member.id),))

        if not reminders:
            logger.debug("reminders for %s were empty" % member.name)

            return [PaginationViewDataItem(field_name="Du hast aktuell keine Reminder.")]

        def getTimeFromRepeatInMinutes(minutes: int | None) -> (int, int, int) | None:
            """
            Calculates the days, hours and minutes from repeat_in_minutes from each reminder.

            :param minutes: Minutes for each repetition to convert into days, hours and minutes
            """
            if not minutes:
                return None

            days = minutes // (24 * 60)
            remainingMinutes = minutes % (24 * 60)
            hours = remainingMinutes // 60
            minutes = remainingMinutes % 60

            return days, hours, minutes

        allReminder: [PaginationViewDataItem] = []

        for reminder in reminders:
            repetition = getTimeFromRepeatInMinutes(reminder['repeat_in_minutes'])

            allReminder += [
                PaginationViewDataItem(
                    field_name=f"__**{reminder['content']}**__",
                    field_value=f"**Zeitpunkt**: {reminder['time_to_sent'].strftime('%d.%m.%Y %H:%M')} Uhr\n "
                                f"**Wiederholung**: {'aktiviert - alle %d Tage, %d Stunden, %d Minuten' % (repetition[0], repetition[1], repetition[2]) if repetition else 'deaktiviert'}\n"
                                f"**Whatsapp**: {'aktiviert' if reminder['whatsapp'] else 'deaktiviert'}\n"
                                f"**Typ**: {'Reminder' if not reminder['is_timer'] else 'Timer'}\n"
                                f"**ID**: {reminder['id']}"
                )
            ]

        logger.debug("listed all reminders from %s" % member.name)

        return allReminder

    async def manageReminders(self):
        """
        Reduces all outstanding reminders times and initiates the sending process

        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()

        query = "SELECT r.*, d.user_id " \
                "FROM reminder r INNER JOIN discord d on r.discord_user_id = d.id " \
                "WHERE time_to_sent is NOT NULL"
        reminders = database.fetchAllResults(query)

        if not reminders:
            logger.debug("no reminders were found")

            return

        tempReminders = []

        for reminder in reminders:
            if reminder['time_to_sent'] < datetime.now():
                reminder = await self._sendReminder(reminder)

            tempReminders.append(reminder)

        reminders = tempReminders

        for reminder in reminders:
            # remove column that does not exist in the reminder field list
            reminder.pop('user_id', None)

            query, nones = writeSaveQuery("reminder", reminder['id'], reminder)

            if not database.runQueryOnDatabase(query, nones):
                logger.critical("couldn't save reminder into database, id: %s" % str(reminder['id']))

    def deleteReminder(self, member: Member, id: int) -> str:
        """
        Deletes the wanted reminder from the database, but only if the user has outstanding ones and the id belongs to
        the specific user

        :param member:
        :param id:
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()

        try:
            id = int(id)
        except ValueError:
            logger.debug("the given string was not a number")

            return "Bitte gib eine korrekte ID ein!"

        query = "SELECT r.* " \
                "FROM reminder r INNER JOIN discord d ON r.discord_user_id = d.id " \
                "WHERE d.user_id = %s AND r.time_to_sent IS NOT NULL"

        reminders = database.fetchAllResults(query, (member.id,))

        if not reminders:
            logger.debug("no entries to delete")

            return "Du hast keine aktiven Reminders!"

        if not any(reminder['id'] == id for reminder in reminders):
            logger.debug("id was not found in personal reminders")

            return "Du hast keinen Reminder mit dieser ID!"

        query = "DELETE FROM reminder WHERE id = %s"

        if not database.runQueryOnDatabase(query, (id,)):
            logger.critical(f"couldnt save changes to database: {query}, id: {id}")
        else:
            logger.debug("deleted entry from database")

        return "Dein Reminder wurde erfolgreich gelöscht."

    async def _sendReminder(self, reminder: dict) -> dict:
        """
        Sends the remainder per DM (and WhatsApp) to the user

        :param reminder: Remainder entry from the database
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        database = Database_Old()

        member: Member = self.client.get_guild(GuildId.GUILD_KVGG.value).get_member(int(reminder["user_id"]))

        if not member:
            logger.warning("couldn't fetch member with userId from Guild")

            return reminder

        if reminder['whatsapp']:
            query = "INSERT INTO message_queue (message, user_id, created_at, trigger_user_id, is_join_message) " \
                    "VALUES (%s, " \
                    "(SELECT id FROM user WHERE discord_user_id = " \
                    "(SELECT id FROM discord WHERE user_id = %s LIMIT 1) LIMIT 1), " \
                    "%s, " \
                    "(SELECT id FROM discord WHERE user_id = %s LIMIT 1), " \
                    "FALSE)"

            if not database.runQueryOnDatabase(query,
                                               (f"Hier ist "
                                                f"{'deine Erinnerung' if not reminder['is_timer'] else 'dein Timer'}"
                                                f":\n\n" + reminder['content'],
                                                member.id,
                                                datetime.now(),
                                                member.id,)):
                logger.critical("couldn't save message into database")
            else:
                logger.debug("saved whatsapp into message queue")

        try:
            await sendDM(member, f"Hier ist {'deine Erinnerung' if not reminder['is_timer'] else 'dein Timer'}:\n\n"
                         + reminder['content'] + separator)

            logger.debug("send reminder to %s" % member.name)
        except discord.HTTPException as e:
            logger.error("there was a problem sending the DM", exc_info=e)

            reminder['error'] = True
        except Exception as e:
            logger.error("there was a problem sending the message", exc_info=e)

            reminder['error'] = True

        if not reminder['repeat_in_minutes']:
            reminder['time_to_sent'] = None
        else:
            reminder['time_to_sent'] = reminder['time_to_sent'] + timedelta(minutes=reminder['repeat_in_minutes'])

        reminder['sent_at'] = datetime.now()

        return reminder
