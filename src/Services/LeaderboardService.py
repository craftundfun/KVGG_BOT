import asyncio
import logging
import random
import textwrap
from enum import Enum
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from discord import Client
from sqlalchemy import select

from src.DiscordParameters.Colors import Colors
from src.Helper.GetFormattedTime import getFormattedTime
from src.Manager.DatabaseManager import getSession
from src.Repository.DiscordUser.Entity.DiscordUser import DiscordUser
from src.Repository.Game.Repository.DiscordGameRepository import getMostPlayedGames
from src.Repository.UserRelation.Entity.DiscordUserRelation import DiscordUserRelation
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
    url = "https://axellotl.de:8000/backend/discord/plots/"

    def __init__(self, client: Client):
        self.client = client

        self.gameDiscordService = GameDiscordService(self.client)

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

            if self.createTopGamesDiagram():
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

        if not (session := getSession()):
            return False

        messageQuery = (select(DiscordUser)
                        .order_by(DiscordUser.message_count_all_time.desc())
                        .limit(countOfEntries))
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

        if not (session := getSession()):
            return False

        getQuery = (select(DiscordUser)
                    .where(DiscordUser.time_online.is_not(None))
                    .order_by(DiscordUser.time_online.desc())
                    .limit(countOfUsers))

        try:
            onlineUsers = session.scalars(getQuery).all()
        except Exception as error:
            logger.error("couldn't fetch data for top online users", exc_info=error)
            session.close()

            return False

        getQuery = (select(DiscordUser)
                    .where(DiscordUser.time_online.is_not(None))
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

        if not (session := getSession()):
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

        if not (session := getSession()):
            return False

        countOfGames = 5
        games = getMostPlayedGames(session, countOfGames)

        if not games:
            logger.error("couldn't fetch games")
            session.close()

            return False

        session.close()

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
