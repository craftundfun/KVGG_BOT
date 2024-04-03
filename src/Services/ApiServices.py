import json
import logging
from pathlib import Path

import httpx
import requests

from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("KVGG_BOT")


class ApiServices:
    url = "https://api.api-ninjas.com/v1/"
    basepath = Path(__file__).parent.parent.parent

    def __init__(self):
        self.apiKey = getParameter(Parameters.API_KEY)

    # noinspection PyMethodMayBeStatic
    async def getJoke(self, category: str) -> str:
        """
        Returns a joke after requesting if from the API.

        :param category: Optional category choice by the user
        """
        payload = {
            'language': 'de',
            'category': category,
        }
        answer = requests.get(
            'https://witzapi.de/api/joke',
            params=payload,
        )

        if answer.status_code != 200:
            logger.warning(f"joke-API sent an invalid response! Code: {answer.status_code}")

            return "Es gab Probleme beim Erreichen der API - kein Witz."

        answer = answer.content.decode('utf-8')
        data = json.loads(answer)

        return data[0]['text']

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
            logger.debug("calling API for weather")

            answerWeather = await client.get(
                self.url + "weather",
                params=payload,
                headers={
                    'X-API-Key': self.apiKey,
                }
            )

            logger.debug("calling API for air-quality")

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

        logger.debug("retrieved data successfully")

        answerWeather = answerWeather.content.decode('utf-8')
        dataWeather = json.loads(answerWeather)
        answerAir = answerAir.content.decode('utf-8')
        dataAir = json.loads(answerAir)

        return (f"Aktuell sind es in {city} {dataWeather['temp']}°C. Die gefühlte Temperatur liegt bei "
                f"{dataWeather['feels_like']}°C. Es herrscht eine Luftfeuchtigkeit von {dataWeather['humidity']} "
                f"Prozent. Es ist zu {dataWeather['cloud_pct']} Prozent bewölkt. Der Luftqualitätsindex liegt bei "
                f"{dataAir['overall_aqi']} (von maximal 500).")

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
            logger.debug("calling API for currency-conversion")

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

        logger.debug("retrieved data successfully")

        data = answer.content.decode('utf-8')
        data = json.loads(data)

        return f"{data['old_amount']} {data['old_currency']} sind {data['new_amount']} {data['new_currency']}."

    async def generateQRCode(self, text: str) -> Path | str:
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
            logger.debug("calling API for QR-Code generation")

            answer = await client.get(
                "https://api.qrserver.com/v1/create-qr-code/",
                params=payload,
                headers=headers,
            )

        if answer.status_code != 200:
            logger.warning("API sent an invalid response!: " + answer.content.decode('utf-8'))

            return "Es ist ein Problem aufgetreten!"

        logger.debug("retrieved data successfully")

        path: Path = self.basepath.joinpath(f"data/qrcode/qrcode.png")

        try:
            with open(path, 'wb') as file:
                file.write(answer.content)
        except Exception as error:
            logger.error("couldn't write qrcode content to file", exc_info=error)

            return "Es ist ein Problem aufgetreten!"

        return path
