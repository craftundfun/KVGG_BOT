import logging
import textwrap
from enum import Enum
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from discord import Client

from src.Helper.GetFormattedTime import getFormattedTime
from src.Services.GameDiscordService import GameDiscordService
from src.View.PaginationView import PaginationViewDataItem, PaginationViewDataTypes

logger = logging.getLogger("KVGG_BOT")


class LeaderboardImageNames(Enum):
    ACTIVITIES = "top_5_activities.png"


class LeaderboardService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.gameDiscordService = GameDiscordService(self.client)

    def getLeaderboard(self) -> list[PaginationViewDataItem]:
        self.createTopGamesDiagram()

        return [PaginationViewDataItem(field_name="Aktivitäten",
                                       data_type=PaginationViewDataTypes.PICTURE,
                                       field_value=f"https://axellotl.de:8000/backend/discord/plots/"
                                                   f"{LeaderboardImageNames.ACTIVITIES.value}"), ]

    def createTopGamesDiagram(self):
        countOfGames = 5
        games = self.gameDiscordService.getMostPlayedGames(countOfGames)

        if not games:
            logger.error("couldn't fetch games")

            return

        gameNames: list[str] = []
        values: list[int] = []
        path: Path = self.basepath.joinpath(f"data/plots/{LeaderboardImageNames.ACTIVITIES.value}")

        for game in games:
            gameNames.append(game['name'])
            values.append(int(game['time_played']))

        # sort games and values
        gameNames, values = zip(*sorted(zip(gameNames, values), key=lambda x: x[1]))

        yTicks = [0]
        maxValue = values[len(values) - 1]
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
                color='#6900ff', )
        plt.xlabel("Aktivitäten")
        plt.ylabel("Stunden", labelpad=35)
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
                     y=values[len(values) - 1] * .1,
                     s=xLabels[i],
                     ha='center',
                     va='center',
                     fontsize=10,
                     color='white',
                     path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

        plt.subplots_adjust(left=0.125, right=0.9, top=0.90, bottom=0.1)
        plt.savefig(path)
