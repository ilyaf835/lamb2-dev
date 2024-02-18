from ..exceptions import MusicException


class ExtractorException(MusicException):
    pass


class InfoExtractionError(ExtractorException):
    msg = 'Extractor failed to extract video info'


class InvalidUrlError(ExtractorException):
    msg = 'Invalid url was provided'
