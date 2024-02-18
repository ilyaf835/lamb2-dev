import pydantic
from sanic import Sanic, SanicException, redirect, empty

from .app import App, AppRequest
from .decorators import render_error
from .forms import IndexForm
from .errors import translate_error_code


app: App = Sanic.get_app('drrr_lamb')


@app.get('/health')
async def health_get(request: AppRequest):
    return empty()


@app.get('/')
@app.ext.template('index.html')
async def index_get(request: AppRequest):
    if await app.ctx.service.redis.check_session_exists(request.ctx.session_id):
        return redirect('/bot')
    return {'flash_message': request.ctx.flash_message}


@app.post('/')
@render_error('/')
async def index_post(request: AppRequest):
    session_id = request.ctx.session_id
    if await app.ctx.service.redis.check_session_exists(session_id):
        return redirect('/bot', status=303)

    if not request.form:
        raise SanicException('Empty form', status_code=403)
    try:
        form = IndexForm(**request.form).model_dump()
    except pydantic.ValidationError:
        raise SanicException('Invalid form', status_code=403)

    error = await app.ctx.service.create_bot(session_id, **form)
    if error:
        message, status_code = translate_error_code(error)
        raise SanicException(message=message, status_code=status_code)

    return redirect('/bot', status=303)


@app.get('/bot')
@app.ext.template('bot.html')
async def bot_get(request: AppRequest):
    session = await app.ctx.service.redis.get_session_json(request.ctx.session_id)
    if not session:
        return redirect('/')
    return {'session': session}


@app.post('/disconnect')
@render_error('/')
async def disconnect_post(request: AppRequest):
    session_id = request.ctx.session_id
    if not await app.ctx.service.redis.check_session_exists(session_id):
        return redirect('/', status=303)

    error = await app.ctx.service.delete_bot(session_id)
    if error:
        message, status_code = translate_error_code(error)
        raise SanicException(message=message, status_code=status_code)

    return redirect('/', status=303)
