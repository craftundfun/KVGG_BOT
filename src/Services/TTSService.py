import logging
import os
from pathlib import Path

from gtts import gTTS

logger = logging.getLogger("KVGG_BOT")


class TTSService:
    language = "de"
    basepath = Path(__file__).parent.parent.parent

    def __init__(self):
        pass

    async def generateTTS(self, message: str, path: str = "data/sounds/tts.mp3") -> bool:
        """
        Creates the given message in german as a TTS. Return is a boolean to determine the success of the operation.

        :param message: Message to say
        :param path: Path to save the MP3-File
        :return:
        """
        logger.debug(f"creating TTS: {message}")

        try:
            tts = gTTS(text=message, lang=self.language, slow=False)
            path = os.path.abspath(
                os.path.join(self.basepath, "..", "..", "..", f"{self.basepath}/{path}")
            )

            tts.save(path)
        except Exception as error:
            logger.error("couldn't create TTS", exc_info=error)

            return False
        else:
            return True
