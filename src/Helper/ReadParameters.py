import functools
import logging
import os
from enum import Enum

from dotenv import load_dotenv

# Get the absolute path of the directory where the script is located
script_dir = os.path.abspath(os.path.dirname(__file__))

# Construct the path to the .env file
env_path = os.path.join(script_dir, '..', '..', 'parameters.env')

# Load the .env file
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("KVGG_BOT")


class Parameters(Enum):
    DATABASE_HOST = 0
    DATABASE_USERNAME = 1
    DATABASE_PASSWORD = 2
    DATABASE_SCHEMA = 3
    DISCORD_TOKEN = 4
    EMAIL_SERVER = 5
    EMAIL_PORT = 6
    EMAIL_USERNAME = 7
    EMAIL_PASSWORD = 8
    API_KEY = 9


@functools.lru_cache(maxsize=32)
def getParameter(param: Parameters) -> str:
    match param:
        case Parameters.DATABASE_HOST:
            return os.getenv("DATABASE_HOST")
        case Parameters.DATABASE_USERNAME:
            return os.getenv("DATABASE_USERNAME")
        case Parameters.DATABASE_PASSWORD:
            return os.getenv("DATABASE_PASSWORD")
        case Parameters.DATABASE_SCHEMA:
            return os.getenv("DATABASE_SCHEMA")
        case Parameters.DISCORD_TOKEN:
            return os.getenv("DISCORD_TOKEN")
        case Parameters.EMAIL_SERVER:
            return os.getenv("EMAIL_SERVER")
        case Parameters.EMAIL_PORT:
            return os.getenv("EMAIL_PORT")
        case Parameters.EMAIL_USERNAME:
            return os.getenv("EMAIL_USERNAME")
        case Parameters.EMAIL_PASSWORD:
            return os.getenv("EMAIL_PASSWORD")
        case Parameters.API_KEY:
            return os.getenv("API_KEY")
        case _:
            logger.error(f"parameter {param} not found")

            return ""
