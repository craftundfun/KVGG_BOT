from src.InheritedCommands.NameCounter.Counter import Counter


class OlegCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Oleg', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['oleg_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['oleg_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['oleg_counter']
