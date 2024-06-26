import logging

from discord import Member

from src.DiscordParameters.NotificationType import NotificationType
from src.Entities.DiscordUser.Repository.NotificationSettingRepository import getNotificationSettings
from src.Entities.DiscordUser.Repository.WhatsappSettingRepository import getWhatsappSetting
from src.Manager.DatabaseManager import getSession

logger = logging.getLogger("KVGG_BOT")


class UserSettings:
    # noinspection PyMethodMayBeStatic
    def changeNotificationSetting(self, member: Member, kind: str, switch: bool) -> str:
        """
        Changes the notification setting for coming online

        :param member: Member, who wants to change the settings
        :param kind: Type of setting
        :param switch: New value
        :return: Answer
        """
        if not (session := getSession()):
            return "Es gab einen Fehler!"

        if not (settings := getNotificationSettings(member, session)):
            logger.error(f"couldn't fetch NotificationSettings for {member.display_name}")
            session.close()

            return "Es gab einen Fehler!"

        setting = None

        for notificationSetting in NotificationType.getObjects():
            if notificationSetting.value.lower() == kind.lower():
                setting = notificationSetting

                break

        if not setting:
            logger.error(f"couldn't find NotificationSettingObject for {kind}")
            session.close()

            return "Es gab einen Fehler!"

        match setting:
            case NotificationType.NOTIFICATION:
                settings.notifications = switch
            case NotificationType.DOUBLE_XP:
                settings.double_xp = switch
            case NotificationType.WELCOME_BACK:
                settings.welcome_back = switch
            case NotificationType.QUEST:
                settings.quest = switch
            case NotificationType.XP_INVENTORY:
                settings.xp_inventory = switch
            case NotificationType.XP_SPIN:
                settings.xp_spin = switch
            case NotificationType.STATUS:
                settings.status_report = switch
            case NotificationType.RETROSPECT:
                settings.retrospect = switch
            case NotificationType.MEME_LIKES:
                settings.meme_likes = switch
            case NotificationType.COUNTER_CHANGE:
                settings.counter_change = switch
            case _:
                logger.error(f"undefined enum entry was reached: {setting}")
                session.rollback()
                session.close()

                return "Es gab einen Fehler!"

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit NotificationSettings for {member.display_name}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab einen Fehler!"

        session.close()
        logger.debug(f"saved NotificationSettings for {member.display_name}")

        return "Deine Einstellung wurde erfolgreich gespeichert!"

    # noinspection PyMethodMayBeStatic
    async def manageWhatsAppSettings(self, member: Member, type: str, action: str, switch: str) -> str:
        """
        Lets the user change their WhatsApp settings

        :param member: Member, who requested a change of his / her settings
        :param type: Type of messages (gaming or university)
        :param action: Action of the messages (join or leave)
        :param switch: Switch (on / off)
        :return:
        """
        logger.debug(f"{member.display_name} requested a change of his / her WhatsApp settings")

        if not (session := getSession()):
            return "Es gab einen Fehler!"

        if not (whatsappSettings := getWhatsappSetting(member, session)):
            logger.warning("no WhatsappSetting found for {member.display_name}")

            return "Du bist nicht für Whatsapp-Nachrichten bei uns eingetragen!"

        if type == 'Gaming':
            # !whatsapp join
            if action == 'join':
                # !whatsapp join on
                if switch == 'on':
                    whatsappSettings.receive_join_notification = True
                # !whatsapp join off
                elif switch == 'off':
                    whatsappSettings.receive_join_notification = False
                else:
                    logger.error("undefined entry was reached")

                    return "Es gab ein Problem."
            # !whatsapp leave
            elif action == 'leave':
                # !whatsapp leave on
                if switch == 'on':
                    whatsappSettings.receive_leave_notification = True
                # !whatsapp leave off
                elif switch == 'off':
                    whatsappSettings.receive_leave_notification = False
                else:
                    logger.error("undefined entry was reached")

                    return "Es gab ein Problem."
        # !whatsapp uni
        elif type == 'Uni':
            if action == 'join':
                if switch == 'on':
                    whatsappSettings.receive_uni_join_notification = True
                elif switch == 'off':
                    whatsappSettings.receive_uni_join_notification = False
                else:
                    logger.error("undefined entry was reached")

                    return "Es gab ein Problem."
            elif action == 'leave':
                if switch == 'on':
                    whatsappSettings.receive_uni_leave_notification = True
                elif switch == 'off':
                    whatsappSettings.receive_uni_leave_notification = False
                else:
                    logger.error("undefined entry was reached")

                    return "Es gab ein Problem."

        try:
            session.commit()
        except Exception as error:
            logger.error(f"couldn't commit changes for {member.display_name} and {whatsappSettings}", exc_info=error)
            session.rollback()
            session.close()

            return "Es gab ein Problem!"
        else:
            return "Deine Einstellung wurde übernommen!"
