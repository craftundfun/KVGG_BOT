import logging
from pathlib import Path

from discord import Client
from discord import Member

from src.DiscordParameters.AchievementParameter import AchievementParameter
from src.Helper.WriteSaveQuery import writeSaveQuery
from src.Id.RoleId import RoleId
from src.Repository.DiscordUserRepository import getDiscordUser
from src.Services.Database import Database
from src.Services.ExperienceService import ExperienceService
from src.Services.ProcessUserInput import hasUserWantedRoles, getTagStringFromId
from src.Services.TTSService import TTSService
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")


class CounterService:
    basepath = Path(__file__).parent.parent.parent

    def __init__(self, client: Client):
        self.client = client

        self.voiceClientService = VoiceClientService(self.client)
        self.experienceService = ExperienceService(self.client)
        self.ttsService = TTSService()

    async def createNewCounter(self, name: str, description: str, voiceLine: str, member: Member) -> str:
        """
        Creates a new counter for everyone in the Discord-Database.

        :param name: Name of the new counter
        :param description: Description of the new counter
        :param voiceLine: eventual tts voice line
        :param member: Member who creates the counter
        """
        database = Database()

        if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD):
            logger.debug(f"{member.display_name} has no rights to create counters")

            return "Dir fehlen die Berechtigungen dafür!"

        if name.count(" ") > 0:
            logger.debug("counter name contains white spaces")

            return "Dein Counter-Name darf keine Leerzeichen enthalten."

        if len(name) > 20:
            logger.debug("counter name is longer than 20 characters")

            return "Dein Counter-Name darf nicht länger als 20 Zeichen sein!"

        query = "SELECT name FROM counter"

        if not (counterNames := database.fetchAllResults(query)):
            logger.error("couldn't fetch counter from database")

            return "Es gab ein Problem."

        for row in counterNames:
            if row['name'].lower() == name.lower():
                logger.debug("counter name does already exist")

                return "Dieser Counter-Name existiert bereits!"

        if len(description) > 100:
            logger.debug("description for new counter too long")

            return "Deine Beschreibung ist zu lang! Bitte benutze maximal 100 Zeichen!"

        if voiceLine and len(voiceLine) > 200:
            logger.debug("voiceline too long for new counter")

            return "Deine VoiceLine ist zu lang. Bitte benutze maximal 200 Zeichen!"

        name = name.lower()

        if voiceLine:
            query = "INSERT INTO counter (name, description, tts_voice_line) VALUES (%s, %s, %s)"
            parameters = (name, description, voiceLine,)
        else:
            query = "INSERT INTO counter (name, description) VALUES (%s, %s)"
            parameters = (name, description,)

        if not database.runQueryOnDatabase(query, parameters):
            logger.error("couldn't update database")

            return "Es gab einen Fehler!"
        else:
            logger.critical(f"{member.display_name} hat einen neuen Counter erstellt: {name} - {description}")

        return "Dein neuer Counter wurde erstellt!"

    def listAllCounters(self) -> str:
        """
        Returns a list of all counters currently existing
        """
        query = "SELECT * FROM counter"
        database = Database()

        if not (counters := database.fetchAllResults(query)):
            logger.debug("couldn't fetch counter from database")

            return "Es gab ein Problem!"

        answer = "__Es gibt folgende Counter:__\n\n"

        for index, counter in enumerate(counters, 1):
            answer += f"{index}. {counter['name'].capitalize()} - {counter['description']}\n"

        return answer

    async def accessNameCounterAndEdit(self, counterName: str,
                                       user: Member,
                                       member: Member,
                                       param: int | None) -> str:
        """
        Answering given Counter from given User or adds (subtracts) given amount

        :param user: User which counter was requested
        :param counterName: Chosen counter-type
        :param member: Member who requested the counter
        :param param: Optional amount of time to add / subtract
        :raise ConnectionError: If the database connection cant be established
        :return:
        """
        # whole name with description is given -> split to get name
        counterName = counterName.split(" ")[0]

        database = Database()

        logger.debug("%s requested %s-Counter" % (member.name, counterName))

        dcUserDb = getDiscordUser(user, database)
        answerAppendix = ""

        if not dcUserDb:
            logger.warning("couldn't fetch DiscordUser!")

            return "Dieser Benutzer existiert (noch) nicht!"

        query = ("SELECT cdm.*, c.tts_voice_line "
                 "FROM counter_discord_mapping cdm INNER JOIN counter c ON cdm.counter_id = c.id "
                 "WHERE discord_id = %s AND counter_id = "
                 "(SELECT id FROM counter WHERE name = %s)")

        # when there is no mapping, create one
        if not (counterDiscordMapping := database.fetchOneResult(query, (dcUserDb['id'], counterName.lower(),))):
            insertQuery = ("INSERT INTO counter_discord_mapping (counter_id, discord_id) "
                           "VALUES ((SELECT id FROM counter WHERE name = %s), %s)")

            # create new mapping
            if not database.runQueryOnDatabase(insertQuery, (counterName.lower(), dcUserDb['id'])):
                logger.error(f"couldn't create new counter mapping for {counterName}-Counter "
                             f"and {dcUserDb['username']}!")
            else:
                # fetch newly created mapping
                if not (counterDiscordMapping := database.fetchOneResult(query,
                                                                         (dcUserDb['id'], counterName.lower(),))):
                    logger.error(f"couldn't fetch new counter-discord-mapping ({counterName, dcUserDb['username']} "
                                 f"after creating it ")

                    return "Es gab einen Fehler!"

        if not param:
            return "%s hat einen %s-Counter von %d." % (getTagStringFromId(str(user.id)),
                                                        counterName.capitalize(),
                                                        counterDiscordMapping['value'],)

        try:
            value = int(param)
        except ValueError:
            logger.debug("parameter was not convertable to int")

            return "Dein eingegebener Parameter war ungültig! Bitte gib eine (korrekte) Zahl ein!"

        # user trying to add his own counters
        if int(dcUserDb['user_id']) == member.id:
            # don't allow increasing cookie counter
            if counterName.lower() == "cookie" and value > 0:
                logger.debug("%s tried to increase his / her own cookie-counter" % member.name)

                return "Du darfst deinen eigenen Cookie-Counter nicht erhöhen!"

            # don't allow reducing any counter
            if value < 0:
                logger.debug("%s tried to reduce his / her own counter")

                return "Du darfst deinen Counter nicht selber verringern!"

        # only allow privileged users to increase counter by great amounts
        if not hasUserWantedRoles(member, RoleId.ADMIN, RoleId.MOD) and not -1 <= value <= 1:
            logger.debug("%s wanted to edit the counter to greatly" % member.name)

            return "Du darfst einen Counter nur um -1 verringern oder +1 erhöhen!"

        counterDiscordMapping['value'] = counterDiscordMapping['value'] + value

        # special case for cookie-counter due to xp-boost
        if counterName.lower() == "cookie" and value >= 1:
            try:
                await self.experienceService.grantXpBoost(user, AchievementParameter.COOKIE)
            except Exception as error:
                logger.error("failure to run grantXpBoost", exc_info=error)

            answerAppendix = "\n\n" + getTagStringFromId(str(user.id)) + (", du hast für deinen Keks evtl. einen neuen "
                                                                          "XP-Boost erhalten.")

        # dont decrease to counter into negative
        if counterDiscordMapping['value'] < 0:
            counterDiscordMapping['value'] = 0

        name = user.nick if user.nick else user.name

        if counterDiscordMapping['tts_voice_line']:
            tts = counterDiscordMapping['tts_voice_line'].format(name=name)
        else:
            tts = None

        # remove key here to save mapping to the database
        counterDiscordMapping.pop('tts_voice_line')

        query, nones = writeSaveQuery(
            'counter_discord_mapping',
            counterDiscordMapping['id'],
            counterDiscordMapping,
        )

        if not database.runQueryOnDatabase(query, nones):
            logger.critical("couldn't save changes to database")

            return "Es ist ein Fehler aufgetreten."

        if user.voice and tts:
            logger.debug(f"playing TTS for {user.name}, because {member.name} increased the {counterName}-Counter")

            if await self.ttsService.generateTTS(tts):
                await self.voiceClientService.play(user.voice.channel,
                                                   "./data/sounds/tts.mp3",
                                                   None,
                                                   True, )

        return ("Der %s-Counter von %s wurde um %d erhöht!" % (counterName.capitalize(),
                                                               getTagStringFromId(str(user.id)),
                                                               value,)
                + answerAppendix)

    @staticmethod
    def leaderboardForCounter(database: Database) -> str:
        """
        Sort all counters and list the top three per counter

        :return:
        """
        query = "SELECT id, name FROM counter"

        if not (counters := database.fetchAllResults(query)):
            logger.error("couldn't fetch all counters from database")

            return "\nEs gab ein Problem mit den Countern. Diese können aktuell nicht angezeigt werden."

        answer = ""

        for counter in counters:
            query = ("SELECT d.username, cdm.value "
                     "FROM counter_discord_mapping cdm INNER JOIN discord d ON cdm.discord_id = d.id "
                     "WHERE cdm.value > 0 AND cdm.counter_id = %s "
                     "ORDER BY value DESC "
                     "LIMIT 3")

            if not (mapping := database.fetchAllResults(query, (counter['id'],))):
                continue

            answer += f"\n- __{counter['name'].capitalize()}-Counter__:\n"

            for index, map in enumerate(mapping, 1):
                answer += "\t%d: %s - %d\n" % (index, map['username'], map['value'])

        return answer
