from __future__ import annotations
from typing_extensions import Annotated

import asyncio

from lamb.utils.cryptography import (
    generate_random_string,
    validate_base64_signed,
    base64_sign_value
)

from service.exceptions import ValidationError

from fastapi import APIRouter, Response, Depends

from .types import AppRequest, AppWebSocket
from .models import BotInfo
from .config import config
from .errors import translate_error_code


ALTCHARS = b'-_'


router = APIRouter()


async def validate_session_id(session_id: str):
    if not validate_base64_signed(session_id, 'session', config.SECRET, altchars=ALTCHARS):
        raise ValidationError('Invalid session id')
    return session_id


@router.get('/health')
async def health():
    return {'message': 'OK'}


@router.get('/')
async def index_get():
    return {'message': 'OK'}


@router.get('/bot')
async def bot_get(request: AppRequest, response: Response,
                  session_id: Annotated[str, Depends(validate_session_id)]):
    service = request.app.state.service
    session_list = await service.redis.get_session_json(session_id, '$.bot')
    if session_list:
        session = session_list[0]
        message, response.status_code = 'Bot is running', 200
    else:
        session = {}
        message, response.status_code = 'No bot', 303

    return {'status': response.status_code, 'message': message, 'session': session}


@router.post('/bot')
async def bot_post(request: AppRequest, response: Response, info: BotInfo):
    session_id = base64_sign_value(
        generate_random_string(22), 'session', config.SECRET, altchars=ALTCHARS)

    service = request.app.state.service
    error = await service.create_bot(session_id, **info.model_dump())
    if error:
        message, response.status_code = translate_error_code(error)
    else:
        message, response.status_code = 'Bot created', 200

    return {'status': response.status_code,
            'message': message,
            'session_id': session_id if not error else None}


@router.delete('/bot')
async def bot_delete(request: AppRequest, response: Response,
                     session_id: Annotated[str, Depends(validate_session_id)]):
    service = request.app.state.service
    if not await service.redis.check_session_exists(session_id):
        message, response.status_code = 'Bot already deleted', 303
    else:
        error = await service.delete_bot(session_id)
        if error:
            message, response.status_code = translate_error_code(error)
        else:
            message, response.status_code  = 'Bot successfully disconnected', 200

    return {'status': response.status_code, 'message': message}


@router.websocket('/bot/ws')
async def bot_ws_session(websocket: AppWebSocket,
                         session_id: Annotated[str, Depends(validate_session_id)]):
    service = websocket.app.state.service
    await websocket.accept()
    while True:
        await asyncio.sleep(5)
        session_list = await service.redis.get_session_json(session_id, '$.bot')
        if not session_list:
            return await websocket.close(code=1000, reason='Bot disconnected')
        await websocket.send_json(session_list[0])
