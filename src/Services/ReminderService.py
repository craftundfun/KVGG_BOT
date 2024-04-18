from __future__ import annotations

import logging
from datetime import datetime, timedelta

import discord
from discord import Member
from sqlalchemy import select, insert, null, delete
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from src.Helper.CheckDateAgainstRegex import checkDateAgainstRegex, checkTimeAgainstRegex
from src.Helper.SendDM import sendDM, separator
from src.Id.GuildId import GuildId
from src.Manager.DatabaseManager import getSession
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Entity.WhatsappSetting import WhatsappSetting
from src.Entities.MessageQueue.Entity.MessageQueue import MessageQueue
from src.Entities.Reminder.Entity.Reminder import Reminder
from src.Entities.User.Entity.User import User
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
            logger.error(f"couldn't save Timer to database for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()

        return "Dein Timer wurde gespeichert. Du kannst ihn über `/list_reminder` oder `/delete_reminder` verwalten."

    # noinspection PyMethodMayBeStatic
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
            # noinspection PyTypeChecker
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

        # noinspection PyTypeChecker
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

        :return:
        """
        if not (session := getSession()):  # TODO outside
            return

        getQuery = select(Reminder).where(Reminder.time_to_sent.is_not(None))

        try:
            reminders = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch reminders from database", exc_info=error)
            session.close()

            return

        if not reminders:
            logger.debug("no reminders were found")

            return

        for reminder in reminders:
            if reminder.time_to_sent < datetime.now():
                await self._sendReminder(reminder, session)

        try:
            session.commit()
        except Exception as error:
            logger.error("couldn't commit Reminders", exc_info=error)
        finally:
            session.close()

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
                           Reminder.time_to_sent.is_not(None), ))

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

    async def _sendReminder(self, reminder: Reminder, session: Session):
        """
        Sends the remainder per DM (and WhatsApp) to the user

        :param reminder: Remainder entry from the database
        :raise ConnectionError: If the database connection can't be established
        :return:
        """
        member: Member = (self
                          .client
                          .get_guild(GuildId.GUILD_KVGG.value)
                          .get_member(int(reminder.discord_user.user_id)))

        if not member:
            logger.error(f"couldn't fetch {reminder.discord_user} with userId from guild")

            return

        if reminder.whatsapp:
            message = f"Hier ist {'deine Erinnerung' if not reminder.is_timer else 'dein Timer'}:\n\n{reminder.content}"
            insertQuery = insert(MessageQueue).values(message=message,
                                                      # noinspection PyTypeChecker
                                                      trigger_user_id=(select(DiscordUser.id)
                                                                       .where(DiscordUser.user_id == str(member.id))
                                                                       .scalar_subquery()),
                                                      created_at=datetime.now(),
                                                      # noinspection PyTypeChecker
                                                      user_id=(select(User.id)
                                                               .where(DiscordUser.user_id == str(member.id))
                                                               .scalar_subquery()),
                                                      is_join_message=False, )

            try:
                session.execute(insertQuery)
                session.commit()
            except Exception as error:
                logger.error(f"couldn't insert new MessageQueue for {member.display_name}", exc_info=error)
                session.rollback()

                return
            else:
                logger.debug(f"saved whatsapp into MessageQueue for {member.display_name}")

        try:
            await sendDM(member, f"Hier ist {'deine Erinnerung' if not reminder.is_timer else 'dein Timer'}:\n\n"
                         + reminder.content + separator)

            logger.debug(f"send reminder to {member.display_name}")
        except Exception as e:
            logger.error("there was a problem sending the message", exc_info=e)

            reminder.error = True

        if not reminder.repeat_in_minutes:
            reminder.time_to_sent = null()
        else:
            # noinspection PyTypeChecker
            reminder.time_to_sent = reminder.time_to_sent + timedelta(minutes=reminder.repeat_in_minutes)

        reminder.sent_at = datetime.now()

        return
