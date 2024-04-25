import sys
from typing import Sequence

from sqlalchemy import select, insert

from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.Statistic.Entity.CurrentDiscordStatistic import CurrentDiscordStatistic
from src.Manager.DatabaseManager import getSession
from src.Manager.StatisticManager import StatisticsParameter

if not (session := getSession()):
    print("[ERROR] couldn't get session")

    sys.exit(1)

getQuery = select(DiscordUser)

try:
    dcUsersDb = session.scalars(getQuery).all()
except Exception as error:
    print(f"[ERROR] couldn't get discord users from database: {error}")

    sys.exit(1)
else:
    print(f"[INFO] got {len(dcUsersDb)} discord users from database")

for dcUser in dcUsersDb:
    getQuery = select(CurrentDiscordStatistic).where(CurrentDiscordStatistic.discord_id == dcUser.id)

    try:
        currentDiscordStatistics: Sequence[CurrentDiscordStatistic] = session.scalars(getQuery).all()
    except Exception as error:
        print(f"[ERROR] couldn't get current discord statistics for {dcUser} from database: {error}")

        continue

    if not currentDiscordStatistics:
        print(f"[INFO] no current discord statistics for {dcUser} in database")

        for time in StatisticsParameter.getTimeValues():
            for type in StatisticsParameter.getTypeValues():
                insertQuery = insert(CurrentDiscordStatistic).values(discord_id=dcUser.id,
                                                                     statistic_type=type,
                                                                     statistic_time=time,
                                                                     value=0, )

                try:
                    session.execute(insertQuery)
                    session.commit()
                except Exception as error:
                    print(f"[ERROR] couldn't insert current discord statistic for {dcUser} into database: {error}")

                    continue
                else:
                    print(f"[INFO] inserted current discord statistic for {dcUser}, type: {type} and time: {time} "
                          f"into database")

        print(f"[INFO] inserted current discord statistics for {dcUser} into database")

        continue

    for type in StatisticsParameter.getTypeValues():
        for time in StatisticsParameter.getTimeValues():
            found = False

            for statistic in currentDiscordStatistics:
                if statistic.statistic_type == type and statistic.statistic_time == time:
                    found = True
                    break

            if not found:
                insertQuery = insert(CurrentDiscordStatistic).values(discord_id=dcUser.id,
                                                                     statistic_type=type,
                                                                     statistic_time=time,
                                                                     value=0, )

                try:
                    session.execute(insertQuery)
                    session.commit()
                except Exception as error:
                    print(f"[ERROR] couldn't insert current discord statistic for {dcUser}, type: {type} and time: "
                          f"{time} into database: {error}")

                    continue
                else:
                    print(f"[INFO] inserted current discord statistic for {dcUser}, type: {type} and time: {time} "
                          f"into database")
            else:
                print(f"[INFO] current discord statistic for {dcUser}, type: {type} and time: {time} already exists")
