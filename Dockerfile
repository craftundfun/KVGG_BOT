FROM python:3.11-slim

COPY requirements.txt .
COPY main.py .
COPY data ./data
COPY src ./src
COPY parameters.env .
COPY Web ./Web

RUN apt-get update && apt-get install -y ffmpeg
RUN pip install -r requirements.txt
RUN apt-get install libffi-dev
RUN mkdir "Logs"

ENV PATH="/usr/bin/ffmpeg:${PATH}"
ENV TZ=Europe/Berlin

EXPOSE 8000

CMD ["python3", "./main.py"]