from lamb.exceptions import ModException


class ParsingException(ModException):
    pass


class TokenParserException(ParsingException):
    pass


class UnexpectedTokenError(TokenParserException):
    msg = 'Unexpected token <{}>'


class EnclosingError(TokenParserException):
    msg = 'Quote has never been closed after <{}>'
