FROM python:3.12-rc-alpine3.18

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .