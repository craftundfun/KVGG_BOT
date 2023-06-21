FROM python:3.8.10

ADD main.py .
ADD src ./src
ADD parameters.yaml .
ADD NEVER.mp3 .

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python
RUN pip install requests
RUN apt-get install libffi-dev
# RUN apt-get install python-dev # help
RUN pip install mutagen
RUN apt-get install software-properties-common
RUN add-apt-repository ppa:mc3man/trusty-media
RUN apt-get update
RUN apt-get install ffmpeg
RUN apt-get install frei0r-plugins




CMD [ "python3", "./main.py" ]