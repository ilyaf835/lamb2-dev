import pytest

from lamb.utils.tokenizer.exceptions import UnexpectedTokenError, EnclosingError


parser_values = [
    ('-m',
     [('m', [], [])]),
    ('-m test',
     [('m', ['test'], [])]),
    ('-m test --flag',
     [('m', ['test'], [('flag', [])])]),
    ('-m test --flag flag_value',
     [('m', ['test'], [('flag', ['flag_value'])])]),
    ('-m test --flag flag_value1 flag_value2',
     [('m', ['test'], [('flag', ['flag_value1', 'flag_value2'])])]),
    ('-m test --flag flag_value | -s',
     [('m', ['test'], [('flag', ['flag_value'])]), ('s', [], [])]),
    ('-m --flag1 flag1_value --flag2 flag2_value --flag3',
     [('m', [], [('flag1', ['flag1_value']), ('flag2', ['flag2_value']), ('flag3', [])])]),
]
parser_ids = (v[0] for v in parser_values)


@pytest.mark.parametrize(('s', 'result'), parser_values, ids=parser_ids)
def test_parser(parser, s, result):
    assert parser(s) == result


def test_parser_unexpected_token(parser):
    with pytest.raises(UnexpectedTokenError):
        assert parser('-m test -abc value')


def test_parser_enclosing_error(parser):
    with pytest.raises(EnclosingError):
        assert parser('-m "value')
