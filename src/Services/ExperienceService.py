from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta
from src.Helper import WriteSaveQuery
from discord import Message
from mysql.connector import MySQLConnection
from src.Repository.DiscordUserRepository import getDiscordUser
from src.DiscordParameters.ExperienceParameter import ExperienceParameter


class ExperienceService:

    def __init__(self, databaseConnection: MySQLConnection):
        self.databaseConnection = databaseConnection

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

    async def spinForXpBoost(self, message: Message):
        if (dcUserDb := getDiscordUser(self.databaseConnection, message)) is None:
            await message.reply("Es ist etwas schief gelaufen!")

            return

        xp = self.getExperience(dcUserDb['user_id'])

        if xp is None:
            await message.reply("Es ist etwas schief gelaufen!")

        inventoryJson = xp['xp_boosts_inventory']

        if inventoryJson is None:
            inventory = []
        else:
            inventory = json.loads(inventoryJson)

        if len(inventory) >= ExperienceParameter.MAX_XP_BOOSTS_INVENTORY.value:
            await message.reply("Dein Inventar ist voll! Benutze erst einen oder mehrere XP-Boosts!")

            return

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

                await message.reply("Du darfst nocht nicht wieder drehen! "
                                    "Versuche es in %d Tag(en), %d Stunde(n) und %d Minute(n) wieder!"
                                    % (remainingDays, remainingHours, remainingMinutes)
                                    )

                return

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

            await message.reply("Du hast einen XP-Boost gewonnen!!! Für %d Stunde(n) bekommst du "
                                "%d-Fach XP! Setze ihn über dein Inventar ein!"
                                % (ExperienceParameter.XP_BOOST_SPIN_DURATION.value / 60,
                                   ExperienceParameter.XP_BOOST_MULTIPLIER_SPIN.value
                                   )
                                )
        else:
            days = ExperienceParameter.WAIT_X_DAYS_BEFORE_NEW_SPIN.value
            xp['last_spin_for_boost'] = datetime.now()

            await message.reply("Du hast leider nichts gewonnen! Versuche es in %d Tagen nochmal!" % days)

        with self.databaseConnection.cursor() as cursor:
            query, nones = WriteSaveQuery.writeSaveQuery(
                'experience',
                xp['id'],
                xp,
            )

            cursor.execute(query, nones)
            self.databaseConnection.commit()
