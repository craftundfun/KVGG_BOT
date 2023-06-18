from __future__ import annotations

import json
import math
import random
import string
import discord
import mysql

from discord import Client, Member
from mysql.connector import MySQLConnection
from src.Helper import ReadParameters as rp
from datetime import datetime, timedelta
from src.DiscordParameters.ExperienceParameter import ExperienceParameter
from src.Helper.ReadParameters import Parameters as parameters
from src.Helper import WriteSaveQuery
from src.Id.GuildId import GuildId
from src.Repository.DiscordUserRepository import getDiscordUser


def isDoubleWeekend(date: datetime = datetime.now()) -> bool:
    return date.isocalendar()[1] % 2 == 0 and (date.weekday() == 5 or date.weekday() == 6)


def getDiffUntilNextDoubleXpWeekend() -> timedelta:
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


def getDoubleXpWeekendInformation():
    if isDoubleWeekend():
        return "Dieses Wochenende ist btw. Doppel-XP-Wochenende!"
    else:
        diff: timedelta = getDiffUntilNextDoubleXpWeekend()

        return "Das nächste Doppel-XP-Wochenende beginnt in %s Tagen, %s Stunden und %s Minuten." % \
            (diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60)


async def informAboutDoubleXpWeekend(dcUserDb: dict, client: discord.Client):
    if not dcUserDb['double_xp_notification'] or not isDoubleWeekend():
        return

    await client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(int(dcUserDb['user_id']))
    member = client.get_guild(int(GuildId.GUILD_KVGG.value)).get_member(int(dcUserDb['user_id']))

    if not member.dm_channel:
        await member.create_dm()

        if not member.dm_channel:
            return

    await member.dm_channel.send("Dieses Wochenende gibt es doppelte XP! Viel Spaß beim farmen.\n\nWenn du diese "
                                 "Benachrichtigung nicht mehr erhalten möchtest, kannst du sie in '#bot-commands'"
                                 "auf dem Server mit '!xp off' (oder '!xp on') de- bzw. aktivieren!")


