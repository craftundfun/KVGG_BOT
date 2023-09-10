import string


def getFormattedTime(onlineAfter: string) -> str:
    return str(onlineAfter // 60) + ":" + (str(onlineAfter % 60) if onlineAfter % 60 >= 10 else "0" + str(onlineAfter % 60))
