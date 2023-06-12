from __future__ import annotations

import json
import math

from mysql.connector import MySQLConnection

from src.DiscordParameters.ExperienceParameter import ExperienceParameter


class ExperienceService:

    def __init__(self, databaseConnection: MySQLConnection):
        self.databaseConnection = databaseConnection

    def getExperience(self, userId: int) -> dict:
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, last_spin_for_boost, " \
                    "active_xp_boosts " \
                    "FROM experience " \
                    "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                    "WHERE d.user_id = %s"

            cursor.execute(query, (userId,))

            data = cursor.fetchone()

            if not data:
                try:
                    self.createExperience(userId)

                    query = "SELECT experience.id, discord_user_id, xp_amount, xp_boosts_inventory, " \
                            "last_spin_for_boost, active_xp_boosts " \
                            "FROM experience " \
                            "INNER JOIN discord d ON experience.discord_user_id = d.id " \
                            "WHERE d.user_id = %s"

                    cursor.execute(query, (userId,))

                    data = cursor.fetchone()
                except ValueError:
                    pass  # TODO

        return dict(zip(cursor.column_names, data))

    def createExperience(self, userId: int):
        xpAmount = self.calculateXpFromPreviousData(userId)
        xpBoosts = self.calculateXpBoostsFromPreviousData(userId)

        with self.databaseConnection.cursor() as cursor:
            query = "SELECT id FROM discord WHERE user_id = %s"

            cursor.execute(query, (userId,))

            id = cursor.fetchone()

            if id:
                # user not in database
                id = id[0]
            else:
                raise ValueError

            query = "INSERT INTO experience (xp_amount, discord_user_id, xp_boosts_inventory) " \
                    "VALUES (%s, %s, %s)"

            cursor.execute(query, (xpAmount, id, xpBoosts))
            self.databaseConnection.commit()

    def calculateXpBoostsFromPreviousData(self, dcUserDbId: int):
        with self.databaseConnection.cursor() as cursor:
            query = "SELECT time_online FROM discord WHERE user_id = %s"

            cursor.execute(query, (dcUserDbId,))

            timeOnline = cursor.fetchone()

        if timeOnline:
            timeOnline = timeOnline[0]
        else:
            raise ValueError

        numberAchievementBoosts = timeOnline / (ExperienceParameter.XP_BOOST_FOR_EVERY_X_HOURS.value * 60)
        flooredNumberAchievementBoosts = math.floor(numberAchievementBoosts)
        intNumberAchievementBoosts = int(flooredNumberAchievementBoosts)

        if intNumberAchievementBoosts == 0:
            return

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
