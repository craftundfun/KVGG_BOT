import logging

from discord import Member

from src.DiscordParameters.NotificationType import NotificationType
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Repository.NotificationSettingRepository import getNotificationSettings_OLD
from src.Services.Database_Old import Database_Old

logger = logging.getLogger("KVGG_BOT")


class UserSettings:

    def __init__(self):
        pass

    def _saveToDatabase(self, param: dict, tableName: str, database: Database_Old) -> bool:
        """
        Saves the changes to the database.
        """
        query, nones = writeSaveQuery(tableName, param['id'], param)

        if not database.runQueryOnDatabase(query, nones):
            logger.error(f"couldn't save changes to database")

            return False

        return True

    def _getNotificationSettings(self, member: Member, database: Database_Old) -> dict | None:
        """
        Returns the notification settings from the given Member.

        :param member: Member to fetch the settings of
        """
        query = "SELECT * FROM notification_setting WHERE discord_id = (SELECT id FROM discord WHERE user_id = %s)"

        if not (settings := database.fetchOneResult(query, (member.id,))):
            logger.error(f"couldn't fetch settings for {member.name} from database")

            return None

        return settings

    def changeNotificationSetting(self, member: Member, kind: str, setting: bool) -> str:
        """
        Changes the notification setting for coming online

        :param member: Member, who wants to change the settings
        :param kind: Type of setting
        :param setting: New value
        :raise ConnectionError: if the database connection cant be established
        :return: Answer
        """
        database = Database_Old()
        settings = getNotificationSettings_OLD(member, database)

        if not settings:
            logger.error("couldn't fetch settings")

            return "Es gab ein Problem!"

        # database rows
        settings_keys = NotificationType.getValues()

        if kind in settings_keys:
            settings[kind] = 1 if setting else 0
        else:
            logger.critical(f"undefined value was reached: {kind}")

            return "Es gab ein Problem! Es wurde nichts geändert."

        if not self._saveToDatabase(settings, "notification_setting", database):
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem! Es wurde nichts geändert."

        logger.debug("saved changes to database")

        return "Deine Einstellung wurde erfolgreich gespeichert!"

    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str) -> str:
        """
        Lets the user change their WhatsApp settings

        :param member: Member, who requested a change of his / her settings
        :param type: Type of messages (gaming or university)
        :param action: Action of the messages (join or leave)
        :param switch: Switch (on / off)
        :raise ConnectionError: if the database connection can't be established
        :return:
        """
        logger.debug("%s requested a change of his / her WhatsApp settings" % member.name)

        database = Database_Old()

        query = "SELECT * " \
                "FROM whatsapp_setting " \
                "WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

        whatsappSettings = database.fetchOneResult(query, (member.id,))

        if not whatsappSettings:
            logger.warning("couldn't fetch corresponding settings!")

            return "Du bist nicht als User für WhatsApp-Nachrichten bei uns registriert!"

        if type == 'Gaming':
            # !whatsapp join
            if action == 'join':
                # !whatsapp join on
                if switch == 'on':
                    whatsappSettings['receive_join_notification'] = 1
                # !whatsapp join off
                elif switch == 'off':
                    whatsappSettings['receive_join_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
            # !whatsapp leave
            elif action == 'leave':
                # !whatsapp leave on
                if switch == 'on':
                    whatsappSettings['receive_leave_notification'] = 1
                # !whatsapp leave off
                elif switch == 'off':
                    whatsappSettings['receive_leave_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
        # !whatsapp uni
        elif type == 'Uni':
            if action == 'join':
                if switch == 'on':
                    whatsappSettings['receive_uni_join_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_join_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."
            elif action == 'leave':
                if switch == 'on':
                    whatsappSettings['receive_uni_leave_notification'] = 1
                elif switch == 'off':
                    whatsappSettings['receive_uni_leave_notification'] = 0
                else:
                    logger.critical("undefined entry was reached")

                    return "Es gab ein Problem."

        if self._saveToDatabase(whatsappSettings, "whatsapp_setting", database):
            logger.debug("saved changes to database")

            return "Deine Einstellung wurde übernommen!"
        else:
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem beim Speichern deiner Einstellung."
