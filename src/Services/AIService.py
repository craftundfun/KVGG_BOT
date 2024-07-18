import json

import speech_recognition as sr
from discord import VoiceChannel, Client
from discord.ext import voice_recv

from src.Manager.TTSManager import TTSService
from src.Services.VoiceClientService import VoiceClientService


class AIService:

    def __init__(self, client: Client = None):
        self.voiceClientService = VoiceClientService(client)

        self.client = client

    async def listen(self, channel: VoiceChannel):
        class ListenSink(voice_recv.WaveSink):

            def __init__(self, aiVoiceClientService):
                super().__init__(RECORDED_SOUND)

                self.recognizer = sr.Recognizer()
                self.aiVoiceClientService = aiVoiceClientService
                self.ttsService = TTSService()

            def cleanup(self) -> None:
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

                    loop = self.aiVoiceClientService.getLoop()
                    loop.create_task(self.ttsService.generateTTS(final_text))
                    loop.create_task(self.aiVoiceClientService.play(channel, "./data/sounds/tts.mp3", force=True))
                except Exception as error:
                    print(error)

        return await self.voiceClientService.listen(channel, ListenSink(self.voiceClientService))


RECORDED_SOUND = "./sound.wav"
