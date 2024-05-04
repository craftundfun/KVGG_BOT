import asyncio
import logging
import random
import textwrap
from enum import Enum
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from discord import Client, Member
from sqlalchemy import select, or_

from src.DiscordParameters.Colors import Colors
from src.DiscordParameters.StatisticsParameter import StatisticsParameter
from src.Entities.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Entities.DiscordUser.Repository.DiscordUserRepository import getDiscordUser
from src.Entities.Experience.Repository.ExperienceRepository import getExperience
from src.Entities.Game.Repository.DiscordGameRepository import getMostPlayedGames
from src.Entities.UserRelation.Entity.DiscordUserRelation import DiscordUserRelation
from src.Helper.GetFormattedTime import getFormattedTime
from src.Helper.ReadParameters import getParameter, Parameters
from src.Manager.DatabaseManager import getSession
from src.Services.GameDiscordService import GameDiscordService
from src.Services.RelationService import RelationTypeEnum
from src.View.PaginationView import PaginationViewDataItem, PaginationViewDataTypes

logger = logging.getLogger("KVGG_BOT")


class LeaderboardImageNames(Enum):
    ACTIVITIES = "top_5_activities.png"
    RELATIONS = "top_5_relations.png"
    ONLINE_AND_STREAM = "top_5_online_stream.png"
    MESSAGES_AND_COMMANDS = "top_5_message_command.png"

    @classmethod
    def getNameForImage(cls, imageName: "LeaderboardImageNames"):
        match imageName:
            case LeaderboardImageNames.ACTIVITIES:
                return "Aktivitäten"
            case LeaderboardImageNames.RELATIONS:
                return "Online- und Stream-Relationen"
            case LeaderboardImageNames.ONLINE_AND_STREAM:
                return "Online- und Stream-Zeit"
            case LeaderboardImageNames.MESSAGES_AND_COMMANDS:
                return "gesendete Nachrichten und Commands"
            case _:
                logger.error(f"Unknown image name: {imageName}")

                return "FEHLER"


