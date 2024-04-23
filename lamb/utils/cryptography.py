from __future__ import annotations
from typing import AnyStr, Optional

import math
import hmac
import hashlib
import base64
import secrets


ALPHANUMERIC = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


def compare_digest(a: AnyStr, b: AnyStr):
    return hmac.compare_digest(a, b)


def generate_random_string(length: int, chars: str = ALPHANUMERIC):
    return ''.join(secrets.choice(chars) for i in range(length))


def generate_salt(entropy: int, chars: str = ALPHANUMERIC):
    char_count = math.ceil(entropy / math.log2(len(chars)))
    return generate_random_string(char_count, chars=ALPHANUMERIC)


def hash_passcode(passcode: bytes | str, salt: Optional[str] = None, algorithm: str = 'sha256',
                  iterations: int = 600000, salt_entropy: int = 128):
    if isinstance(passcode, str):
        passcode = passcode.encode('utf-8')
    if salt is None:
        salt = generate_salt(salt_entropy)

    passcode_hash = hashlib.pbkdf2_hmac(algorithm, passcode, salt.encode('utf-8'), iterations)
    decoded_hash = base64.b64encode(passcode_hash).decode('ascii').strip()

    return f'{algorithm}${iterations}${salt}${decoded_hash}', salt


def salted_hmac(value: bytes | str, salt: bytes | str, secret: bytes | str, algorithm='sha256'):
    if isinstance(value, str):
        value = value.encode('utf-8')
    else:
        value = bytes(value)
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    else:
        salt = bytes(salt)
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    else:
        secret = bytes(secret)

    return hmac.new(hashlib.new(algorithm, salt + secret).digest(), value, algorithm)


def base64_salted_hmac(value: bytes | str, salt: bytes | str,
                       secret: bytes | str, algorithm: str = 'sha256',
                       altchars: bytes | None = None):
    return base64.b64encode(salted_hmac(value, salt, secret, algorithm).digest(),
                            altchars=altchars).decode('ascii').strip()


def hex_salted_hmac(value: bytes | str, salt: bytes | str,
                    secret: bytes | str, algorithm: str = 'sha256'):
    return salted_hmac(value, salt, secret, algorithm).hexdigest()


def hex_sign_value(value: bytes | str, salt: bytes | str, secret: bytes | str,
                   separator: str = '--', algorithm: str = 'sha256'):
    if isinstance(value, bytes):
        str_value = value.decode()
    else:
        str_value = value

    return f'{str_value}{separator}{hex_salted_hmac(value, salt, secret, algorithm)}'


def base64_sign_value(value: bytes | str, salt: bytes | str, secret: bytes | str,
                      separator: str = '--', algorithm: str = 'sha256',
                      altchars: bytes | None = None):
    if isinstance(value, bytes):
        str_value = value.decode()
    else:
        str_value = value

    return f'{str_value}{separator}{base64_salted_hmac(value, salt, secret, algorithm, altchars)}'


def validate_hex_signed(value: str, salt: bytes | str, secret: bytes | str,
                    separator: str = '--', algorithm: str = 'sha256'):
    msg, *sig = value.split(separator, maxsplit=1)
    if not sig:
        return False
    if not compare_digest(value, hex_sign_value(msg, salt, secret, separator, algorithm)):
        return False
    else:
        return True


def validate_base64_signed(value: str, salt: bytes | str, secret: bytes | str,
                    separator: str = '--', algorithm: str = 'sha256',
                    altchars: bytes | None = None):
    msg, *sig = value.split(separator, maxsplit=1)
    if not sig:
        return False
    if not compare_digest(value, base64_sign_value(
        msg, salt, secret, separator, algorithm, altchars)):
        return False
    else:
        return True
