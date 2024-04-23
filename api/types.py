from __future__ import annotations
from typing import TYPE_CHECKING

from starlette.datastructures import State
from fastapi import FastAPI, WebSocket, Request

if TYPE_CHECKING:
    from service.main import Service


class AppState(State):
    service: Service


class App(FastAPI):
    state: AppState


class AppRequest(Request):
    app: App


class AppWebSocket(WebSocket):
    app: App
