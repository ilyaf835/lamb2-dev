from typing import Protocol


class BaseExtractor(Protocol):
    def extract(self, url: str): ...
