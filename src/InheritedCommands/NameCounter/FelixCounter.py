from src.InheritedCommands.NameCounter.Counter import Counter


class FelixCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Felix', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['felix_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['felix_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['felix_counter']
