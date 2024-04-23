from __future__ import annotations

import re

from .exceptions import UnexpectedTokenError, EnclosingError


def create_parser(command_prefix: str):
    CPL  = len(command_prefix)
    FPL  = 2
    FSPL = 1

    ANY    = 'ANY'
    FLAGS  = 'FLAGS'
    CQUOTE = 'CLOSEQUOTE'

    SQUOTE  = r'\"'
    QUOTE   = r'"'
    DELIM   = r'|'
    COMMAND = re.compile(rf'{re.escape(command_prefix)}\w+')
    FLAGSEQ = re.compile(r'-\w+')
    FLAG    = re.compile(r'--\w+')

    def parse_args(args):
        values = buffer = []
        flags = []
        expect = ANY
        cursor = -1
        enclosed = 0
        for token in args:
            cursor += 1
            if expect == ANY:
                if token == DELIM:
                    return values, flags, args[cursor+1:]
                elif token[:2] == SQUOTE:
                    buffer.append(QUOTE + token[2:])
                elif token[0] == QUOTE:
                    if token == QUOTE:
                        enclosed = cursor
                        expect = CQUOTE
                    elif token[-1] == QUOTE:
                        if token[-2:] == SQUOTE:
                            args[cursor] = token[:-2] + QUOTE
                            enclosed = cursor
                            expect = CQUOTE
                        else:
                            buffer.append(token[1:-1])
                    else:
                        enclosed = cursor
                        expect = CQUOTE
                elif FLAG.fullmatch(token):
                    buffer = []
                    flags.append((token[FPL:], buffer))
                elif FLAGSEQ.fullmatch(token):
                    for flag in token[FSPL:]:
                        flags.append((flag, []))
                    expect = FLAGS
                else:
                    buffer.append(token)
            elif expect == FLAGS:
                if token == DELIM:
                    return values, flags, args[cursor+1:]
                if FLAG.fullmatch(token):
                    buffer = []
                    flags.append((token[FPL:], buffer))
                    expect = ANY
                elif FLAGSEQ.fullmatch(token):
                    for flag in token[FSPL:]:
                        flags.append((flag, []))
                else:
                    raise UnexpectedTokenError(format_args=(token,))
            elif expect == CQUOTE:
                if token[-1] == QUOTE:
                    if token[-2:] == SQUOTE:
                        args[cursor] = token[:-2] + QUOTE
                    else:
                        buffer.append(' '.join(args[enclosed:cursor+1])[1:-1].strip())
                        expect = ANY

        if expect is CQUOTE:
            raise EnclosingError(format_args=(args[enclosed],))

        return values, flags, args[cursor+1:]

    def parse(s: str) -> list[tuple[str, list[str], list[tuple[str, list[str]]]]]:
        output = []
        args = s.split()
        while args:
            command = args[0]
            if not COMMAND.fullmatch(command):
                break
            args = args[1:]
            if args:
                values, flags, args = parse_args(args)
                output.append((command[CPL:], values, flags))
            else:
                output.append((command[CPL:], [], []))

        return output

    return parse
