from __future__ import annotations

from service.errors import Errors


ERRORS_MAP: dict[str, tuple[str, int]] = {
    Errors.ALREADY_CREATED: ('Bot already created', 403),
    Errors.NO_BOT: ('Bot already deleted', 303),
    Errors.NO_BALANCERS: ('Service is currently unavailable', 503),
    Errors.NO_WORKERS: ('Service is currently unavailable', 503),
    Errors.PUBLISH_ERROR: ('Service is currently unavailable', 503)
}


def translate_error_code(error: str, default_code=503):
    return ERRORS_MAP.get(error, (error, default_code))
