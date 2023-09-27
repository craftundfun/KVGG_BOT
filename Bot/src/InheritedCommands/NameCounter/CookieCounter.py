import logging

from discord import Member, Client

from Bot.src.DiscordParameters.AchievementParameter import AchievementParameter
from Bot.src.InheritedCommands.NameCounter.Counter import Counter
from Bot.src.Services.ExperienceService import ExperienceService

logger = logging.getLogger("KVGG_BOT")


class CookieCounter(Counter):

    def __init__(self, dcUserDb=None):
        super().__init__('Keks', dcUserDb)

    def getCounterValue(self) -> int:
        if self.dcUserDb:
            return self.dcUserDb['cookie_counter']
        return -1

    def setCounterValue(self, value: int, member: Member = None, client: Client = None):
        """
        Increases the counter and if a member & client exists grants him / her a cookie xp boost.

        :param client: Discord
        :param value: Value to set the counter
        :param member: Member who will receive the boost
        :return:
        """
        if self.dcUserDb:
            self.dcUserDb['cookie_counter'] = value

            if value > 0 and member and client:
                try:
                    es = ExperienceService(client)
                except ConnectionError as error:
                    logger.error("failure to start ExperienceService", exc_info=error)
                else:
                    es.grantXpBoost(member, AchievementParameter.COOKIE)

    def getCounterValueByDifferentDiscordUser(self, dcUserDb) -> int:
        return dcUserDb['cookie_counter']
