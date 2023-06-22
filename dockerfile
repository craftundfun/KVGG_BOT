FROM python:3.8.10

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python
RUN pip install requests
RUN apt-get install libffi-dev
RUN pip install mutagen


ADD main.py .
ADD src ./src
ADD parameters.yaml .
ADD f.mp3 .

CMD ["python3", "./main.py"]