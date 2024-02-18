from types import SimpleNamespace

from sanic import Sanic, Request
from sanic_ext import Extend

from service.main import Service
from .config import Config, ExtentionsConfig


class AppContext(SimpleNamespace):
    service: Service


class RequestContext(SimpleNamespace):

    def __init__(self, **kwargs):
        self.session_id = ''
        self.flash_cookie = ''
        self.flash_message = ''
        self.flash_status = ''
        self.add_session_cookie = False
        self.add_flash_cookie = False
        self.remove_flash_cookie = False
        super().__init__(**kwargs)


class AppRequest(Request[Sanic, RequestContext]):

    @staticmethod
    def make_context():
        return RequestContext()


App = Sanic[Config, AppContext]


async def setup_service(app: App):
    service = app.ctx.service = Service()
    await service.init()


async def teardown_service(app: App):
    await app.ctx.service.close()


def create_app() -> App:
    app = Sanic('drrr_lamb', config=Config(), ctx=AppContext(), request_class=AppRequest)
    Extend(app, config=ExtentionsConfig())
    app.register_listener(setup_service, 'before_server_start')
    app.register_listener(teardown_service, 'after_server_stop')

    from .handlers import app
    from .middleware import app

    return app
