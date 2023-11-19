import logging

from discord import Member

from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


class UserSettings:

    def __init__(self):
        self.database = Database()

    def _saveToDatabase(self, param: dict, tableName: str) -> bool:
        query, nones = writeSaveQuery(tableName, param['id'], param)

        if not self.database.runQueryOnDatabase(query, nones):
            logger.error(f"couldn't save changes to database")

            return False

        return True

    def _getNotificationSettings(self, member: Member) -> dict | None:
        query = "SELECT * FROM notification_setting WHERE discord_id = (SELECT id FROM discord WHERE user_id = %s)"

        if not (settings := self.database.fetchOneResult(query, (member.id,))):
            logger.error(f"couldn't fetch settings for {member.name} from database")

            return None

        return settings

    @validateKeys
    def changeNotificationSetting(self, member: Member, kind: str, setting: bool) -> str:
        """
        Changes the notification setting for coming online

        :param member: Member, who wants to change the settings
        :param kind: Type of setting
        :param setting: New value
        :return: Answer
        """
        settings = self._getNotificationSettings(member)

        if not settings:
            logger.warning("couldn't fetch settings")

            return "Es gab ein Problem!"

        # database rows
        settings_keys = ["notifications", "double_xp", "welcome_back", "quest"]

        if kind in settings_keys:
            settings[kind] = 1 if setting else 0
        else:
            logger.critical(f"undefined value was reached: {kind}")

            return "Es gab ein Problem! Es wurde nichts geändert."

        if not self._saveToDatabase(settings, "notification_setting"):
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem! Es wurde nichts geändert."

        logger.debug("saved changes to database")

        return "Deine Einstellung wurde erfolgreich gespeichert!"

    @validateKeys
    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str) -> str:
        """
        Lets the user change their WhatsApp settings

        :param member: Member, who requested a change of his / her settings
        :param type: Type of messages (gaming or university)
        :param action: Action of the messages (join or leave)
        :param switch: Switch (on / off)
        :return:
        """
        logger.debug("%s requested a change of his / her WhatsApp settings" % member.name)

        query = "SELECT * " \
                "FROM whatsapp_setting " \
                "WHERE discord_user_id = (SELECT id FROM discord WHERE user_id = %s)"

        whatsappSettings = self.database.fetchOneResult(query, (member.id,))

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

        if self._saveToDatabase(whatsappSettings, "whatsapp_setting"):
            logger.debug("saved changes to database")

            return "Deine Einstellung wurde übernommen!"
        else:
            logger.critical("couldn't save changes to database")

            return "Es gab ein Problem beim Speichern deiner Einstellung."
