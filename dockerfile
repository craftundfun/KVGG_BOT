FROM python:3.8.10

ADD main.py .

RUN python3 -m pip install -U "discord.py[voice]"
RUN pip install mysql-connector-python
RUN pip install SQLAlchemy
RUN pip install requests


CMD [ "python3", "./main.py" ]