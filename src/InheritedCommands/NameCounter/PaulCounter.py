from src.InheritedCommands.NameCounter.Counter import Counter


class PaulCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Paul', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['paul_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['paul_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['paul_counter']
