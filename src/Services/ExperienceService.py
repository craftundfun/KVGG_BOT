from __future__ import annotations

import copy
import json
import logging
import math
import random
import string
from datetime import datetime, timedelta

from discord import Client, Member

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Repository.DiscordUserRepository import getDiscordUser, getDiscordUserById
from src.Services.AchievementService import AchievementService
from src.Services.Database import Database

logger = logging.getLogger("KVGG_BOT")


def isDoubleWeekend(date: datetime) -> bool:
    """
    Returns whether it is currently double-xp-weekend

    :param date:
    :return:
    """
    return date.isocalendar()[1] % 2 == 0 and (date.weekday() == 5 or date.weekday() == 6)


class ExperienceService:

    def __init__(self, client: Client):
        """
        :param client:
        :raise ConnectionError:
        """
        self.client = client
        self.achievementService = AchievementService(self.client)
        self.database = Database()

    def __getDoubleXpWeekendInformation(self) -> string:
        """
        Returns a string with information about this or the upcoming double-xp-weekend

        :return:
        """
        if isDoubleWeekend(datetime.now()):
            return "Dieses Wochenende ist btw. Doppel-XP-Wochenende!"
        else:
            diff: timedelta = self.__getDiffUntilNextDoubleXpWeekend()

            return "Das nächste Doppel-XP-Wochenende beginnt in %s Tagen, %s Stunden und %s Minuten." % \
                (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60)

    def __getDiffUntilNextDoubleXpWeekend(self) -> timedelta:
        """
        Gets the time until the next double-xp-weekend

        :return: Timedelta of duration
        """
        now = datetime.now()  # get current time
        weekday = now.weekday()  # get current weekday
        daysUntilSaturday = (5 - weekday) % 7  # calculate days until saturday
        nextSaturday = now + timedelta(days=daysUntilSaturday)  # get date of next saturday
        nextSaturday = nextSaturday.replace(hour=0, minute=0, second=0, microsecond=0)  # set to midnight

        if isDoubleWeekend(nextSaturday):
            return nextSaturday - now
        else:
            nextNextSaturday = now + timedelta(days=daysUntilSaturday + 7)  # get next weeks saturday
            nextNextSaturday = nextNextSaturday.replace(hour=0, minute=0, second=0, microsecond=0)

            return nextNextSaturday - now

    def __getExperience(self, userId: int, lock: bool = False) -> dict | None:
        """
        Returns the Experience from the given user. If no entry exists, it will create one

        :param userId: User of the Experience
        :return:
        """
        logger.debug("fetching experience")

        query = "SELECT e.* " \
                "FROM experience AS e " \
                "INNER JOIN discord d ON e.discord_user_id = d.id " \
                "WHERE d.user_id = %s"

        if lock:
            query += " FOR UPDATE"

        xp = self.database.fetchOneResult(query, (userId,))

        if not xp:
            logger.debug("found no experience for %s" % str(userId))

            if not self.__createExperience(userId):
                logger.warning("couldn't fetch experience!")

                return None

            xp = self.database.fetchOneResult(query, (userId,))

        if xp:
            logger.debug("fetched experience")
        else:
            logger.critical("couldn't fetch experience, after creating still None")

        return xp

    def __createExperience(self, userId: int) -> bool:
        """
        Creates an Experience for the given user

        :param userId: User of the Experience
        :return: bool - Whether creation of Experience was successful
        """
        logger.debug("creating experience for %s" % str(userId))

        xpAmount = self.__calculateXpFromPreviousData(userId)
        xpBoosts = self.__calculateXpBoostsFromPreviousData(userId)
        dcUserDb = getDiscordUserById(userId)

        if dcUserDb is None:
            logger.warning("couldn't create Experience!")

            return False

        query = "INSERT INTO experience (xp_amount, discord_user_id, xp_boosts_inventory) " \
                "VALUES (%s, %s, %s)"

        return self.database.runQueryOnDatabase(query, (xpAmount, dcUserDb['id'], xpBoosts,))

    def __calculateXpBoostsFromPreviousData(self, dcUserDbId: int) -> str | None:
        """
        Calculates the XP-Boosts earned until now

        :param dcUserDbId: ID of the user
        :return: None | string JSON of earned boots, otherwise None
        """
        logger.debug("calculating xp boosts from previous data")

        query = "SELECT time_online, time_streamed FROM discord WHERE user_id = %s"

        times = self.database.fetchOneResult(query, (dcUserDbId,))

        if not times:
            return None

        timeOnline = times['time_online']
        timeStreamed = times['time_streamed']

        if not timeOnline:
            return None

        # get a floored number of grant-able boosts
        numberAchievementBoosts = timeOnline / (AchievementParameter.ONLINE_TIME_HOURS.value * 60)
        flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
        intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

        if intNumberAchievementBoosts == 0:
            logger.debug("no boosts to grant")

            # no time = no streams, so we don't have to check for that as well
            return None

        if intNumberAchievementBoosts > ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            intNumberAchievementBoosts = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value

        boosts = []

        for i in range(intNumberAchievementBoosts):
            boost = {
                'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_ONLINE.value,
                'remaining': ExperienceParameter.XP_BOOST_ONLINE_DURATION.value,
                'description': ExperienceParameter.DESCRIPTION_ONLINE.value,
            }

            boosts.append(boost)

        # if the user never streamed or inventory is already full return it
        if not timeStreamed or len(boosts) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            logger.debug("%d online boosts granted" % intNumberAchievementBoosts)

            return json.dumps(boosts)

        numberAchievementBoosts = timeStreamed / (AchievementParameter.STREAM_TIME_HOURS.value * 60)
        flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
        intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

        if intNumberAchievementBoosts == 0:
            logger.debug("no boosts to grant")

            return json.dumps(boosts)

        if len(boosts) + intNumberAchievementBoosts >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            intNumberAchievementBoosts = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value - len(boosts)

        for i in range(intNumberAchievementBoosts):
            boost = {
                'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_STREAM.value,
                'remaining': ExperienceParameter.XP_BOOST_STREAM_DURATION.value,
                'description': ExperienceParameter.DESCRIPTION_STREAM.value,
            }

            boosts.append(boost)

        logger.debug("%d online and stream boosts granted" % intNumberAchievementBoosts)

        return json.dumps(boosts)

    def __calculateXpFromPreviousData(self, userId: int) -> int:
        """
        Calculates the XP earned until now

        :param userId: User of the Experience
        :return: int
        """
        logger.debug("calculating xp from previous data")

        amount = 0
        query = "SELECT time_online, time_streamed, message_count_all_time " \
                "FROM discord " \
                "WHERE user_id = %s"
        data = self.database.fetchOneResult(query, (userId,))

        if not data:
            logger.warning("couldn't calculate previously earned xp!")

        if timeOnline := data['time_online']:
            amount += timeOnline * ExperienceParameter.XP_FOR_ONLINE.value

        if timeStreamed := data['time_streamed']:
            amount += timeStreamed * ExperienceParameter.XP_FOR_STREAMING.value

        if messages := data['message_count_all_time']:
            amount += messages * ExperienceParameter.XP_FOR_MESSAGE.value

        logger.debug("calculated %d xp" % amount)

        return amount

    def grantXpBoost(self, member: Member, kind: AchievementParameter):
        """
        Grants the member the specified xp-boost

        :param member: Member who earned the boost
        :param kind: Kind of boost
        :return:
        """
        if not isinstance(kind.value, str):
            logger.critical("false argument given")

            return

        if not (xp := self.__getExperience(member.id, True)):
            logger.debug("couldn't fetch xp for %s" % member.name)

            return

        match kind:
            case AchievementParameter.ONLINE:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_ONLINE.value,
                    'remaining': ExperienceParameter.XP_BOOST_ONLINE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_ONLINE.value,
                }
            case AchievementParameter.STREAM:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_STREAM.value,
                    'remaining': ExperienceParameter.XP_BOOST_STREAM_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_STREAM.value,
                }
            case AchievementParameter.RELATION_ONLINE:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_RELATION_ONLINE.value,
                    'remaining': ExperienceParameter.XP_BOOST_RELATION_ONLINE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_RELATION_ONLINE.value,
                }
            case AchievementParameter.RELATON_STREAM:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_RELATION_STREAM.value,
                    'remaining': ExperienceParameter.XP_BOOST_RELATION_STREAM_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_RELATION_STREAM.value,
                }
            case AchievementParameter.COOKIE:
                if lastBoost := xp['last_cookie_boost']:
                    if ((interval := (datetime.now() - lastBoost)).days
                            < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_COOKIE_BOOST.value
                            and interval.seconds
                            < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_COOKIE_BOOST.value * 24 * 60 * 60):
                        logger.debug("cant grant new cookie boost, time was not passed")

                        return

                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_COOKIE.value,
                    'remaining': ExperienceParameter.XP_BOOST_COOKIE_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_COOKIE.value,
                }
                xp['last_cookie_boost'] = datetime.now()
            case AchievementParameter.DAILY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_DAILY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_DAILY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_DAILY_QUEST.value,
                }
            case AchievementParameter.WEEKLY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_WEEKLY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_WEEKLY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_WEEKLY_QUEST.value,
                }
            case AchievementParameter.MONTHLY_QUEST:
                boost = {
                    'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_MONTHLY_QUEST.value,
                    'remaining': ExperienceParameter.XP_BOOST_MONTHLY_QUEST_DURATION.value,
                    'description': ExperienceParameter.DESCRIPTION_MONTHLY_QUEST.value,
                }
            case _:
                logger.critical("undefined enum entry was reached")

                return

        if xp['xp_boosts_inventory']:
            inventory = json.loads(xp['xp_boosts_inventory'])

            if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                logger.debug("cant grant boost, too many inactive xp boosts")

                return
        else:
            inventory = []

        # TODO remove after investigation
        invBefore = copy.deepcopy(inventory)
        inventory.append(boost)

        xp['xp_boosts_inventory'] = json.dumps(inventory)
        query, nones = writeSaveQuery(
            'experience',
            xp['id'],
            xp,
        )

        if not self.database.runQueryOnDatabase(query, nones):
            logger.error("couldn't save new xp boost to database for %s" % member.name)
        else:
            logger.debug("------------------------------------------------------")
            logger.debug("boost:")
            logger.debug(str(boost) + "\n")
            logger.debug("inventory für: %s" % member.name)
            logger.debug("vorher:")
            logger.debug(str(invBefore))
            logger.debug("nachher:")
            logger.debug(str(inventory))
            logger.debug("SQL-statement: %s" % query)

            logger.debug("saved granted boost to database for %s" % member.name)

            if xp := self.__getExperience(member.id):
                logger.debug("inventory: " + xp['xp_boosts_inventory'])
            else:
                logger.debug("couldn't fetch inventory again")

    @validateKeys
    def spinForXpBoost(self, member: Member) -> string:
        """
        Xp-Boost-Spin for member

        :param member: Member, who started the spin
        :return:
        """
        logger.debug("%s requested XP-SPIN." % member.name)

        if (dcUserDb := getDiscordUser(member)) is None:
            logger.warning("couldn't fetch DiscordUser!")

            return "Es ist etwas schief gelaufen!"

        xp = self.__getExperience(dcUserDb['user_id'])

        if xp is None:
            logger.warning("couldn't spin because of missing experience!")

            return "Es ist etwas schief gelaufen!"

        inventoryJson = xp['xp_boosts_inventory']

        if inventoryJson is None:
            inventory = []
        else:
            inventory = json.loads(inventoryJson)

        if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            logger.debug("full inventory, cant spin")

            return "Dein Inventar ist voll! Benutze erst einen oder mehrere XP-Boosts!"

        lastXpSpinTime = xp['last_spin_for_boost']

        if lastXpSpinTime is not None:
            difference: timedelta = datetime.now() - lastXpSpinTime
            days = difference.days
            hours, remainingSeconds = divmod(difference.seconds, 3600)
            minutes, remainingSeconds = divmod(remainingSeconds, 60)  # why Python, why?

            # cant spin again -> still on cooldown
            if days < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value:
                remainingDays = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value - days - 1
                remainingHours = 23 - hours
                remainingMinutes = 59 - minutes
                remainingSeconds = 59 - remainingSeconds

                logger.debug("cant spin, still on cooldown")

                if days == 6 and hours == 23 and minutes == 59:
                    return "Du darfst noch nicht wieder drehen! Versuche es in %d Sekunden wieder!" % remainingSeconds

                return "Du darfst noch nicht wieder drehen! Versuche es in %d Tag(en), %d Stunde(n) und " \
                       "%d Minute(n) wieder!" % (remainingDays, remainingHours, remainingMinutes)

        # win
        if random.randint(0, (100 / ExperienceParameter.SPIN_WIN_PERCENTAGE.value)) == 1:
            logger.debug("won xp boost")

            boost = {
                'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value,
                'remaining': ExperienceParameter.XP_BOOST_SPIN_DURATION.value,
                'description': ExperienceParameter.DESCRIPTION_SPIN.value,
            }

            inventory.append(boost)
            xp['xp_boosts_inventory'] = json.dumps(inventory)
            xp['last_spin_for_boost'] = datetime.now()
            query, nones = writeSaveQuery(
                'experience',
                xp['id'],
                xp,
            )

            if self.database.runQueryOnDatabase(query, nones):
                logger.debug("saved new xp boost to database")

                return "Du hast einen XP-Boost gewonnen!!! Für %d Stunde(n) bekommst du %d-Fach XP! Setze ihn über " \
                       "dein Inventar ein!" % (ExperienceParameter.XP_BOOST_SPIN_DURATION.value / 60,
                                               ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value)
            else:
                logger.critical("couldn't save new boost into database!")

                return ("Herzlichen Glückwunsch, du hast gewonnen! Allerdings gab es ein Problem beim speichern. "
                        "Bitte wende dich an craftundfun für weitere Hilfe :/.")
        else:
            logger.debug("did not win xp boost")

            days = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value
            xp['last_spin_for_boost'] = datetime.now()

            query, nones = writeSaveQuery(
                'experience',
                xp['id'],
                xp,
            )

            if self.database.runQueryOnDatabase(query, nones):
                logger.debug("saved date to database")
            else:
                logger.critical("couldn't save changes to database")

            return "Du hast leider nichts gewonnen! Versuche es in %d Tagen nochmal!" % days

    def getXpValue(self, dcUserDb: dict) -> dict | None:
        """
        Returns the xp for the given discord user

        :param dcUserDb:
        :return:
        """
        logger.debug("requested xp from %s" % dcUserDb['username'])

        return self.__getExperience(dcUserDb['user_id'])

    @validateKeys
    def handleXpRequest(self, member: Member, user: Member) -> string:
        """
        Handles the XP-Request of the given tag

        :param user: Tag of the requested user
        :param member: Member, who called the command
        :return: string - answer
        """
        # lazy import to avoid circular import
        from src.Services.ProcessUserInput import getTagStringFromId

        logger.debug("%s requested XP" % member.name)

        dcUserDb = getDiscordUser(user)

        if dcUserDb is None:
            logger.warning("couldn't fetch DiscordUser!")

            return "Es ist ein Fehler aufgetreten!"

        xp = self.__getExperience(dcUserDb['user_id'])

        if xp is None:
            logger.warning("couldn't fetch Experience!")

            return "Es ist ein Fehler aufgetreten!"

        reply = "%s hat bereits %d XP gefarmt!\n\n" % (getTagStringFromId(dcUserDb['user_id']), xp['xp_amount'])
        reply += self.__getDoubleXpWeekendInformation()

        logger.debug("replying xp amount")

        return reply

    @validateKeys
    def handleXpNotification(self, member: Member, setting: string) -> string:
        """
        Lets the user choose his / her double-xp-weekend notification

        :param member:
        :param setting:
        :return:
        """
        logger.debug("%s requested a change of his / her double-xp-weekend notification" % member.name)

        if setting == 'on':
            dcUserDb = getDiscordUser(member)

            if dcUserDb is None:
                logger.warning("couldn't fetch DiscordUser!")

                return "Es ist ein Fehler aufgetreten!"

            dcUserDb['double_xp_notification'] = 1
        else:
            dcUserDb = getDiscordUser(member)

            if dcUserDb is None:
                logger.warning("Couldn't fetch DiscordUser!")

                return "Es ist ein Fehler aufgetreten!"

            dcUserDb['double_xp_notification'] = 0

        query, nones = writeSaveQuery(
            'discord',
            dcUserDb['id'],
            dcUserDb
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved setting to database")

            return "Deine Einstellungen wurden gespeichert!"
        else:
            logger.critical("couldn't save changes to database")

            return "Es ist leider ein Fehler aufgetreten."

    @validateKeys
    def handleXpInventory(self, member: Member, action: str, row: str = None) -> str:
        """
        Handles the XP-Inventory

        :param member: Member, who the inventory belongs to
        :param action: Action the user wants to perform with his inventory
        :param row: Optional row to choose boost from
        :return:
        """
        logger.debug("%s requested Xp-Inventory" % member.name)

        dcUserDb: dict | None = getDiscordUser(member)

        if dcUserDb is None:
            logger.warning("couldn't fetch DiscordUser")

            return "Es ist ein Fehler aufgetreten!"

        xp = self.__getExperience(dcUserDb['user_id'])

        if xp is None:
            logger.warning("couldn't fetch Experience")

            return "Es ist ein Fehler aufgetreten!"

        if action == 'list':
            logger.debug("list-action used")

            reply = ""

            if xp['xp_boosts_inventory'] is None:
                logger.debug("no boosts in inventory")

                reply += "Du hast keine XP-Boosts in deinem Inventar!"

                if xp['active_xp_boosts']:
                    reply += "\n\n__Du hast folgende aktive XP-Boosts__:\n\n"
                    inventory = json.loads(xp['active_xp_boosts'])

                    for index, item in enumerate(inventory, start=1):
                        reply += "%d. %s-Boost, der noch für %s Minuten %s-Fach XP gibt\n" % (
                            index, item['description'], item['remaining'], item['multiplier'])

                return reply

            logger.debug("list all current and active boosts")

            reply = "__Du hast folgende XP-Boosts in deinem Inventar__:\n\n"
            inventory = json.loads(xp['xp_boosts_inventory'])

            for index, item in enumerate(inventory, start=1):
                reply += "%d. %s-Boost, für %s Minuten %s-Fach XP\n" % \
                         (index, item['description'], item['remaining'], item['multiplier'])

            if xp['active_xp_boosts'] is not None:
                reply += "\n\n__Du hast folgende aktive XP-Boosts__:\n\n"
                inventory = json.loads(xp['active_xp_boosts'])

                for index, item in enumerate(inventory, start=1):
                    reply += "%d. %s-Boost, der noch für %s Minuten %s-Fach XP gibt\n" % (
                        index, item['description'], item['remaining'], item['multiplier'])

            reply += "\nMit '/xp_inventory use zeile:1 | all' kannst du einen oder mehrere XP-Boost einsetzen!"

            return reply
        # !inventory use
        else:
            logger.debug("use-action used")

            # no xp boosts available
            if xp['xp_boosts_inventory'] is None:
                logger.debug("no boosts in inventory")

                return "Du hast keine XP-Boosts in deinem Inventar!"

            # too many xp boosts are active, cant activate another one
            if xp['active_xp_boosts'] is not None and len(
                    json.loads(xp['active_xp_boosts'])) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                logger.debug("too many boosts active")

                return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere " \
                       "es erneut!"

            # inventory use all
            if row == 'all':
                logger.debug("use all boosts")
                # list to keep track of which boosts will be used
                usedBoosts = []

                # empty active boosts => can use all boosts at once
                if xp['active_xp_boosts'] is None:
                    xp['active_xp_boosts'] = xp['xp_boosts_inventory']
                    usedBoosts = copy.deepcopy(xp['xp_boosts_inventory'])
                    xp['xp_boosts_inventory'] = None
                # xp boosts can fit into active
                elif (len(json.loads(xp['active_xp_boosts'])) + len(
                        json.loads(xp['xp_boosts_inventory']))) <= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:

                    usedBoosts = copy.deepcopy(xp['xp_boosts_inventory'])
                    inventory = json.loads(xp['xp_boosts_inventory'])
                    activeBoosts = json.loads(xp['active_xp_boosts'])
                    xp['active_xp_boosts'] = json.dumps(activeBoosts + inventory)
                    xp['xp_boosts_inventory'] = None
                # not all xp-boosts fit into active ones
                else:
                    logger.debug("choosing fitting amount of boosts")

                    numXpBoosts = len(json.loads(xp['active_xp_boosts']))
                    currentPosInInventory = 0
                    xpBoostsInventory: list = json.loads(xp['xp_boosts_inventory'])
                    activeXpBoosts: list = json.loads(xp['active_xp_boosts'])
                    inventoryAfter: list = json.loads(xp['xp_boosts_inventory'])

                    while (numXpBoosts < ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value
                           and currentPosInInventory < len(xpBoostsInventory)):
                        currentBoost = xpBoostsInventory[currentPosInInventory]

                        usedBoosts.append(currentBoost)
                        activeXpBoosts.append(currentBoost)
                        inventoryAfter.remove(currentBoost)

                        currentPosInInventory += 1
                        numXpBoosts += 1

                    xp['xp_boosts_inventory'] = json.dumps(inventoryAfter)
                    xp['active_xp_boosts'] = json.dumps(activeXpBoosts)

                answer = "Alle (möglichen) XP-Boosts wurden eingesetzt!\n\n"

                for boost in json.loads(usedBoosts):
                    answer += (f"- {boost['description']}-Boost, der für {boost['remaining']} Minuten "
                               f"{boost['multiplier']}-Fach XP gibt\n")

            # !inventory use 1
            else:
                logger.debug("using boosts in specific row")

                # inventory empty
                if xp['xp_boosts_inventory'] is None:
                    logger.debug("no boosts in inventory")

                    return "Du hast keine XP-Boosts in deinem Inventar!"
                # active inventory full
                elif xp['active_xp_boosts'] is not None and len(
                        json.loads(xp['active_xp_boosts'])) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                    logger.debug("too many active boosts")

                    return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere es erneut!"

                try:
                    if row is None:
                        raise ValueError
                    row = int(row)
                except ValueError:
                    logger.debug("entered row was no number")

                    return "Bitte gib eine korrekte Zeilennummer ein!"

                inventory: list = json.loads(xp['xp_boosts_inventory'])

                if len(inventory) >= row > 0:
                    chosenXpBoost = inventory[row - 1]

                    if xp['active_xp_boosts'] is None:
                        activeXpBoosts = []
                    else:
                        activeXpBoosts: list = json.loads(xp['active_xp_boosts'])

                    inventory.remove(chosenXpBoost)
                    activeXpBoosts.append(chosenXpBoost)

                    if not inventory:
                        xp['xp_boosts_inventory'] = None
                    else:
                        xp['xp_boosts_inventory'] = json.dumps(inventory)

                    xp['active_xp_boosts'] = json.dumps(activeXpBoosts)

                    answer = "Dein XP-Boost wurde eingesetzt! Für die nächsten %s Minuten bekommst du %s-Fach XP!" % (
                        chosenXpBoost['remaining'], chosenXpBoost['multiplier'])
                else:
                    logger.debug("number out of range")

                    return "Deine Eingabe war ungültig!"

        query, nones = writeSaveQuery(
            'experience',
            xp['id'],
            xp,
        )

        if self.database.runQueryOnDatabase(query, nones):
            logger.debug("saved changes to database")
        else:
            logger.critical("couldn't save changes to database")

        return answer

    async def addExperience(self, experienceParameter: int, member: Member = None):
        """
        Adds the given amount of xp to the given user

        :param member: Optional Member if DiscordUser is not used
        :param experienceParameter: Amount of xp
        :return:
        """
        logger.debug("%s gets XP" % member.name)

        xp = self.__getExperience(member.id)

        if xp is None:
            logger.warning("couldn't fetch Experience")

            return

        xpAmountBefore = xp['xp_amount']
        toBeAddedXpAmount = experienceParameter

        if xp['active_xp_boosts']:
            logger.debug("multiply xp with active boosts")

            for boost in json.loads(xp['active_xp_boosts']):
                # don't add the base experience everytime
                toBeAddedXpAmount += experienceParameter * boost['multiplier'] - experienceParameter

        if toBeAddedXpAmount == experienceParameter:
            if isDoubleWeekend(datetime.now()):
                xp['xp_amount'] = xpAmountBefore + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value
            else:
                xp['xp_amount'] = xpAmountBefore + experienceParameter
        else:
            if isDoubleWeekend(datetime.now()):
                xp['xp_amount'] = (xpAmountBefore + toBeAddedXpAmount
                                   + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value)
            else:
                xp['xp_amount'] = xpAmountBefore + toBeAddedXpAmount

        query, nones = writeSaveQuery(
            'experience',
            xp['id'],
            xp
        )

        if not self.database.runQueryOnDatabase(query, nones):
            logger.critical("couldn't save changes to database")

        # 99 mod 10 > 101 mod 10 -> achievement for 100
        if (xpAmountBefore % AchievementParameter.XP_AMOUNT.value
                > xp['xp_amount'] % AchievementParameter.XP_AMOUNT.value):
            # rip formatting
            await (self.
                   achievementService.
                   sendAchievementAndGrantBoost(member,
                                                AchievementParameter.XP,
                                                (xp['xp_amount'] - (xp['xp_amount']
                                                                    % AchievementParameter.XP_AMOUNT.value))))

        logger.debug("saved changes to database")

    @validateKeys
    def sendXpLeaderboard(self, member: Member) -> string:
        """
        Answers the Xp-Leaderboard

        :param member: Member, who called the command
        :return:
        """
        logger.debug("%s requested XP-Leaderboard" % member.name)

        query = "SELECT d.username, e.xp_amount " \
                "FROM experience e LEFT JOIN discord d ON e.discord_user_id = d.id " \
                "WHERE e.xp_amount != 0 " \
                "ORDER BY e.xp_amount DESC " \
                "LIMIT 10"

        users = self.database.fetchAllResults(query)

        if not users:
            logger.critical("couldn't fetch data from database - or the results were None")

            return "Es gab ein Problem."

        reply = "Folgende User haben die meisten XP:\n\n"

        for index, user in enumerate(users):
            reply += "%d. %s - %s XP\n" % (index, user['username'], '{:,}'.format(user['xp_amount']).replace(',', '.'))

        return reply

    def reduceXpBoostsTime(self, member: Member):
        query = "SELECT * " \
                "FROM experience " \
                "WHERE active_xp_boosts IS NOT NULL AND discord_user_id = " \
                "(SELECT id FROM discord WHERE user_id = %s)"
        xp = self.database.fetchOneResult(query, (member.id,))

        if not xp:
            return

        if not xp['active_xp_boosts']:
            logger.debug("no boosts to reduce")

            return

        boosts = json.loads(xp['active_xp_boosts'])
        editedBoosts = []

        for boost in boosts:
            boost['remaining'] = boost['remaining'] - 1

            if boost['remaining'] > 0:
                editedBoosts.append(boost)

        if len(editedBoosts) == 0:
            boosts = None
        else:
            boosts = json.dumps(editedBoosts)

        xp['active_xp_boosts'] = boosts
        query, nones = writeSaveQuery('experience', xp['id'], xp)

        if not self.database.runQueryOnDatabase(query, nones):
            logger.critical("couldn't reduce xp boost time for %s" % member.name)
