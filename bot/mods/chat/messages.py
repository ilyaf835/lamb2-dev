from __future__ import annotations
from typing import TYPE_CHECKING, Any, Literal, Union

if TYPE_CHECKING:
    from . import User


AnyMessage = Union['JoinMessage', 'TextMessage', 'MusicMessage']


class BaseMessage:

    type: str
    time: float

    def __init__(self, message_json: dict[str, Any], *args, **kwargs):
        self.json = message_json
        self.time = message_json['time']


class JoinMessage(BaseMessage):

    type: Literal['join'] = 'join'

    def __init__(self, message_json: dict[str, Any], users: dict[str, User]):
        super().__init__(message_json)

        self.user = users[message_json['user']['name']]


class TextMessage(BaseMessage):

    type: Literal['message'] = 'message'
    text: str
    private: bool

    def __init__(self, message_json: dict[str, Any], users: dict[str, User]):
        super().__init__(message_json)

        self.user = users[message_json['from']['name']]
        self.text = message_json['message']
        self.private = message_json.get('secret', False)


class MusicMessage(BaseMessage):

    type: Literal['music'] = 'music'

    def __init__(self, message_json: dict[str, Any], users: dict[str, User]):
        super().__init__(message_json)

        self.user = users[message_json['from']['name']]
