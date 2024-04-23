from contextlib import asynccontextmanager

from service.main import Service
from service.exceptions import LambServiceException

from fastapi import FastAPI

from .exceptions import service_exception_handler
from .handlers import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = app.state.service = Service()
    await service.init()
    yield
    await service.close()


def create_app():
    app = FastAPI(title='Bot', lifespan=lifespan)
    app.exception_handler(LambServiceException)(service_exception_handler)
    app.include_router(router)

    return app
