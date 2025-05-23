from enum import Enum


class WhatsAppParameter(Enum):
    WAIT_UNTIL_SEND_LEAVE = 1
    WAIT_UNTIL_SEND_JOIN_AFTER_LEAVE = 5
    DELAY_JOIN_MESSAGE = 1
    SEND_LEAVE_AFTER_X_MINUTES_AFTER_LAST_ONLINE = 10

