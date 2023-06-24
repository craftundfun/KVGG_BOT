from src.InheritedCommands.NameCounter.Counter import Counter


class BjarneCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Bjarne', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['bjarne_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['bjarne_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['bjarne_counter']
