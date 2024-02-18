from lamb.exceptions import ModException


class ChatException(Exception):
    pass


class ChatHttpError(ChatException):
    pass


class ChatApiError(ChatException):

    def __init__(self, msg, response, *args, response_json=None, **kwargs):
        super().__init__(msg)
        self.msg = msg
        self.response = response
        self.response_json = response_json


class ChatNotConnectedError(ChatException):
    pass


class ChatAlreadyConnectedError(ChatException):
    pass


class RoomNotConnectedError(ChatException):
    pass


class RoomAlreadyConnectedError(ChatException):
    pass


class InvalidRoomUrlError(ChatException):
    pass


class ChatModException(ModException):
    pass


class UserNotFoundError(ChatModException):
    msg = 'User <{}> is not in the room'
