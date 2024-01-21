from enum import Enum


class NotificationType(Enum):
    NOTIFICATION = "notifications"
    NOTIFICATION_SETTING_NAME = "Alle"

    DOUBLE_XP = "double_xp"
    DOUBLE_XP_SETTING_NAME = "Doppel-XP-Wochenende"

    WELCOME_BACK = "welcome_back"
    WELCOME_BACK_SETTING_NAME = "Willkommen"

    QUEST = "quest"
    QUEST_SETTING_NAME = "Quests"

    XP_INVENTORY = "xp_inventory"
    XP_INVENTORY_SETTING_NAME = "XP-Inventar"

    STATUS = "status_report"
    STATUS_SETTING_NAME = "Statusmeldungen"

    RETROSPECT = "retrospect"
    RETROSPECT_SETTING_NAME = "Rückblicke"

    @classmethod
    def getValues(cls) -> set[str]:
        return set(notificationType.value for notificationType in NotificationType)

    @classmethod
    def getSettingNameForType(cls, settingType: 'NotificationType') -> 'NotificationType':
        match settingType:
            case cls.NOTIFICATION:
                return cls.NOTIFICATION_SETTING_NAME

            case cls.DOUBLE_XP:
                return cls.DOUBLE_XP_SETTING_NAME

            case cls.WELCOME_BACK:
                return cls.WELCOME_BACK_SETTING_NAME

            case cls.QUEST:
                return cls.QUEST_SETTING_NAME

            case cls.XP_INVENTORY:
                return cls.XP_INVENTORY_SETTING_NAME

            case cls.STATUS:
                return cls.STATUS_SETTING_NAME

            case cls.RETROSPECT:
                return cls.RETROSPECT_SETTING_NAME

            case _:
                return None
