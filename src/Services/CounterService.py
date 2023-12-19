import json
import logging
from pathlib import Path

from discord import Client
from discord import Member

from src.Id.RoleId import RoleId
from src.Services.Database import Database
from src.Services.ProcessUserInput import hasUserWantedRoles

logger = logging.getLogger("KVGG_BOT")


class CounterService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

    async def createNewCounter(self, name: str, description: str, member: Member) -> str:
        """
        Creates a new counter for everyone in the Discord-Database.

        :param name: Name of the new counter
        :param description: Description of the new counter
        :param member: Member who creates the counter
        """
        try:
            with open(f"{self.basepath}/data/CounterNames", "r") as file:
                counters: dict = json.load(file)
        except Exception as error:
            logger.error("couldn't read counters from disk", exc_info=error)

            return "Es ist ein Fehler aufgetreten!"

        if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug(f"{member.display_name} has no rights to create counters")

            return "Dir fehlen die Berechtigungen dafür!"

        if len(counters.keys()) >= 25:
            logger.critical("cant add more than 25 counter names")

            return "Es gibt bereits zu viele Counter."

        if name.count(" ") > 0:
            logger.debug("counter name contains white spaces")

            return "Dein Counter-Name darf keine Leerzeichen enthalten."

        if not name.isalnum():
            logger.debug("counter name not alphanumeric")

            return "Dein Counter-Name darf nur alphanumerisch sein!"

        if len(name) > 20:
            logger.debug("counter name is longer than 20 characters")

            return "Dein Counter-Name darf nicht länger als 20 Zeichen sein!"

        if name in counters.keys():
            logger.debug("new counter name already existing")

            return "Der Counter existiert bereits!"

        if len(description) > 100:
            logger.debug("description for new counter too long")

            return "Deine Beschreibung ist zu lang!"

        name = name.lower()
        counters[name] = description

        try:
            with open(f"{self.basepath}/data/CounterNames", "w") as file:
                json.dump(counters, file)
        except Exception as error:
            logger.error("couldn't read counters from disk", exc_info=error)

            return "Es ist ein Fehler aufgetreten!"

        database = Database()
        query = "UPDATE discord SET counter = JSON_INSERT(counter, %s, 0)"

        if not database.runQueryOnDatabase(query, (f'$.{name}',)):
            logger.error("couldn't update database")

            return "Es gab einen Fehler!"
        else:
            logger.critical(f"{member.display_name} hat einen neuen Counter erstellt: {name} - {description}")

        return "Dein neuer Counter wurde erstellt!"
