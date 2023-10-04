FROM python:3.10.12

COPY requirements.txt .
COPY main.py .
COPY data ./data
COPY src ./src
COPY parameters.yaml .

RUN pip install -r requirements.txt
RUN python3 -m pip install -U "discord.py[voice]"
RUN apt-get install libffi-dev
RUN apt-get install -y ffmpeg

ENV PATH="/usr/bin/ffmpeg:${PATH}"

RUN mkdir "Logs"

ENV AM_I_IN_A_DOCKER_CONTAINER Yes
ENV TZ=Europe/Berlin

CMD ["python3", "./main.py"]