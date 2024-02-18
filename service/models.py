from __future__ import annotations
from typing import Any, TypedDict


class User(TypedDict):
    id: str
    name: str
    tripcode: str
    passcode: str


class Bot(TypedDict):
    name: str
    tripcode: str
    passcode: str
    icon: str
    language: str
    command_prefix: str
    whitelist: dict[str, Any]
    blacklist: dict[str, Any]
    groups: dict[str, Any]
    user_id: int
