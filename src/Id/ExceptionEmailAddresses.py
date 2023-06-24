from enum import Enum


class ExceptionEmailAddresses(Enum):
    EMAIL_BJARNE = "bjarneblu@gmail.com"
    EMAIL_ALEX = "alex.richter39@gmail.com"
    EMAIL_RENE = "rene.mlodoch@gmail.com"

    @classmethod
    def getValues(cls) -> set:
        return set(channel.value for channel in ExceptionEmailAddresses)
