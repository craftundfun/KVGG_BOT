import re

# https://stackoverflow.com/questions/15491894/regex-to-validate-date-formats-dd-mm-yyyy-dd-mm-yyyy-dd-mm-yyyy-dd-mmm-yyyy
REGEX_DATE = (r"^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|["
              r"2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:("
              r"?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:("
              r"?:1[6-9]|[2-9]\d)?\d{2})$")
# https://stackoverflow.com/questions/7536755/regular-expression-for-matching-hhmm-time-format
REGEX_TIME = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"


def checkDateAgainstRegex(date: str) -> bool:
    return bool(re.match(REGEX_DATE, date))


def checkTimeAgainstRegex(time: str) -> bool:
    return bool(re.match(REGEX_TIME, time))
