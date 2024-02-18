from lamb.exceptions import ModException


class MusicException(ModException):
    pass


class PlayerException(MusicException):
    pass


class EmptyQueueError(PlayerException):
    msg = 'Queue is empty'


class QueueIndexError(PlayerException):
    msg = 'Index out of range'


class QueueLimitError(PlayerException):
    msg = 'Queue exceeds limit of {} tracks'


class TrackDurationError(PlayerException):
    msg = 'Track duration exceeds {} seconds limit'
