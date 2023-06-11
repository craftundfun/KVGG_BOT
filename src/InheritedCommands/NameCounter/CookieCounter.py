from src.InheritedCommands.NameCounter.Counter import Counter


class CookieCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Keks', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['cookie_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['cookie_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['cookie_counter']
