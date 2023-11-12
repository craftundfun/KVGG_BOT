from src.InheritedCommands.NameCounter.Counter import Counter


class ReneCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Rene', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['rene_counter']
        return -1

    async def setCounterValue(self, value: int):
        if self.dcUserDb:
            self.dcUserDb['rene_counter'] = value

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['rene_counter']
