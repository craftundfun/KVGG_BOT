def getFormattedTime(onlineAfter: int) -> str:
    if onlineAfter == 0:
        return "0:00"

    return str(onlineAfter // 60) + ":" + (str(onlineAfter % 60) if onlineAfter % 60 >= 10 else "0" + str(onlineAfter % 60))
