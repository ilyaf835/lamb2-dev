from typing import Any

import os
import datetime


class Config(dict):

    def __init__(self, *args, **kwargs):
        password = os.getenv('POSTGRES_PASSWORD')
        if not password:
            path = os.getenv('POSTGRES_PASSWORD_FILE')
            if path:
                with open(path) as f:
                    password = f.read()

        self.POSTGRES_SETTINGS = {
            'host': os.getenv('POSTGRES_HOST'),
            'user': os.getenv('POSTGRES_USER'),
            'database': os.getenv('POSTGRES_DB'),
            'password': password}
        self.RABBITMQ_SETTINGS = {
            'host': os.getenv('RABBITMQ_HOST'),
            'prefetch_count': 100}
        self.REDIS_SETTINGS = {
            'host': os.getenv('REDIS_HOST'),
            'protocol': 3,
            'decode_responses': True}
        self.SESSION_TTL = datetime.timedelta(minutes=5)

        super().__init__(*args, **kwargs)

    def __getattr__(self, attr: Any):
        return self[attr]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value
