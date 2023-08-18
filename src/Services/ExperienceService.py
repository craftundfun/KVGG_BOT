from __future__ import annotations

import json
import logging
import math
import random
import string
import discord

from discord import Client, Member
from datetime import datetime, timedelta
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper import WriteSaveQuery
from src.Helper.CreateNewDatabaseConnection import getDatabaseConnection
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser, getDiscordUserById
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys
from src.Helper.SendDM import sendDM

logger = logging.getLogger("KVGG_BOT")


def isDoubleWeekend(date: datetime) -> bool:
    """
    Returns whether it is currently double-xp-weekend

    :param date:
    :return:
    """
    return date.isocalendar()[1] % 2 == 0 and (date.weekday() == 5 or date.weekday() == 6)


def getDiffUntilNextDoubleXpWeekend() -> timedelta:
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


def getDoubleXpWeekendInformation() -> string:
    """
    Returns a string with information about this or the upcoming double-xp-weekend

    :return:
    """
    if isDoubleWeekend(datetime.now()):
        return "Dieses Wochenende ist btw. Doppel-XP-Wochenende!"
    else:
        diff: timedelta = getDiffUntilNextDoubleXpWeekend()

        return "Das nächste Doppel-XP-Wochenende beginnt in %s Tagen, %s Stunden und %s Minuten." % \
            (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60)


async def informAboutDoubleXpWeekend(dcUserDb: dict, client: discord.Client):
    """
    Sends a DM to the given user to inform him about the currently active double-xp-weekend

    :param dcUserDb: DiscordUser, who will be informed
    :param client: Bot
    :return:
    """
    if not dcUserDb['double_xp_notification'] or not isDoubleWeekend(datetime.now()):
        return

    await client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(int(dcUserDb['user_id']))
    member = client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

    await sendDM(member, "Dieses Wochenende gibt es doppelte XP! Viel Spaß beim farmen.\n\nWenn du diese "
                         "Benachrichtigung nicht mehr erhalten möchtest, kannst du sie in '#bot-commands'"
                         "auf dem Server mit '/notifications' de- bzw. aktivieren!")

    logger.debug("sent double xp notification")


