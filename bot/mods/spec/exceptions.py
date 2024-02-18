from lamb.utils.tokenizer.exceptions import ParsingException


class CommandParserException(ParsingException):
    pass


class NoSuchCommandError(CommandParserException):
    msg = 'No such command as <{}>'


class NoSuchFlagError(CommandParserException):
    msg = 'No such flag as <{}>'


class ValueMissingError(CommandParserException):
    msg = '<{}> requires atleast one value'


class ValueNotAllowedError(CommandParserException):
    msg = '<{}> does not allow values'


class MultipleValuesError(CommandParserException):
    msg = '<{}> does not allow multiple values'


class AccessRightsError(CommandParserException):
    msg = 'Not enough rights to use <{}>'
