FROM python:3.11-slim

COPY requirements.txt .
COPY main.py .
COPY data ./data
COPY src ./src
COPY parameters.env .
COPY Web ./Web

RUN apt-get update && apt-get install -y ffmpeg && apt-get install -y unzip && apt-get install -y wget
RUN pip install -r requirements.txt
RUN apt-get install libffi-dev
RUN mkdir "Logs"

ENV PATH="/usr/bin/ffmpeg:${PATH}"
ENV TZ=Europe/Berlin

EXPOSE 8000

# https://alphacephei.com/vosk/models
# RUN wget https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip # 1.9 GB
RUN wget https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip # 50 MB
RUN unzip vosk-model-small-de-0.15.zip
RUN mv vosk-model-small-de-0.15 model

CMD ["python3", "./main.py"]