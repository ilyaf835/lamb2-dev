FROM python:3.12-bookworm as build

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY docker/images/api.requirements.txt ./requirements.txt

RUN python -m pip install -U pip setuptools wheel \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=build app/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY runners/api_server.py .
COPY lamb ./lamb/
COPY bot ./bot/
COPY service ./service/
COPY api/ ./api/
