from typing import Any

import os
import datetime


class Config(dict):

    def __init__(self, *args, **kwargs):
        try:
            password = os.environ['POSTGRES_PASSWORD']
        except KeyError:
            with open(os.environ['POSTGRES_PASSWORD_FILE']) as f:
                password = f.read()

        self.POSTGRES_SETTINGS = {
            'host': os.environ['POSTGRES_HOST'],
            'user': os.environ['POSTGRES_USER'],
            'database': os.environ['POSTGRES_DB'],
            'password': password}
        self.RABBITMQ_SETTINGS = {
            'host': os.environ['RABBITMQ_HOST'],
            'prefetch_count': 100}
        self.REDIS_SETTINGS = {
            'host': os.environ['REDIS_HOST'],
            'protocol': 3,
            'decode_responses': True}
        self.SESSION_TTL = datetime.timedelta(minutes=1)

        super().__init__(*args, **kwargs)

    def __getattr__(self, attr: Any):
        return self[attr]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value
