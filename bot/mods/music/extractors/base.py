from typing import Protocol, Any


class BaseExtractor(Protocol):
    def extract(self, url: str) -> Any: ...
