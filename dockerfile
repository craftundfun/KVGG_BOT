FROM python:3.8.10

ADD main.py .
ADD src ./src
ADD parameters.yaml .

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python
RUN pip install requests
RUN apt-get install libffi-dev
RUN apt-get install python-dev # help
RUN pip install mutagen




CMD [ "python3", "./main.py" ]