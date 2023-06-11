from src.InheritedCommands.NameCounter.Counter import Counter


class CarlCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Carl', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['carl_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['carl_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['carl_counter']
