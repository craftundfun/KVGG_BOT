import json
import logging
from io import BytesIO

import discord
import httpx

from src.Helper import ReadParameters

logger = logging.getLogger("KVGG_BOT")


class ApiServices:
    url = "https://api.api-ninjas.com/v1/"

    def __init__(self):
        self.apiKey = ReadParameters.getParameter(ReadParameters.Parameters.API_KEY)

    async def getWeather(self, ctx: discord.interactions.Interaction, city: str):
        """
        Returns the current weather of the given city

        :param ctx: Interaction from discord
        :param city: City for the weather call
        :return:
        """
        response: discord.InteractionResponse = ctx.response
        webhook: discord.Webhook = ctx.followup
        payload = {
            'city': city,
            'country': 'Germany',
        }

        logger.debug("setting response to thinking")
        await response.defer(thinking=True)

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
            await webhook.send("Es gab ein Problem! Vielleicht lag deine Stadt / dein Ort nicht in Deutschland? Wenn"
                               " das Problem weiterhin auftreten sollte liegt es wohl nicht an dir.")

            return

        logger.debug("retrieved data successfully")

        answerWeather = answerWeather.content.decode('utf-8')
        dataWeather = json.loads(answerWeather)
        answerAir = answerAir.content.decode('utf-8')
        dataAir = json.loads(answerAir)

        answerWeather = "Aktuell sind es in %s %d°C. Die gefühlte Temperatur liegt bei %s°C. Es herrscht eine " \
                        "Luftfeuchtigkeit von %d Prozent. Es ist zu %s Prozent bewölkt. Der Luftqualitätsindex liegt " \
                        "bei %s (von maximal 500)." % (
                            city, dataWeather['temp'], dataWeather['feels_like'], dataWeather['humidity'],
                            dataWeather['cloud_pct'], dataAir['overall_aqi'],
                        )

        await webhook.send(answerWeather)

    async def convertCurrency(self, ctx: discord.interactions.Interaction, have: str, want: str, amount: float):
        """
        Converts the given currency into the other

        :param ctx: Interaction from discord
        :param have: Start currency
        :param want: End currency
        :param amount: Amount of money
        :return:
        """
        response: discord.InteractionResponse = ctx.response
        webhook: discord.Webhook = ctx.followup

        if len(have) != 3 or len(want) != 3:
            await response.send_message("Eine deiner Währungen ist kein dreistelliger Währungscode!")

            return

        payload = {
            'have': have,
            'want': want,
            'amount': amount,
        }

        logger.debug("setting response to thinking")
        await response.defer(thinking=True)

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
            await webhook.send("Es gab ein Problem! Existieren deine Währungscodes überhaupt? Wenn ja, dann liegt "
                               "es nicht an dir.")

            return

        logger.debug("retrieved data successfully")

        data = answer.content.decode('utf-8')
        data = json.loads(data)
        answer = "%s %s sind %s %s." % (
            data['old_amount'], data['old_currency'], data['new_amount'], data['new_currency'])

        await webhook.send(answer)

    async def generateQRCode(self, ctx: discord.interactions.Interaction, text: str):
        """
        Generates a QRCode from the given text

        :param ctx: Interation from discord
        :param text: Text to convert into a QRCode
        :return:
        """
        response: discord.InteractionResponse = ctx.response
        webhook: discord.Webhook = ctx.followup
        payload = {
            'data': text,
            'size': "1000x1000"
        }
        headers = {
            'Accept': 'image/png',
        }

        logger.debug("setting response to thinking")
        await response.defer(thinking=True)

        async with httpx.AsyncClient() as client:
            logger.debug("calling API for QR-Code generation")
            answer = await client.get(
                "https://api.qrserver.com/v1/create-qr-code/",
                params=payload,
                headers=headers,
            )

        if answer.status_code != 200:
            logger.warning("API sent an invalid response!: " + answer.content.decode('utf-8'))
            await webhook.send("Es ist ein Problem aufgetreten!")

            return

        logger.debug("retrieved data successfully")

        await webhook.send(file=discord.File(BytesIO(answer.content), filename="qrcode.png"))
