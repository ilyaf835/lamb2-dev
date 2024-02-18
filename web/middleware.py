from __future__ import annotations
from typing import TYPE_CHECKING

from sanic import Sanic

from service.utils.crypto import validate_signed, hex_sign_value, generate_random_string

from .app import App, AppRequest

if TYPE_CHECKING:
    from sanic import HTTPResponse


app: App = Sanic.get_app('drrr_lamb')


@app.on_request
async def check_flash_cookie(request: AppRequest):
    flash_cookie = request.cookies.get('flash')
    if not flash_cookie:
        return
    if validate_signed(flash_cookie, 'flash', app.config.SECRET):
        message, *sig = flash_cookie.split('--', maxsplit=1)
        request.ctx.flash_message, request.ctx.flash_status = message.split('<status>')
        request.ctx.remove_flash_cookie = True


@app.on_request
async def check_session_cookie(request: AppRequest):
    session_cookie = request.cookies.get('session_id')
    if session_cookie and validate_signed(session_cookie, 'session', app.config.SECRET):
        request.ctx.session_id = session_cookie
    else:
        request.ctx.session_id = hex_sign_value(generate_random_string(32), 'session', app.config.SECRET)
        request.ctx.add_session_cookie = True


@app.on_response
async def set_flash_cookie(request: AppRequest, response: HTTPResponse):
    if request.ctx.add_flash_cookie:
        flash_cookie = hex_sign_value(request.ctx.flash_cookie, 'flash', app.config.SECRET)
        response.add_cookie('flash', flash_cookie, secure=False, httponly=True, samesite='Strict', max_age=30)
    elif request.ctx.remove_flash_cookie:
        response.add_cookie('flash', '', secure=False, httponly=True, max_age=0)


@app.on_response
async def set_session_cookie(request: AppRequest, response):
    if request.ctx.add_session_cookie:
        response.add_cookie('session_id', request.ctx.session_id, secure=False, httponly=True, samesite='Strict')
