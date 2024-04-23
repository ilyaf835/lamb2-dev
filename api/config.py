from typing import Any

import os


class Config(dict):

    def __init__(self, *args, **kwargs):
        self.SECRET = os.environ['SECRET']

        super().__init__(*args, **kwargs)

    def __getattr__(self, attr: Any):
        return self[attr]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


config = Config()