class ExperienceService:

    def __init__(self, client: Client):
        self.databaseConnection = mysql.connector.connect(
            user=rp.getParameter(parameters.USER),
            password=rp.getParameter(parameters.PASSWORD),
            host=rp.getParameter(parameters.HOST),
            database=rp.getParameter(parameters.NAME),
        )
        self.client = client

    def getExperience(self, userId: int) -> dict | None:
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, last_spin_for_boost, " \
                    "active_xp_boosts " \
                    "FROM experience " \
                    "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                    "WHERE d.user_id = %s"

            cursor.execute(query, (userId,))

            data = cursor.fetchone()

            # data can be None here, not the value
            if not data:
                self.createExperience(userId)

                query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, " \
                        "last_spin_for_boost, active_xp_boosts " \
                        "FROM experience " \
                        "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                        "WHERE d.user_id = %s"

                cursor.execute(query, (userId,))

                data = cursor.fetchone()

                if not data:
                    return None

        return dict(zip(cursor.column_names, data))

    # TODO reduce database load - get information once and use them
    def createExperience(self, userId: int):
        xpAmount = self.calculateXpFromPreviousData(userId)
        xpBoosts = self.calculateXpBoostsFromPreviousData(userId)

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT id FROM discord WHERE user_id = %s"

            cursor.execute(query, (userId,))

            dcUserDbId = cursor.fetchone()

            if dcUserDbId:
                # user in database
                dcUserDbId = dcUserDbId[0]
            else:
                return None  # TODO create new DiscordUser, but look out if it's really necessary

            query = "INSERT INTO experience (xp_amount, discord_user_id, xp_boosts_inventory) " \
                    "VALUES (%s, %s, %s)"

            cursor.execute(query, (xpAmount, dcUserDbId, xpBoosts))
            self.databaseConnection.commit()

    def calculateXpBoostsFromPreviousData(self, dcUserDbId: int):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT time_online FROM discord WHERE user_id = %s"

            cursor.execute(query, (dcUserDbId,))

            timeOnline = cursor.fetchone()

        timeOnline = timeOnline[0]

        if not timeOnline:
            return None

        numberAchievementBoosts = timeOnline / (ExperienceParameter.XP_BOOST_FOR_EVERY_X_HOURS.value * 60)
        flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
        intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

        if intNumberAchievementBoosts == 0:
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

        return json.dumps(boosts)

    def calculateXpFromPreviousData(self, userId: int):
        amount = 0

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT time_online, time_streamed, message_count_all_time " \
                    "FROM discord " \
                    "WHERE user_id = %s"

            cursor.execute(query, (userId,))

            data = dict(zip(cursor.column_names, list(cursor.fetchone())))

        if timeOnline := data['time_online']:
            amount += timeOnline * ExperienceParameter.XP_FOR_ONLINE.value

        if timeStreamed := data['time_streamed']:
            amount += timeStreamed * ExperienceParameter.XP_FOR_STREAMING.value

        if messages := data['message_count_all_time']:
            amount += messages * ExperienceParameter.XP_FOR_MESSAGE.value

        return amount

    def checkAndGrantXpBoost(self):
        pass  # only necessary for cronjob

    async def spinForXpBoost(self, member: Member) -> string:
        if (dcUserDb := getDiscordUser(self.databaseConnection, member)) is None:
            return "Es ist etwas schief gelaufen!"

        xp = self.getExperience(dcUserDb['user_id'])

        if xp is None:
            return "Es ist etwas schief gelaufen!"

        inventoryJson = xp['xp_boosts_inventory']

        if inventoryJson is None:
            inventory = []
        else:
            inventory = json.loads(inventoryJson)

        if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
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

                return "Du darfst nocht nicht wieder drehen! Versuche es in %d Tag(en), %d Stunde(n) und " \
                       "%d Minute(n) wieder!" % (remainingDays, remainingHours, remainingMinutes)

        # win
        if random.randint(0, (100 / ExperienceParameter.SPIN_WIN_PERCENTAGE.value)) == 1:
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

            return "Du hast einen XP-Boost gewonnen!!! Für %d Stunde(n) bekommst du %d-Fach XP! Setze ihn über dein " \
                   "Inventar ein!" % (ExperienceParameter.XP_BOOST_SPIN_DURATION.value / 60,
                                      ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value
                                      )

        else:
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

            return "Du hast leider nichts gewonnen! Versuche es in %d Tagen nochmal!" % days

    # returns xp for given user or changes settings for double-xp-notification
    async def handleXpRequest(self, userTag: str) -> string:
        # lazy import to avoid circular import
        from src.Services.ProcessUserInput import getTagStringFromId, getUserIdByTag

        # TODO improve
        """
        if messageParts[1] == 'on':
            dcUserDb = getDiscordUser(self.databaseConnection, message.author)

            if dcUserDb is None:
                await message.reply("Es ist ein Fehler aufgetreten!")

                return

            dcUserDb['double_xp_notification'] = 1

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            with self.databaseConnection.cursor() as cursor:
                cursor.execute(query, nones)
                self.databaseConnection.commit()

            await message.reply("Deine Einstellungen wurden gespeichert!")

            return
        elif messageParts[1] == 'off':
            dcUserDb = getDiscordUser(self.databaseConnection, message.author)

            if dcUserDb is None:
                await message.reply("Es ist ein Fehler aufgetreten!")

                return

            dcUserDb['double_xp_notification'] = 0

            query, nones = WriteSaveQuery.writeSaveQuery(
                'discord',
                dcUserDb['id'],
                dcUserDb
            )

            with self.databaseConnection.cursor() as cursor:
                cursor.execute(query, nones)
                self.databaseConnection.commit()

            await message.reply("Deine Einstellungen wurden gespeichert!")

            return
        """
        # else:
        if (userId := getUserIdByTag(userTag)) is None:
            return "Bitte tagge einen User korrekt!"

        taggedMember = await self.client.get_guild(int(GuildId.GUILD_KVGG.value)).fetch_member(userId)
        dcUserDb = getDiscordUser(self.databaseConnection, taggedMember)

        if dcUserDb is None:
            return "Es ist ein Fehler aufgetreten!"

        xp = self.getExperience(dcUserDb['user_id'])

        if xp is None:
            return "Es ist ein Fehler aufgetreten!"

        reply = "%s hat bereits %d XP gefarmt!\n\n" % (getTagStringFromId(dcUserDb['user_id']), xp['xp_amount'])
        reply += getDoubleXpWeekendInformation()

        return reply

    async def handleXpInventory(self, member: Member, action: str, row: str = None):
        dcUserDb: dict | None = getDiscordUser(self.databaseConnection, member)

        if dcUserDb is None:
            return "Es ist ein Fehler aufgetreten!"

        xp = self.getExperience(dcUserDb['user_id'])

        if xp is None:
            return "Es ist ein Fehler aufgetreten!"

        if action == 'list':
            if xp['xp_boosts_inventory'] is None:
                return "Du hast keine XP-Boosts in deinem Inventar!"

            reply = "Du hast folgende XP-Boosts in deinem Inventar:\n\n"
            inventory = json.loads(xp['xp_boosts_inventory'])

            for index, item in enumerate(inventory, start=1):
                reply += "%d. %s-Boost, für %s Minuten %s-Fach XP\n" % \
                         (index, item['description'], item['remaining'], item['multiplier'])

            reply += "\nMit '!inventory use {Zeile}' kannst du einen XP-Boost einsetzen!"

            return reply
        # !inventory use
        else:
            # no xp boosts available
            if xp['xp_boosts_inventory'] is None:
                return "Du hast keine XP-Boosts in deinem Inventar!"

            # too many xp boosts are active, cant activate another one
            if xp['active_xp_boosts'] is not None and len(
                    json.loads(xp['active_xp_boosts'])) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere " \
                       "es erneut!"

            # inventory use all
            if row == 'all':
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
                # inventory empty
                if xp['xp_boosts_inventory'] is None:
                    return "Du hast keine XP-Boosts in deinem Inventar!"
                # active inventory full
                elif xp['active_xp_boosts'] is not None and len(
                        json.loads(xp['active_xp_boosts'])) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
                    return "Du hast zu viele aktive XP-Boosts! Warte bis einer ausgelaufen ist und probiere es erneut!"

                try:
                    if row is None:
                        raise ValueError
                    row = int(row)
                except ValueError:
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
                    return "Deine Eingabe war unültig!"
        # TODO list active ones with leaderboard simultaneous
        # elif messageParts[1] == 'active':
        #    if xp['active_xp_boosts'] is None:
        #        await message.reply("Du hast keine aktiven XP-Boosts!")

        #        return

        #    reply = "Du hast folgende aktive XP-Boosts:\n\n"
        #    activeBoosts: list = json.loads(xp['active_xp_boosts'])

        #    for index, item in enumerate(activeBoosts, start=1):
        #        reply += "%d. %s-Boost, der noch für %s Minuten %s-Fach XP gibt\n" % (
        #            index, item['description'], item['remaining'], item['multiplier'])

        #    await message.reply(reply)

        #    return  # return here to avoid straining the database with an unnecessary save

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'experience',
                xp['id'],
                xp,
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()

        return answer

    def addExperience(self, dcUserDb: dict, experienceParameter: int):
        xp = self.getExperience(dcUserDb['user_id'])

        if xp is None:
            return

        currentXpAmount = xp['xp_amount']
        toBeAddedXpAmount = 0

        if xp['active_xp_boosts']:
            for boost in json.loads(xp['active_xp_boosts']):
                toBeAddedXpAmount += experienceParameter * boost['multiplier']

        if toBeAddedXpAmount == 0:
            if isDoubleWeekend():
                xp['xp_amount'] = currentXpAmount + experienceParameter * ExperienceParameter.XP_WEEKEND_VALUE.value
            else:
                xp['xp_amount'] = currentXpAmount + experienceParameter
        else:
            if isDoubleWeekend():
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
