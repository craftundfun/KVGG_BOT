import string
from enum import Enum
from os import path


class Parameters(Enum):
    HOST = 0
    USER = 1
    PASSWORD = 2
    NAME = 3
    TOKEN = 4
    EMAIL_HOST = 5
    PORT = 6
    EMAIL_USER = 7
    EMAIL_PASSWORD = 8
    API_KEY = 9


def getParameter(param: Parameters) -> string:
    basepath = path.dirname(__file__)
    filepath = path.abspath(path.join(basepath, "..", "..", "parameters.yaml"))

    with open(filepath) as file:
        return file.readlines()[param.value:param.value + 1][0].strip()
