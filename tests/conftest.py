import pytest

from lamb.utils.tokenizer import create_parser


@pytest.fixture(scope='session')
def parser():
    return create_parser(command_prefix='-')
