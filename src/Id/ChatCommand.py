from enum import Enum


@DeprecationWarning
class ChatCommand(Enum):
    HELP = "!help"
    JOKE = "!witz"
    MOVE = "!move"
    QUOTE = "!zitat"
    TIME = "!zeit"
    STREAM = "!stream"
    WhatsApp = "!whatsapp"
    LEADERBOARD = "!leaderboard"
    REGISTRATION = "!registrieren"
    RENE_COUNTER = "!rene"
    FELIX_COUNTER = "!felix"
    PAUL_COUNTER = "!paul"
    BJARNE_COUNTER = "!bjarne"
    UNIVERSITY = "!uni"
    OLEG_COUNTER = "!oleg"
    JJ_COUNTER = "!jj"
    LOGS = "!logs"
    COOKIE_COUNTER = "!keks"
    CARL_COUNTER = "!carl"
    XP_BOOST_SPIN = "!spin"
    XP_INVENTORY = "!inventory"
    XP = "!xp"
