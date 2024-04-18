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


ENV PATH="/usr/bin/ffmpeg:${PATH}"

RUN mkdir "Logs"

ARG PROD=True
ENV AM_I_IN_A_DOCKER_CONTAINER ${PROD}
ENV TZ=Europe/Berlin

# EXPOSE 8000 TODO

CMD ["python3", "./main.py"]