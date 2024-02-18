from __future__ import annotations
from typing import Any, Optional


class LambServiceException(Exception):

    extra: dict[str, Any] = {}

    def __init__(self, message: Optional[str] = None,
                 extra: Optional[dict[str, Any]] = None, **kwargs):
        self.extra = {**self.extra, **(extra or {}), **kwargs}
        if message is None:
            message = self.extra.get('message')
        else:
            self.extra['message'] = message

        if message is not None:
            super().__init__(message)


class ValidationError(LambServiceException):

    extra = {'status_code': 403}