class LeaderboardService:
    basepath = Path(__file__).parent.parent.parent
    url = f"https://axellotl.de:{getParameter(Parameters.API_PORT)}/backend/discord/plots/"

    def __init__(self, client: Client):
        self.client = client

        self.gameDiscordService = GameDiscordService(self.client)

    # noinspection PyMethodMayBeStatic
    def getDataForMember(self, member: Member) -> list[str]:
        wholeAnswer: list[str] = []

        if member.bot:
            return ["Bots haben keine Leaderboards!"]

        if not (session := getSession()):
            return ["Es gab einen Fehler!"]

        if not (dcUserDb := getDiscordUser(member, session)):
            session.close()

            return ["Es gab einen Fehler!"]

        answer = f"## __Daten von <@{member.id}>:__\n"
        answer += f"### Zeit:\n"
        answer += f"- **Online-Zeit:** {getFormattedTime(dcUserDb.time_online)} Stunden\n"
        answer += f"- **Stream-Zeit:** {getFormattedTime(dcUserDb.time_streamed)} Stunden\n"
        answer += f"- **Uni-Zeit:** {getFormattedTime(dcUserDb.university_time_online)} Stunden\n"
        answer += f"- **Gesendete Nachrichten:** {dcUserDb.message_count_all_time} Nachrichten\n"
        answer += f"- **Gesendete Commands:** {dcUserDb.command_count_all_time} Commands\n"

        if xp := getExperience(member, session):
            answer += f"- **Erfahrung**: {'{:,}'.format(xp.xp_amount).replace(',', '.')} XP\n"

        wholeAnswer.append(answer)
        del answer

        logger.debug(f"added basic data to answer for {member.display_name}")

        if games := dcUserDb.game_mappings:
            answer = f"\n### Spiele: (Name | Zeit online | Zeit offline)\n"

            for game in games:
                answer += (f"- **{game.discord_game.name}:** {getFormattedTime(game.time_played_online)} Stunden"
                           f", {getFormattedTime(game.time_played_offline)} Stunden\n")

            wholeAnswer.append(answer)
            del answer

            logger.debug(f"added games data to answer for {member.display_name}")
        else:
            logger.debug(f"no games found for {member.display_name}")

        try:
            getQuery = (select(DiscordUserRelation)
                        .where(or_(DiscordUserRelation.discord_user_1 == dcUserDb,
                                   DiscordUserRelation.discord_user_2 == dcUserDb, ))
                        .order_by(DiscordUserRelation.type))
            relations = session.scalars(getQuery).all()
        except Exception as error:
            logger.error(f"couldn't fetch relations for {member.display_name}", exc_info=error)
            session.close()

            return ["Es gab einen Fehler!"]
        else:
            if relations:
                answer = f"\n### Relationen mit: (Member | Zeit | Typ)\n"
                lastRelation = ""

                for relation in relations:
                    # if the type changes, add a new line
                    if lastRelation != relation.type:
                        answer += "\n"

                    lastRelation = relation.type

                    if relation.discord_user_1 == dcUserDb:
                        answer += (f"- **{relation.discord_user_2.username}:** {getFormattedTime(relation.value)} "
                                   f"Stunden, {relation.type.capitalize()}\n")
                    else:
                        answer += (f"- **{relation.discord_user_1.username}:** {getFormattedTime(relation.value)} "
                                   f"Stunden, {relation.type.capitalize()}\n")

                wholeAnswer.append(answer)
                del answer

                logger.debug(f"added relation data to answer for {member.display_name}")
            else:
                logger.debug(f"no relations found for {member.display_name}")

        if counters := dcUserDb.counter_mappings:
            answer = "\n### Counter: (Name | Wert)\n"
            atleastOneCounter = False

            for counter in counters:
                if counter.value < 1:
                    continue

                answer += f"- **{counter.counter.name.capitalize()}:** {counter.value}\n"
                atleastOneCounter = True

            if atleastOneCounter:
                wholeAnswer.append(answer)

            del answer

            logger.debug(f"added counter data to answer for {member.display_name}")
        else:
            logger.debug(f"no counters found for {member.display_name}")

        if currentStatistics := dcUserDb.current_discord_statistics:
            answer = "\n### aktuelle Statistiken: (Name | Wert | Zeitraum)\n"
            answerSortedByTimes = {}

            # create a dict with all times and types sorted to retain the same order
            for time in StatisticsParameter.getTimeValues():
                answerSortedByTypes = {}

                for type in StatisticsParameter.getTypeValues():
                    answerSortedByTypes[type] = ""

                answerSortedByTimes[time] = answerSortedByTypes

            for statistic in currentStatistics:
                if statistic.statistic_type == "command":
                    unit = "Commands"
                elif statistic.statistic_type == "message":
                    unit = "Nachrichten"
                else:
                    unit = "Stunden"

                answerSortedByTimes[statistic.statistic_time][statistic.statistic_type] \
                    += (f"- **{statistic.statistic_type.capitalize()}:** "
                        f"{getFormattedTime(statistic.value) if unit == 'Stunden' else statistic.value} {unit}, "
                        f"{statistic.statistic_time.capitalize()}\n")

            for time in answerSortedByTimes.keys():
                for type in answerSortedByTimes[time].keys():
                    answer += answerSortedByTimes[time][type]

                answer += "\n"

            wholeAnswer.append(answer)
            del answer

            logger.debug(f"added current statistics to answer for {member.display_name}")
        else:
            logger.debug(f"no current statistics found for {member.display_name}")

        return wholeAnswer

    async def getLeaderboard(self) -> list[PaginationViewDataItem]:
        async def fetch_leaderboard():
            availablePlots = []
            data = []

            if self.createTopOnlineAndStreamDiagram():
                availablePlots.append(LeaderboardImageNames.ONLINE_AND_STREAM)

            if self.createTopMessagesAndCommandsDiagram():
                availablePlots.append(LeaderboardImageNames.MESSAGES_AND_COMMANDS)

            if self.createTopRelationDiagram():
                availablePlots.append(LeaderboardImageNames.RELATIONS)

            if self.createTopGamesDiagram():  # TODO
                availablePlots.append(LeaderboardImageNames.ACTIVITIES)

            for plot in availablePlots:
                data.append(
                    PaginationViewDataItem(
                        field_name=LeaderboardImageNames.getNameForImage(plot),
                        data_type=PaginationViewDataTypes.PICTURE,
                        # add random number to URL to avoid discords image caching, lol
                        field_value=self.url + plot.value + f"/{random.randint(0, 10000000000)}",
                    )
                )

            return data if data else [PaginationViewDataItem(
                field_name="FEHLER",
                data_type=PaginationViewDataTypes.TEXT,
            )]

        try:
            result = await asyncio.wait_for(fetch_leaderboard(), timeout=10.0)
            return result
        except asyncio.TimeoutError:
            return [PaginationViewDataItem(
                field_name="TIMEOUT",
                data_type=PaginationViewDataTypes.TEXT,
                field_value="Die Anfrage dauerte zu lange.",
            )]

    def _createDoubleBarDiagram(self,
                                firstBarValues: list[int],
                                secondBarValues: list[int],
                                firstBarLabel: str,
                                secondBarLabel: str,
                                namesOfFirstBar: list[str],
                                namesOfSecondBar: list[str],
                                title: str,
                                path: LeaderboardImageNames,
                                countOfEntries: int = 5):
        # prepare usernames to fit in the bars
        xLabelsFirstBar = [textwrap.fill(item, 30) for item in namesOfFirstBar]
        xLabelsSecondBar = [textwrap.fill(item, 30) for item in namesOfSecondBar]

        # create plot
        fig, ax = plt.subplots()
        bar_width = 0.4

        # add bars
        ax.bar(np.arange(len(firstBarValues)),
               firstBarValues,
               width=bar_width,
               color=Colors.MAIN.value,
               label=firstBarLabel)
        ax.bar(np.arange(len(secondBarValues)) + bar_width,
               secondBarValues,
               width=bar_width,
               color=Colors.SECONDARY_MAIN.value,
               label=secondBarLabel)

        # set things
        ax.set_ylabel('Stunden', labelpad=8)
        ax.set_title(title)

        # empty x-ticks to insert our values into the bars
        plt.gca().set_xticks([])
        plt.gca().set_xticklabels([])

        for i, label in enumerate(xLabelsFirstBar):
            plt.text(x=i,
                     y=max(firstBarValues) * .05,
                     s=xLabelsFirstBar[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        for i, label in enumerate(xLabelsSecondBar):
            plt.text(x=i + 0.4,
                     # use online values here to have the texts on the same height
                     y=max(firstBarValues) * .05,
                     s=xLabelsSecondBar[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        for i in range(countOfEntries):
            plt.text(x=i,
                     y=-max(firstBarValues) * .05,
                     s=f"Platz {i + 1}.",
                     color='black', )

        # extract the y-labels from the graph
        labels = [item.get_text() for item in ax.get_yticklabels()]

        # calculate hours from minutes to display
        for i in range(len(labels)):
            labels[i] = getFormattedTime(int(labels[i]))

        # insert values next to y-axis
        ax.set_yticklabels(labels)

        # show legend in the top right corner
        ax.legend()

        # adjust positioning
        plt.subplots_adjust(left=0.15, right=0.95, top=0.90, bottom=0.1)

        savePath: Path = self.basepath.joinpath(f"data/plots/{path.value}")

        # save to disk
        plt.savefig(savePath, dpi=250)

    def createTopMessagesAndCommandsDiagram(self) -> bool:
        logger.debug("creating createTopMessagesAndCommandsDiagram")

        countOfEntries = 5

        if not (session := getSession()):  # TODO outside
            return False

        # noinspection PyUnresolvedReferences
        messageQuery = (select(DiscordUser)
                        .order_by(DiscordUser.message_count_all_time.desc())
                        .limit(countOfEntries))
        # noinspection PyUnresolvedReferences
        commandQuery = (select(DiscordUser)
                        .order_by(DiscordUser.command_count_all_time.desc())
                        .limit(countOfEntries))

        try:
            messageUsers = session.scalars(messageQuery).all()
            commandUsers = session.scalars(commandQuery).all()
        except Exception as error:
            logger.error("couldn't fetch data for leaderboard", exc_info=error)
            session.close()

            return False

        if not messageUsers or not commandUsers:
            logger.error("no message or command users")
            session.close()

            return False

        messageValues = [user.message_count_all_time for user in messageUsers]
        messageValues.sort(reverse=True)
        commandValues = [user.command_count_all_time for user in commandUsers]
        commandValues.sort(reverse=True)

        # prepare usernames to fit in the bars
        xLabelsFirstBar = [textwrap.fill(item, 30) for item in [user.username for user in messageUsers]]
        xLabelsSecondBar = [textwrap.fill(item, 30) for item in [user.username for user in commandUsers]]

        session.close()

        # create plot
        fig, ax = plt.subplots()
        bar_width = 0.4

        # add bars
        ax.bar(np.arange(len(messageValues)),
               messageValues,
               width=bar_width,
               color=Colors.MAIN.value,
               label="Nachrichten")
        ax.bar(np.arange(len(commandValues)) + bar_width,
               commandValues,
               width=bar_width,
               color=Colors.SECONDARY_MAIN.value,
               label="Commands")

        # set things
        ax.set_ylabel('Menge', labelpad=8)
        ax.set_title("gesendete Nachrichten und Commands")

        # empty x-ticks to insert our values into the bars
        plt.gca().set_xticks([])
        plt.gca().set_xticklabels([])

        for i, label in enumerate(xLabelsFirstBar):
            plt.text(x=i,
                     y=max(messageValues) * .05,
                     s=xLabelsFirstBar[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        for i, label in enumerate(xLabelsSecondBar):
            plt.text(x=i + 0.4,
                     # use online values here to have the texts on the same height
                     y=max(messageValues) * .05,
                     s=xLabelsSecondBar[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        for i in range(countOfEntries):
            plt.text(x=i,
                     y=-max(messageValues) * .05,
                     s=f"Platz {i + 1}.",
                     color='black', )

        # extract the y-labels from the graph
        labels = [item.get_text() for item in ax.get_yticklabels()]

        # calculate hours from minutes to display
        for i in range(len(labels)):
            labels[i] = int(labels[i])

        # insert values next to y-axis
        ax.set_yticklabels(labels)

        # show legend in the top right corner
        ax.legend()

        # adjust positioning
        plt.subplots_adjust(left=0.15, right=0.95, top=0.90, bottom=0.1)

        savePath: Path = self.basepath.joinpath(f"data/plots/{LeaderboardImageNames.MESSAGES_AND_COMMANDS.value}")

        # save to disk
        plt.savefig(savePath, dpi=250)

        return True

    def createTopOnlineAndStreamDiagram(self) -> bool:
        logger.debug("creating TopOnlineAndStreamDiagram")

        countOfUsers = 5

        if not (session := getSession()):  # TODO outside
            return False

        # noinspection PyUnresolvedReferences
        getQuery = (select(DiscordUser)
                    .order_by(DiscordUser.time_online.desc())
                    .limit(countOfUsers))

        try:
            onlineUsers = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch data for top online users", exc_info=error)
            session.close()

            return False

        # noinspection PyUnresolvedReferences
        getQuery = (select(DiscordUser)
                    .order_by(DiscordUser.time_streamed.desc())
                    .limit(countOfUsers))

        try:
            streamUsers = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch data for top stream users", exc_info=error)
            session.close()

            return False

        if not onlineUsers or not streamUsers:
            logger.error("no online or stream users")
            session.close()

            return False

        # extracting the values
        onlineValues = [user.time_online for user in onlineUsers]
        onlineValues.sort(reverse=True)
        streamValues = [user.time_streamed for user in streamUsers]
        streamValues.sort(reverse=True)

        session.close()

        self._createDoubleBarDiagram(onlineValues,
                                     streamValues,
                                     "Online",
                                     "Stream",
                                     [user.username for user in onlineUsers],
                                     [user.username for user in streamUsers],
                                     "Online- und Stream-Zeit",
                                     LeaderboardImageNames.ONLINE_AND_STREAM)

        return True

    def createTopRelationDiagram(self) -> bool:
        """
        Creates the plot with the current data from the database

        :return: Success or failure
        """
        logger.debug("creating TopRelationDiagram")

        countOfRelations = 5

        if not (session := getSession()):  # TODO outside
            return False

        getOnlineQuery = (select(DiscordUserRelation)
                          .where(DiscordUserRelation.type == RelationTypeEnum.ONLINE.value)
                          .order_by(DiscordUserRelation.value.desc())
                          .limit(countOfRelations))
        getStreamQuery = (select(DiscordUserRelation)
                          .where(DiscordUserRelation.type == RelationTypeEnum.STREAM.value)
                          .order_by(DiscordUserRelation.value.desc())
                          .limit(countOfRelations))

        try:
            onlineRelations = session.scalars(getOnlineQuery).all()
            streamRelations = session.scalars(getStreamQuery).all()
        except Exception as error:
            logger.error("couldn't fetch data for leaderboard", exc_info=error)
            session.close()

            return False

        if not onlineRelations or not streamRelations:
            logger.error("no online or stream relations")
            session.close()

            return False

        # extracting the values
        onlineValues = [relation.value for relation in onlineRelations]
        onlineValues.sort(reverse=True)
        streamValues = [relation.value for relation in streamRelations]
        streamValues.sort(reverse=True)

        def sortNames(name1: str, name2: str, position: int) -> str:
            """
            Returns the name depending on the value and the position in the string
            """
            if name1 > name2:
                if position == 1:
                    return name1
                else:
                    return name2
            else:
                if position == 1:
                    return name2
                else:
                    return name1

        # we cant style that besser because of Python
        self._createDoubleBarDiagram(onlineValues,
                                     streamValues,
                                     "Online",
                                     "Stream",
                                     [
                                         f"{sortNames(relation.discord_user_1.username, relation.discord_user_2.username, 1)} & "
                                         f"{sortNames(relation.discord_user_1.username, relation.discord_user_2.username, 2)}"
                                         for relation in onlineRelations],
                                     [
                                         f"{sortNames(relation.discord_user_1.username, relation.discord_user_2.username, 1)} & "
                                         f"{sortNames(relation.discord_user_1.username, relation.discord_user_2.username, 2)}"
                                         for relation in streamRelations],
                                     "Online- und Stream-Relationen",
                                     LeaderboardImageNames.RELATIONS)

        return True

    def createTopGamesDiagram(self) -> bool:
        """
        Creates the plot with the current data from the database

        :return: Success or failure
        """
        logger.debug("creating TopGamesDiagram")

        if not (session := getSession()):  # TODO outside
            return False

        countOfGames = 5
        games = getMostPlayedGames(session, countOfGames)

        session.close()

        if not games:
            logger.error("couldn't fetch games")

            return False

        gameNames: list[str] = []
        values: list[int] = []
        path: Path = self.basepath.joinpath(f"data/plots/{LeaderboardImageNames.ACTIVITIES.value}")

        for game in games:
            gameNames.append(game['name'])
            values.append(int(game['time_played']))

        # sort games and values descending
        gameNames, values = zip(*sorted(zip(gameNames, values), key=lambda x: x[1], reverse=True))

        # prepare text for the x-axis
        xLabels = [textwrap.fill(xLabel[:40], 10) for xLabel in list(gameNames)]

        fig, ax = plt.subplots()

        plt.bar(gameNames,
                values,
                color=Colors.MAIN.value, )
        plt.xlabel("Aktivitäten", labelpad=10)
        plt.ylabel("Stunden", labelpad=42)
        plt.title(f"Top {countOfGames} Aktivitäten")

        plt.gca().set_xticks(gameNames)
        plt.gca().set_xticklabels([])

        for i in range(countOfGames):
            plt.text(x=i - .25,
                     y=-max(values) * .05,
                     s=f"Platz {i + 1}.",
                     color='black', )

        # add labels manually to have them in the bar
        for i, label in enumerate(xLabels):
            plt.text(x=i,
                     y=max(values) * .1,
                     s=xLabels[i],
                     ha='center',
                     va='center',
                     fontsize=10,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

        # extract the y-labels from the graph
        labels = [item.get_text() for item in ax.get_yticklabels()]

        # calculate hours from minutes to display
        for i in range(len(labels)):
            try:
                labels[i] = getFormattedTime(int(labels[i]))
            except ValueError:
                logger.warning("encountered ValueError, inserting default value")

                labels[i] = 0

        # insert values next to y-axis
        ax.set_yticklabels(labels)

        plt.subplots_adjust(left=0.15, right=0.95, top=0.90, bottom=0.1)
        plt.savefig(path, dpi=250)

        return True
