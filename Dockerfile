FROM tiangolo/uwsgi-nginx-flask:latest

RUN apt-get update
RUN apt-get install ngspice -y

COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt

WORKDIR /app/

COPY ./main.py main.py
