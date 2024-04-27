FROM python:3.11-slim

COPY requirements.txt .
COPY main.py .
COPY data ./data
COPY src ./src
COPY parameters.env .
COPY Web ./Web

RUN apt-get update && apt-get install -y ffmpeg
# RUN apt-get install -y curl
RUN pip install -r requirements.txt
RUN apt-get install libffi-dev
RUN mkdir "Logs"

ENV PATH="/usr/bin/ffmpeg:${PATH}"
ENV TZ=Europe/Berlin

EXPOSE 8000

# HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=0 \
# 	 CMD curl --fail --insecure https://localhost:8000/health || exit 1

CMD ["python3", "./main.py"]