import asyncio
import json
import logging
import threading
import wave
from asyncio import sleep, AbstractEventLoop

import speech_recognition as sr
from discord import Member
from discord import VoiceChannel, Client
from discord.ext import voice_recv
from discord.ext.voice_recv import VoiceData

from src.Manager.TTSManager import TTSService
from src.Services.VoiceClientService import VoiceClientService

logger = logging.getLogger("KVGG_BOT")

RECORDED_SOUND = "./sound.wav"
canCancel = True


class ListenSink(voice_recv.WaveSink):

    def __init__(self, aiVoiceClientService, channel: VoiceChannel):
        super().__init__(RECORDED_SOUND)

        self.recognizer = sr.Recognizer()
        self.aiVoiceClientService = aiVoiceClientService
        self.ttsService = TTSService()

        self.loop = self.aiVoiceClientService.getLoop()
        self.answerTask = None
        self.channel = channel

    def write(self, user: Member, data: VoiceData) -> None:
        global canCancel

        if canCancel:
            print("recording")
            super().write(user, data)
        else:
            print("not recording")

            return

        if self.answerTask and canCancel:
            self.answerTask.cancel()
            print("cancelled")

        try:
            self.answerTask = self.loop.create_task(self.sleepTillSilence())
            print("fertig")
        except Exception as error:
            logger.error("error", exc_info=error)

    async def sleepTillSilence(self):
        print("going sleep")
        # wait for 1 second silence
        await sleep(.5)
        print("woke up")

        threading.Thread(target=self.answer, args=(self.loop,)).start()

    def answer(self, loop: AbstractEventLoop):
        global canCancel
        print("created thread")
        canCancel = False

        try:
            print("cleanup")

            audio_data = sr.AudioFile(RECORDED_SOUND)

            with audio_data as source:
                audio = self.recognizer.record(source)

            text = self.recognizer.recognize_vosk(audio, language="de-DE")
            print(text)

            text = json.loads(text)["text"]

            import requests

            url = "http://localhost:11434/api/generate"
            data = {
                "model": "llama2-uncensored",
                "prompt": "Antworte auf Deutsch: " + text,
            }

            # print("text: ", text)

            response = requests.post(url, data=json.dumps(data), headers={"Content-Type": "application/json"})
            content = response.text.split("\n")
            liste = [json.loads(i) for i in content if i]

            final_text = ""

            for part in liste:
                final_text += part["response"]

                if part["done"]:
                    break

            # print("Finaltext: ", final_text)
            # print(response.text)

            asyncio.run_coroutine_threadsafe(self.ttsService.generateTTS(final_text), loop)
            asyncio.run_coroutine_threadsafe(self.aiVoiceClientService.play(self.channel,
                                                                            "./data/sounds/tts.mp3",
                                                                            force=True,
                                                                            shouldHandUp=False, ),
                                             loop, )

            with wave.open(RECORDED_SOUND, "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.SAMPLE_WIDTH)
                wf.setframerate(self.SAMPLING_RATE)
                wf.writeframes(b'')

                print("cleared file")
        except Exception as error:
            logger.error("error", exc_info=error)
        finally:
            canCancel = True

            print("set cancel to true")
            return


class AIService:

    def __init__(self, client: Client = None):
        self.voiceClientService = VoiceClientService(client)

        self.client = client

    async def listen(self, channel: VoiceChannel, member: Member):
        return await self.voiceClientService.listen(channel)
