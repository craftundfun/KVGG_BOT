import json
import logging
from io import BytesIO

import discord
import httpx

from src.Helper import ReadParameters
from src.Helper.DictionaryFuntionKeyDecorator import validateKeys

logger = logging.getLogger("KVGG_BOT")


class ApiServices:
    url = "https://api.api-ninjas.com/v1/"

    def __init__(self):
        self.apiKey = ReadParameters.getParameter(ReadParameters.Parameters.API_KEY)

    @validateKeys
    async def getWeather(self, city: str) -> str:
        """
        Returns the current weather of the given city

        :param city: City for the weather call
        :return str: answer
        """
        payload = {
            'city': city,
            'country': 'Germany',
        }

        async with httpx.AsyncClient() as client:
            answerWeather = await client.get(
                self.url + "weather",
                params=payload,
                headers={
                    'X-API-Key': self.apiKey,
                }
            )

            answerAir = await client.get(
                self.url + "airquality",
                params=payload,
                headers={
                    'X-API-Key': self.apiKey,
                }
            )

        if answerWeather.status_code != 200 or answerAir.status_code != 200:
            logger.warning("API sent an invalid response!: " + answerWeather.content.decode('utf-8'))
            return "Es gab ein Problem! Vielleicht lag deine Stadt / dein Ort nicht in Deutschland? Wenn" \
                   " das Problem weiterhin auftreten sollte liegt es wohl nicht an dir."

        answerWeather = answerWeather.content.decode('utf-8')
        dataWeather = json.loads(answerWeather)
        answerAir = answerAir.content.decode('utf-8')
        dataAir = json.loads(answerAir)

        return "Aktuell sind es in %s %d°C. Die gefühlte Temperatur liegt bei %s°C. Es herrscht eine " \
               "Luftfeuchtigkeit von %d Prozent. Es ist zu %s Prozent bewölkt. Der Luftqualitätsindex liegt " \
               "bei %s (von maximal 500)." % (
            city, dataWeather['temp'], dataWeather['feels_like'], dataWeather['humidity'],
            dataWeather['cloud_pct'], dataAir['overall_aqi'])

    @validateKeys
    async def convertCurrency(self, have: str, want: str, amount: float) -> str:
        """
        Converts the given currency into the other

        :param have: Start currency
        :param want: End currency
        :param amount: Amount of money
        :return:
        """
        if len(have) != 3 or len(want) != 3:
            return "Eine deiner Währungen ist kein dreistelliger Währungscode!"

        payload = {
            'have': have,
            'want': want,
            'amount': amount,
        }

        async with httpx.AsyncClient() as client:
            answer = await client.get(
                self.url + "convertcurrency",
                params=payload,
                headers={
                    'X-API-Key': self.apiKey,
                }
            )

        if answer.status_code != 200:
            logger.warning("API sent an invalid response!: " + answer.content.decode('utf-8'))
            return "Es gab ein Problem! Existieren deine Währungscodes überhaupt? Wenn ja, dann liegt " \
                   "es nicht an dir."

        data = answer.content.decode('utf-8')
        data = json.loads(data)
        return "%s %s sind %s %s." % (
            data['old_amount'], data['old_currency'], data['new_amount'], data['new_currency'])

    @validateKeys
    async def generateQRCode(self, text: str) -> discord.File | str:
        """
        Generates a QRCode from the given text

        :param text: Text to convert into a QRCode
        :return:
        """
        payload = {
            'data': text,
            'size': "1000x1000"
        }
        headers = {
            'Accept': 'image/png',
        }

        async with httpx.AsyncClient() as client:
            answer = await client.get(
                "https://api.qrserver.com/v1/create-qr-code/",
                params=payload,
                headers=headers,
            )

        if answer.status_code != 200:
            logger.warning("API sent an invalid response!: " + answer.content.decode('utf-8'))
            return "Es ist ein Problem aufgetreten!"

        return discord.File(BytesIO(answer.content), filename="qrcode.png")
