from service.exceptions import LambServiceException


class ChatProviderException(LambServiceException):
    pass


class ChatRequestError(ChatProviderException):

    extra = {'status_code': 403}


class ChatApiNotResponding(ChatProviderException):

    extra = {'status_code': 503,
             'message': 'Chat API is not responding'}
