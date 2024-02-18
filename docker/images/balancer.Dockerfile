FROM python:3.12-bookworm as build

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY docker/images/balancer.requirements.txt ./requirements.txt

#RUN python -m venv --copies .venv \
#    && bash -c "source .venv/bin/activate \
#       && python -m pip install -U pip setuptools wheel \
#       && pip install --no-cache-dir -r requirements.txt"

RUN python -m pip install -U pip setuptools wheel \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
WORKDIR /app

#COPY --from=build app/.venv/ .venv/
COPY --from=build app/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY lamb ./lamb/
COPY bot ./bot/
COPY service ./service/
COPY runners/balancer.py ./

CMD ["bash"]
