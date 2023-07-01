FROM python:3.8.10

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python
RUN pip install requests
RUN apt-get install libffi-dev
RUN pip install mutagen
RUN pip install nest-asyncio


COPY main.py .
COPY src ./src
COPY parameters.yaml .

RUN mkdir "Logs"

ENV AM_I_IN_A_DOCKER_CONTAINER Yes
ENV TZ=Europe/Berlin

CMD ["python3", "./main.py"]