class ExperienceService:

    def __init__(self, client: Client):
        self.databaseConnection = getDatabaseConnection()
        self.client = client

    def __getExperience(self, userId: int) -> dict | None:
        """
        Returns the Experience from the given user. If no entry exists, it will create one

        :param userId: User of the Experience
        :return:
        """
        logger.debug("fetching experience")

        query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, last_spin_for_boost, " \
                "active_xp_boosts " \
                "FROM experience " \
                "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                "WHERE d.user_id = %s"

        with self.databaseConnection.cursor() as cursor:
            cursor.execute(query, (userId,))

            if not (data := cursor.fetchone()):
                logger.debug("found no experience for %s" % str(userId))

                if not self.__createExperience(userId):
                    logger.warning("couldn't fetch Experience!")

                    return None

                cursor.execute(query, (userId,))

                if not (data := cursor.fetchone()):
                    logger.warning("couldn't fetch Experience!")

                    return None

        logger.debug("fetched experience")

        return dict(zip(cursor.column_names, data))

    def __createExperience(self, userId: int) -> bool:
        """
        Creates an Experience for the given user

        :param userId: User of the Experience
        :return: bool - Whether creation of Experience was successful
        """
        logger.debug("creating experience for %s" % str(userId))

        xpAmount = self.__calculateXpFromPreviousData(userId)
        xpBoosts = self.__calculateXpBoostsFromPreviousData(userId)
        dcUserDb = getDiscordUserById(self.databaseConnection, userId)

        if dcUserDb is None:
            logger.warning("couldn't create Experience!")

            return False

        with self.databaseConnection.cursor() as cursor:
            query = "INSERT INTO experience (xp_amount, discord_user_id, xp_boosts_inventory) " \
                    "VALUES (%s, %s, %s)"

            cursor.execute(query, (xpAmount, dcUserDb['id'], xpBoosts))
            self.databaseConnection.commit()

            logger.debug("saved experience into database")

        return True

    def __calculateXpBoostsFromPreviousData(self, dcUserDbId: int) -> str | None:
        """
        Calculates the XP-Boosts that were earned until now

        :param dcUserDbId: Id of the user
        :return: None | string JSON of earned boots, otherwise None
        """
        logger.debug("calculating xp boosts from previous data")

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT time_online FROM discord WHERE user_id = %s"

            cursor.execute(query, (dcUserDbId,))

            if not (data := cursor.fetchone()):
                logger.warning("couldn't calculate xp boosts")

                return None

            timeOnline = dict(zip(cursor.column_names, data))['time_online']

        if not timeOnline:
            return None

        # get a floored number of grant-able boosts
        numberAchievementBoosts = timeOnline / (ExperienceParameter.XP_BOOST_FOR_EVERY_X_HOURS.value * 60)
        flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
        intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

        if intNumberAchievementBoosts == 0:
            logger.debug("no boosts to grant")

            return None

        if intNumberAchievementBoosts > ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            intNumberAchievementBoosts = ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value

        boosts = []

        for i in range(intNumberAchievementBoosts):
            boost = {
                'multiplier': ExperienceParameter.XP_BOOST_MULTIPLIER_ACHIEVEMENT.value,
                'remaining': ExperienceParameter.XP_BOOST_ACHIEVEMENT_DURATION.value,
                'description': ExperienceParameter.DESCRIPTION_ACHIEVEMENT.value,
            }

            boosts.append(boost)

        logger.debug("%d boosts granted" % intNumberAchievementBoosts)

        return json.dumps(boosts)

    def __calculateXpFromPreviousData(self, userId: int) -> int:
        """
        Calculates the XP that was earned until now

        :param userId: User of the Experience
        :return: int
        """
        logger.debug("calculating xp from previous data")

        amount = 0

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT time_online, time_streamed, message_count_all_time " \
                    "FROM discord " \
                    "WHERE user_id = %s"

            cursor.execute(query, (userId,))

            if not (data := cursor.fetchone()):
                logger.warning("Couldn't calculate previously earned xp!")

                return 0

            data = dict(zip(cursor.column_names, data))

        if timeOnline := data['time_online']:
            amount += timeOnline * ExperienceParameter.XP_FOR_ONLINE.value

        if timeStreamed := data['time_streamed']:
            amount += timeStreamed * ExperienceParameter.XP_FOR_STREAMING.value

        if messages := data['message_count_all_time']:
            amount += messages * ExperienceParameter.XP_FOR_MESSAGE.value

        logger.debug("calculated %d xp" % amount)

        return amount

    @DeprecationWarning
    def checkAndGrantXpBoost(self):
        pass  # only necessary for cronjob

    @validateKeys
    async def spinForXpBoost(self, member: Member) -> string:
        """
        Xp-Boost-Spin for member

        :param member: Member, who started the spin
        :return:
        """
        logger.debug("%s requested XP-SPIN." % member.name)

        if (dcUserDb := getDiscordUser(self.databaseConnection, member)) is None:
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
            hours = difference.seconds // 3600
            minutes = (difference.seconds // 60) % 60  # why Python, why?

            # cant spin again -> still on cooldown
            if days < ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value:
                remainingDays = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value - days - 1
                remainingHours = 23 - hours
                remainingMinutes = 59 - minutes

                logger.debug("cant spin, still on cooldown")

                return "Du darfst nocht nicht wieder drehen! Versuche es in %d Tag(en), %d Stunde(n) und " \
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

            with self.databaseConnection.cursor() as cursor:
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'experience',
                    xp['id'],
                    xp,
                )

                cursor.execute(query, nones)
                self.databaseConnection.commit()
                logger.debug("saved new xp boost to database")

            return "Du hast einen XP-Boost gewonnen!!! Für %d Stunde(n) bekommst du %d-Fach XP! Setze ihn über dein " \
                   "Inventar ein!" % (ExperienceParameter.XP_BOOST_SPIN_DURATION.value / 60,
                                      ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value
                                      )
        else:
            logger.debug("did not win xp boost")

            days = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value
            xp['last_spin_for_boost'] = datetime.now()

            with self.databaseConnection.cursor() as cursor:
                query, nones = WriteSaveQuery.writeSaveQuery(
                    'experience',
                    xp['id'],
                    xp,
                )

                cursor.execute(query, nones)
                self.databaseConnection.commit()
                logger.debug("saved date to database")

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
    async def handleXpRequest(self, member: Member, user: Member) -> string:
        """
        Handles the XP-Request of the given tag

        :param user: Tag of the requested user
        :param member: Member, who called the command
        :return: string - answer
        """
        # lazy import to avoid circular import
        from src.Services.ProcessUserInput import getTagStringFromId, getUserIdByTag

        logger.debug("%s requested XP" % member.name)

        dcUserDb = getDiscordUser(self.databaseConnection, user)

        if dcUserDb is None:
            logger.warning("couldn't fetch DiscordUser!")

            return "Es ist ein Fehler aufgetreten!"

        xp = self.__getExperience(dcUserDb['user_id'])

        if xp is None:
            logger.warning("couldn't fetch Experience!")

            return "Es ist ein Fehler aufgetreten!"

        reply = "%s hat bereits %d XP gefarmt!\n\n" % (getTagStringFromId(dcUserDb['user_id']), xp['xp_amount'])
        reply += getDoubleXpWeekendInformation()

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
            dcUserDb = getDiscordUser(self.databaseConnection, member)

            if dcUserDb is None:
                logger.warning("couldn't fetch DiscordUser!")

                return "Es ist ein Fehler aufgetreten!"

            dcUserDb['double_xp_notification'] = 1

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )
        else:
            dcUserDb = getDiscordUser(self.databaseConnection, member)

            if dcUserDb is None:
                logger.warning("Couldn't fetch DiscordUser!")

                return "Es ist ein Fehler aufgetreten!"

            dcUserDb['double_xp_notification'] = 0

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

        with self.databaseConnection.cursor() as cursor:
            cursor.execute(query, nones)
            self.databaseConnection.commit()

        logger.debug("saved setting to database")

        return "Deine Einstellungen wurden gespeichert!"

    @validateKeys
    async def handleXpInventory(self, member: Member, action: str, row: str = None):
        """
        Handles the XP-Inventory

        :param member: Member, who the inventory belongs to
        :param action: Action the user wants to perform with his inventory
        :param row: Optional row to choose boost from
        :return:
        """
        logger.debug("%s requested Xp-Inventory" % member.name)

        dcUserDb: dict | None = getDiscordUser(self.databaseConnection, member)

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

            reply += "\nMit '!inventory use {Zeile}' kannst du einen XP-Boost einsetzen!"

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

                # empty active boosts => can use all boosts at once
                if xp['active_xp_boosts'] is None:
                    xp['active_xp_boosts'] = xp['xp_boosts_inventory']
                    xp['xp_boosts_inventory'] = None
                # xp boosts can fit into active
                elif (len(json.loads(xp['active_xp_boosts'])) + len(
                        json.loads(xp['xp_boosts_inventory']))) <= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:

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

                    while numXpBoosts < ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value and currentPosInInventory < len(
                            xpBoostsInventory):
                        currentBoost = xpBoostsInventory[currentPosInInventory]

                        activeXpBoosts.append(currentBoost)
                        inventoryAfter.remove(currentBoost)

                        currentPosInInventory += 1
                        numXpBoosts += 1

                    xp['xp_boosts_inventory'] = json.dumps(inventoryAfter)
                    xp['active_xp_boosts'] = json.dumps(activeXpBoosts)

                answer = "Alle deine XP-Boosts wurden eingesetzt!"
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

                    return "Deine Eingabe war unültig!"

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'experience',
                xp['id'],
                xp,
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

        logger.debug("saved changes to database")

        return answer

    def addExperience(self, experienceParameter: int, dcUserDb: dict = None, member: Member = None):
        """
        Adds the given amount of xp to the given user

        :param member: Optional Member if DiscordUser is not used
        :param dcUserDb: DiscordUser, who receives the xp
        :param experienceParameter: Amount of xp
        :return:
        """
        if dcUserDb:
            logger.debug("%s gets XP" % dcUserDb['username'])
        elif member:
            logger.debug("%s gets XP" % member.name)
        else:
            logger.warning("Someone is getting XP, but nothing is given!")

        if not dcUserDb:
            if member is None:
                logger.warning("member and dcUserDb are None")

                raise ValueError

            if (dcUserDb := getDiscordUser(self.databaseConnection, member)) is None:
                logger.warning("couldn't fetch DiscordUser!")

                return

        xp = self.__getExperience(dcUserDb['user_id'])

        if xp is None:
            logger.warning("couldn't fetch Experience")

            return

        currentXpAmount = xp['xp_amount']
        toBeAddedXpAmount = 0

        if xp['active_xp_boosts']:
            logger.debug("multiply xp with active boosts")

            for boost in json.loads(xp['active_xp_boosts']):
                toBeAddedXpAmount += experienceParameter * boost['multiplier']

        if toBeAddedXpAmount == 0:
            if isDoubleWeekend(datetime.now()):
                xp['xp_amount'] = currentXpAmount + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value
            else:
                xp['xp_amount'] = currentXpAmount + experienceParameter
        else:
            if isDoubleWeekend(datetime.now()):
                xp[
                    'xp_amount'] = currentXpAmount + toBeAddedXpAmount + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value
            else:
                xp['xp_amount'] = currentXpAmount + toBeAddedXpAmount

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'experience',
                xp['id'],
                xp
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

        logger.debug("saved changes to database")

    @validateKeys
    def sendXpLeaderboard(self, member: Member) -> string:
        """
        Answers the Xp-Leaderboard

        :param member: Member, who called the command
        :return:
        """
        logger.debug("%s requested XP-Leaderboard" % member.name)

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT d.username, e.xp_amount " \
                    "FROM experience e LEFT JOIN discord d ON e.discord_user_id = d.id " \
                    "WHERE e.xp_amount != 0 " \
                    "ORDER BY e.xp_amount DESC " \
                    "LIMIT 10"

            cursor.execute(query)

            if (data := cursor.fetchall()) is None:
                logger.warning("couldn't fetch leaderboard-data!")

                return "Es ist ein Fehler aufgetreten!"

        users = [dict(zip(cursor.column_names, date)) for date in data]
        reply = "Folgende User haben die meisten XP:\n\n"

        for index, user in enumerate(users):
            reply += "%d. %s - %d XP\n" % (index, user['username'], user['xp_amount'])

        return reply

    def __del__(self):
        self.databaseConnection.close()
