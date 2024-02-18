from __future__ import annotations
from typing import TYPE_CHECKING, Callable
from functools import wraps

from sanic import SanicException, redirect

from service.exceptions import LambServiceException

if TYPE_CHECKING:
    from .app import AppRequest


def render_error(redirect_path: str):
    def decorator(f: Callable):
        @wraps(f)
        async def decorated_function(request: AppRequest, *args, **kwargs):
            try:
                return await f(request, *args, **kwargs)
            except LambServiceException as exc:
                status = exc.extra['status_code']
                if status == 500:
                    raise SanicException(**exc.extra)
                request.ctx.flash_cookie = f'{exc.extra["message"]}<status>{status}'
                request.ctx.add_flash_cookie = True
                return redirect(redirect_path, status=303)
            except SanicException as exc:
                status = exc.status_code
                message, *args = exc.args or ('Unexpected server error',)
                if status == 500:
                    raise
                request.ctx.flash_cookie = f'{message}<status>{status}'
                request.ctx.add_flash_cookie = True
                return redirect(redirect_path, status=303)

        return decorated_function

    return decorator
