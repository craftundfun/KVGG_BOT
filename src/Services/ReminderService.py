from __future__ import annotations

import logging
from datetime import datetime, timedelta

import discord
from discord import Member
from sqlalchemy import select, insert, null, delete
from sqlalchemy.orm.exc import NoResultFound

from src.Helper.CheckDateAgainstRegex import checkDateAgainstRegex, checkTimeAgainstRegex
from src.Helper.SendDM import sendDM, separator
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.DiscordUser.Entity.WhatsappSetting import WhatsappSetting
from src.Repository.Reminder.Entity.Reminder import Reminder
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
        """
        Creates a timer based on the reminder system
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        if len(name) > 1000:
            logger.debug(f"name for timer is too long by {member.display_name}")

            return "Bitte gib einen kürzeren Namen ein!"

        if minutes <= 0:
            logger.debug(f"negative number of minutes given by {member.display_name}")

            return "Deine angegebene Zeit muss sich in der Zukunft befinden!"
        elif minutes > 525960:
            logger.debug(f"{member.display_name} wanted to time a timer for over a year in the future")

            return "Bitte stell deinen Timer auf unter ein Jahr ein! Das sollte doch möglich sein, oder?"

        now = datetime.now()
        timeToSent = now + timedelta(minutes=minutes)

        insertQuery = insert(Reminder).values(discord_user_id=(select(DiscordUser.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery()),
                                              content=name,
                                              time_to_sent=timeToSent,
                                              sent_at=null(),
                                              whatsapp=False,
                                              repeat_in_minutes=null(),
                                              is_timer=True, )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldnt save Timer to database for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

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
        :param date: Date of the Reminder
        :param time: Time of the Reminder
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if not checkDateAgainstRegex(date):
            logger.debug(f"the given date had a incorrect format by {member.display_name}")

            return ("Dein Datum war falsch! Bitte halte dich an das korrekt Format: 'dd/mm/yyyy', 'dd-mm-yyyy' oder "
                    "'dd.mm.yyyy'.")

        if not checkTimeAgainstRegex(time):
            logger.debug(f"the given time had a incorrect format by {member.display_name}")

            return "Deine Uhrzeit war falsch! Bitte halte dich an das korrekte Format: 'HH:MM' oder 'H:MM'."

        # replace '/' with '.'
        date = date.replace("/", ".")
        # replace '-' with '.' incase the user didn't use '/'
        date = date.replace("-", ".")
        completeDate = date + " " + time

        try:
            date = datetime.strptime(completeDate, "%d.%m.%Y %H:%M")
        except ValueError:
            logger.debug(f"{completeDate} couldn't be translated to a datetime object from {member.display_name}")

            return "Es ist ein Fehler beim Konvertieren des Datums aufgetreten!"

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
                    logger.debug(f"{member.display_name} chose a date in the past and repetition was also in past")

                    return ("Dein Zeitpunkt inklusive der Wiederholung liegt in der Vergangenheit! "
                            "Bitte wähle einen in der Zukunft!")
            elif repeatTime and not repeatType:
                return "Du hast die Zeit mit angeben (wiederhole_alle), aber nicht die Art der Zeit!"
            elif repeatType and not repeatTime:
                return "Du hast die Art mit angeben (art_der_zeit), aber nicht die Menge an Zeit!"
            else:
                return "Dein Zeitpunkt liegt in der Vergangenheit! Bitte wähle einen in der Zukunft!"

        if len(content) > 1000:
            logger.debug(f"content is too long by {member.display_name}")

            return "Bitte gib einen kürzeren Text ein!"

        minutesLeft = __getMinutesLeft()

        if not (session := getSession()):
            return "Es gab einen Fehler!"

        if whatsapp:
            getQuery = (select(WhatsappSetting)
                        .where(WhatsappSetting.discord_user_id == (select(DiscordUser.id)
                                                                   .where(DiscordUser.user_id == str(member.id))
                                                                   .scalar_subquery())))
            try:
                whatsappSetting = session.scalars(getQuery).one()
            except NoResultFound:
                logger.debug(f"{member.display_name} cannot receive whatsapp notifications")

                answerAppendix = "Allerdings kannst du keine Whatsapp-Benachrichtigungen bekommen."
                whatsapp: bool = False
            except Exception as error:
                logger.error(f"couldn't fetch WhatsappSettings for {member.display_name}", exc_info=error)
                session.rollback()
                session.close()

                return "Es ist ein Fehler aufgetreten!"
            else:
                whatsapp: bool = True
        else:
            whatsapp: bool = False

        insertQuery = insert(Reminder).values(content=content,
                                              time_to_sent=date,
                                              sent_at=null(),
                                              whatsapp=whatsapp,
                                              repeat_in_minutes=minutesLeft,
                                              discord_user_id=(select(DiscordUser.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery()), )

        try:
            session.execute(insertQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't insert new Reminder for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

        return "Deine Erinnerung wurde erfolgreich gespeichert! " + \
            (answerAppendix if 'answerAppendix' in locals() else "")

    def listReminders(self, member: Member) -> [PaginationViewDataItem]:
        """
        Lists all active reminders from the user

        :param member: Member, who asked for his / her remainders
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        if not (session := getSession()):
            return [PaginationViewDataItem(field_name="Es gab einen Fehler!")]

        getQuery = (select(Reminder)
                    .where(Reminder.discord_user_id == (select(DiscordUser.id)
                                                        .where(DiscordUser.user_id == str(member.id))
                                                        .scalar_subquery()),
                           Reminder.time_to_sent is not None, ))

        try:
            reminders = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch reminders for {member.display_name}", exc_info=error)

            return [PaginationViewDataItem(field_name="Es gab einen Fehler!")]
        finally:
            session.close()

        if not reminders:
            logger.debug(f"{member.display_name} has no active reminders")

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
            repetition = getTimeFromRepeatInMinutes(reminder.repeat_in_minutes)

            allReminder += [
                PaginationViewDataItem(
                    field_name=f"__**{reminder.content}**__",
                    field_value=f"**Zeitpunkt**: {reminder.time_to_sent.strftime('%d.%m.%Y %H:%M')} Uhr\n "
                                f"**Wiederholung**: {'aktiviert - alle %d Tage, %d Stunden, %d Minuten' % (repetition[0], repetition[1], repetition[2]) if repetition else 'deaktiviert'}\n"
                                f"**Whatsapp**: {'aktiviert' if reminder.whatsapp else 'deaktiviert'}\n"
                                f"**Typ**: {'Reminder' if not reminder.is_timer else 'Timer'}\n"
                                f"**ID**: {reminder.id}"
                )
            ]

        logger.debug(f"listed all reminders from {member.display_name}")

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
        :return:
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        try:
            id = int(id)
        except ValueError:
            logger.debug(f"the given string was not a number by {member.display_name}")

            return "Bitte gib eine korrekte ID ein!"

        getQuery = (select(Reminder)
                    .where(Reminder.discord_user_id == (select(DiscordUser.id)
                                                        .where(DiscordUser.user_id == str(member.id))
                                                        .scalar_subquery()),
                           Reminder.time_to_sent is not None, ))

        try:
            reminders = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"error while fetching Reminders for {member.display_name}", exc_info=error)
            session.close()

            return "Es gab einen Fehler!"

        if not reminders:
            logger.debug(f"no entries to delete for {member.display_name}")

            return "Du hast keine aktiven Reminders!"

        if not any(reminder.id == id for reminder in reminders):
            logger.debug(f"id was not found in personal reminders for {member.display_name}")

            return "Du hast keinen Reminder mit dieser ID!"

        deleteQuery = delete(Reminder).where(Reminder.id == id)

        try:
            session.execute(deleteQuery)
            session.commit()
        except Exception as error:
            logger.error(f"couldn't delete Reminder for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

        return "Dein Reminder wurde erfolgreich gelöscht!"

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
