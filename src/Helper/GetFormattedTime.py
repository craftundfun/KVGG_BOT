import string


def getFormattedTime(onlineAfter: string) -> string:
    return str(onlineAfter // 60) + ":" + str(onlineAfter % 60)
