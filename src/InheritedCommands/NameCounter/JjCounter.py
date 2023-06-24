from src.InheritedCommands.NameCounter.Counter import Counter


class JjCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('JJ', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['jj_counter']
        return -1

    def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['jj_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['jj_counter']
