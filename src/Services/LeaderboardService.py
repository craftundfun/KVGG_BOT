import logging
import random
import textwrap
from enum import Enum
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from discord import Client

from src.DiscordParameters.Colors import Colors
from src.Helper.GetFormattedTime import getFormattedTime
from src.Services.Database import Database
from src.Services.GameDiscordService import GameDiscordService
from src.Services.RelationService import RelationTypeEnum
from src.View.PaginationView import PaginationViewDataItem, PaginationViewDataTypes

logger = logging.getLogger("KVGG_BOT")


class LeaderboardImageNames(Enum):
    ACTIVITIES = "top_5_activities.png"
    RELATIONS = "top_5_relations.png"

    @classmethod
    def getNameForImage(cls, imageName: "LeaderboardImageNames"):
        match imageName:
            case LeaderboardImageNames.ACTIVITIES:
                return "Aktivitäten"
            case LeaderboardImageNames.RELATIONS:
                return "Relationen"
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
        availablePlots = []
        data = []

        if self.createTopGamesDiagram():
            availablePlots.append(LeaderboardImageNames.ACTIVITIES)

        if self.createTopRelationDiagram():
            availablePlots.append(LeaderboardImageNames.RELATIONS)

        for plot in availablePlots:
            data.append(
                PaginationViewDataItem(
                    field_name=LeaderboardImageNames.getNameForImage(plot),
                    data_type=PaginationViewDataTypes.PICTURE,
                    # add random number to URL to avoid discords image caching, lol
                    field_value=self.url + plot.value + f"/{random.randint(0, 10000000000)}",
                )
            )

        print("data", data)

        return data

    def createTopRelationDiagram(self) -> bool:
        logger.debug("creating TopRelationDiagram")

        countOfRelations = 5
        query = ("SELECT d1.username AS username_1, d2.username AS username_2, dur.value"
                 " FROM discord_user_relation dur "
                 "JOIN discord d1 ON d1.id = dur.discord_user_id_1 "
                 "JOIN discord d2 ON d2.id = dur.discord_user_id_2 "
                 "WHERE dur.type = %s "
                 "ORDER BY dur.value DESC "
                 "LIMIT %s")
        database = Database()
        path: Path = self.basepath.joinpath(f"data/plots/{LeaderboardImageNames.RELATIONS.value}")

        if not (onlineRelations := database.fetchAllResults(query, (RelationTypeEnum.ONLINE.value, countOfRelations,))):
            logger.error("couldn't fetch onlineRelations")

            return False

        if not (streamRelations := database.fetchAllResults(query, (RelationTypeEnum.STREAM.value, countOfRelations))):
            logger.error("couldn't fetch streamRelations")

            return False

        onlineValues = [relation['value'] for relation in onlineRelations]
        onlineValues.sort(reverse=True)
        streamValues = [relation['value'] for relation in streamRelations]
        streamValues.sort(reverse=True)

        yTicks = [0]
        maxValue = max(onlineValues)
        stepSize = maxValue // countOfRelations
        stepSizeBefore = 0
        yTickLabels = []

        # calculate steps of the y-axis
        for _ in range(countOfRelations):
            stepSizeBefore += stepSize
            yTicks.append(int(stepSizeBefore))

        for yTick in yTicks:
            yTickLabels.append(getFormattedTime(yTick))

        xLabelsOnline = [textwrap.fill(f"{relation['username_1']} & {relation['username_2']}", 30)
                         for relation in onlineRelations]
        xLabelsStream = [textwrap.fill(f"{relation['username_1']} & {relation['username_2']}", 30)
                         for relation in streamRelations]

        bar_width = 0.4

        fig, ax = plt.subplots()

        ax.bar(np.arange(len(onlineValues)), onlineValues, width=bar_width, color=Colors.MAIN.value, label='Online')
        ax.bar(np.arange(len(streamValues)) + bar_width, streamValues, width=bar_width,
               color=Colors.SECONDARY_MAIN.value,
               label='Stream')
        ax.set_ylabel('Stunden', labelpad=8)
        ax.set_title('Online- und Stream-Relationen')

        plt.gca().set_xticks([])
        plt.gca().set_xticklabels([])
        # plt.gca().set_yticklabels([])

        for i, label in enumerate(xLabelsOnline):
            plt.text(x=i,
                     y=max(onlineValues) * .05,
                     s=xLabelsOnline[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        for i, label in enumerate(xLabelsStream):
            plt.text(x=i + 0.4,
                     # use online values here to have the texts on the same height
                     y=max(onlineValues) * .05,
                     s=xLabelsStream[i],
                     ha='center',
                     fontsize=12,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')],
                     rotation=90, )

        labels = [item.get_text() for item in ax.get_yticklabels()]

        for i in range(len(labels)):
            labels[i] = getFormattedTime(int(labels[i]))

        ax.set_yticklabels(labels)
        ax.legend()
        plt.subplots_adjust(left=0.15, right=0.95, top=0.90, bottom=0.1)

        plt.savefig(path, dpi=500)

        return True

    def createTopGamesDiagram(self) -> bool:
        logger.debug("creating TopGamesDiagram")

        countOfGames = 5
        games = self.gameDiscordService.getMostPlayedGames(countOfGames)

        if not games:
            logger.error("couldn't fetch games")

            return False

        gameNames: list[str] = []
        values: list[int] = []
        path: Path = self.basepath.joinpath(f"data/plots/{LeaderboardImageNames.ACTIVITIES.value}")

        for game in games:
            gameNames.append(game['name'])
            values.append(int(game['time_played']))

        # sort games and values
        gameNames, values = zip(*sorted(zip(gameNames, values), key=lambda x: x[1], reverse=True))

        yTicks = [0]
        maxValue = max(values)
        stepSize = maxValue // countOfGames
        stepSizeBefore = 0
        yTickLabels = []

        # calculate steps of the y-axis
        for _ in range(countOfGames):
            stepSizeBefore += stepSize
            yTicks.append(int(stepSizeBefore))

        for yTick in yTicks:
            yTickLabels.append(getFormattedTime(yTick))

        # prepare text for the x-axis
        xLabels = [textwrap.fill(xLabel[:40], 10) for xLabel in list(gameNames)]

        plt.figure(dpi=250)
        plt.bar(gameNames,
                values,
                color=Colors.MAIN.value, )
        plt.xlabel("Aktivitäten")
        plt.ylabel("Stunden", labelpad=42)
        plt.title(f"Top {countOfGames} Aktivitäten")

        plt.gca().set_yticks(yTicks)
        plt.gca().set_yticklabels([])
        plt.gca().set_xticks(gameNames)
        plt.gca().set_xticklabels([])

        # add labels manually => otherwise type incompatibility
        for i, label in enumerate(yTickLabels):
            # for x placement: -1.5 * countOfGames * (0.15 - (0.025 * (countOfGames // 5)))
            plt.text(-1, yTicks[i], label, ha="center", va="center", fontsize=8)

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

        plt.subplots_adjust(left=0.15, right=0.95, top=0.90, bottom=0.1)
        plt.savefig(path)

        return True
