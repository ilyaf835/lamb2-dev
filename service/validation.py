from types import SimpleNamespace

from .providers.chat import ROOM_URL_PATTERN, ROOM_URL_BASE
from .exceptions import ValidationError


def validate_user_name(full_user_name: str):
    if not full_user_name:
        raise ValidationError('Empty user name')
    name, *passcode = full_user_name.split('#', maxsplit=1)
    if not name:
        raise ValidationError('Empty user name')
    if len(name) > 20:
        raise ValidationError('User name must be less than 20 characters')
    if not passcode:
        raise ValidationError('User must have passcode')
    passcode = passcode[0]
    if not passcode.startswith('#'):
        raise ValidationError('Passcode must start with "#"')
    if len(passcode) < 6:
        raise ValidationError('Passcode must be more than 6 characters')

    return name, passcode


def validate_bot_name(full_bot_name: str):
    if not full_bot_name:
        raise ValidationError('Empty bot name')
    name, *passcode = full_bot_name.split('#', maxsplit=1)
    if not name:
        raise ValidationError('Empty bot name')
    if len(name) > 20:
        raise ValidationError('Bot name must be less than 20 characters')
    if not passcode:
        raise ValidationError('Bot must have passcode')
    passcode = passcode[0]
    if not passcode.startswith('#'):
        raise ValidationError('Passcode must start with "#"')
    if len(passcode) < 6:
        raise ValidationError('Passcode must be more than 6 characters')

    return name, passcode


def validate_room_url(room_url: str):
    if not room_url:
        raise ValidationError('Empty room id/url')
    match = ROOM_URL_PATTERN.fullmatch(room_url) or ROOM_URL_PATTERN.fullmatch(ROOM_URL_BASE + room_url)
    if not match:
        raise ValidationError('Invalid room id/url')

    return match.group('id')


def validate_create_command(user_name: str, bot_name: str, room_url: str, hidden: bool = False):
    c = SimpleNamespace()

    c.user_name, c.user_passcode = validate_user_name(user_name)
    c.bot_name, c.bot_passcode = validate_bot_name(bot_name)
    c.full_user_name = user_name
    c.full_bot_name = bot_name

    if c.user_name == c.bot_name:
        raise ValidationError('User and bot nicknames must be different')

    c.room_id = validate_room_url(room_url)
    c.room_url = room_url
    c.hidden = hidden

    return c
