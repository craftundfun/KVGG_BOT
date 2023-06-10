FROM python:3.8.10

ADD main.py .

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python

CMD [ "python3", "./main.py" ]