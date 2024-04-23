from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from service.exceptions import LambServiceException
    from .types import AppRequest


async def service_exception_handler(request: AppRequest, exc: LambServiceException):
    status_code = exc.extra['status_code']
    return JSONResponse(
        content={'status': status_code, 'message': exc.extra['message']},
        status_code=status_code)
