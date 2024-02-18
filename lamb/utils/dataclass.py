import sys


MISSING = object()
MISSING_KW = object()

TEMPLATE = """
def __create__({local}):
    def {name}({args}, {kwargs}):
        {body}
    return {name}
"""


def create_func(name, args, kwargs, body, globs, local):
    if isinstance(body, str):
        body = body.splitlines()

    formatted = TEMPLATE.format(
        name=name,
        local=', '.join(local),
        args=', '.join(args),
        kwargs=', '.join(f'{key}={value}' for key, value in kwargs.items()),
        body='\n        '.join(body))

    namespace = {}
    exec(formatted, globs, namespace)

    return namespace['__create__'](**local)


def create_init(parent_fields, fields, class_name, globs):
    local = {'MISSING_KW': MISSING_KW}
    body = [f'super({class_name}, self).__init__({", ".join(parent_fields)})']
    args = ['self']
    kwargs = {}

    def chain_fields():
        for key, field in parent_fields.items():
            yield key, field, False
        for key, field in fields.items():
            yield key, field, True

    def append_signature():
        if field.value is not MISSING:
            local[f'{argname}_value'] = field.value
            kwargs[argname] = f'{argname}_value'
        elif field.factory is not MISSING:
            local[f'{key}_factory'] = field.factory
            local[f'{key}_factory_args'] = field.factory_args
            local[f'{key}_factory_kw'] = field.factory_kw
            if argname not in args:
                kwargs[argname] = 'MISSING_KW'
        elif argname not in args:
            args.append(argname)

    def append_code():
        if field.factory is MISSING:
            fieldname = argname
        else:
            fieldname = f'{key}_{argname}'
            body.extend((
                f'{fieldname} = {argname}',
                f'if {argname} is MISSING_KW:',
                f'    {fieldname} = {key}_factory(*{key}_factory_args, **{key}_factory_kw)'))
        if field.wrapper:
            local[f'{key}_wrapper'] = field.wrapper
            local[f'{key}_wrapper_args'] = field.wrapper_args
            local[f'{key}_wrapper_kw'] = field.wrapper_kw
            body.append(f'self.{key} = {key}_wrapper({fieldname}, *{key}_wrapper_args, **{key}_wrapper_kw)')
        else:
            body.append(f'self.{key} = {fieldname}')

    for key, field, current in chain_fields():
        argname = key if field.argname is None else field.argname
        append_signature()
        if current:
            append_code()

    body.extend((f'if self.__class__ is {class_name}:',
                 '    self.__postinit__()'))

    return create_func('__init__', args, kwargs, body, globs, local)


def metaclass_new(mcs, name, bases, attrs, **kwargs):
    slots = attrs.setdefault('__slots__', [])
    if not isinstance(slots, list):
        if isinstance(slots, str):
            attrs['__slots__'] = [slots]
        else:
            attrs['__slots__'] = list(slots)

    parent_fields = {}
    fields = {}
    for base in bases:
        if issubclass(base, Dataclass):
            parent_fields = base.__fields__
            break
    for key, value in attrs.copy().items():
        if isinstance(value, Field):
            fields[key] = attrs.pop(key)
            attrs['__slots__'].append(key)

    attrs['__fields__'] = {**parent_fields, **fields}
    if bases:
        module = attrs['__module__']
        if module in sys.modules:
            attrs['__init__'] = create_init(parent_fields, fields, name, sys.modules[module].__dict__)
        else:
            attrs['__init__'] = create_init(parent_fields, fields, name, {})

    return type.__new__(mcs, name, bases, attrs, **kwargs)


class Field:

    __slots__ = ('value', 'factory', 'factory_args', 'factory_kw',
                 'wrapper', 'wrapper_args', 'wrapper_kw', 'argname')

    def __init__(self, value=MISSING, factory=MISSING, factory_args=(), factory_kw=None,
                 wrapper=None, wrapper_args=(), wrapper_kw=None, argname=None):
        self.value = value
        self.factory = factory
        self.factory_args = factory_args
        if factory_kw is None:
            factory_kw = {}
        self.factory_kw = factory_kw
        self.wrapper = wrapper
        self.wrapper_args = wrapper_args
        if wrapper_kw is None:
            wrapper_kw = {}
        self.wrapper_kw = wrapper_kw
        self.argname = argname


def field(value=MISSING, factory=MISSING, factory_args=(), factory_kw=None,
          wrapper=None, wrapper_args=(), wrapper_kw=None, argname=None):
    return Field(value, factory, factory_args, factory_kw,
                 wrapper, wrapper_args, wrapper_kw, argname)


class DataMeta(type):

    def __new__(mcs, name, bases, attrs, **kwargs):
        return metaclass_new(mcs, name, bases, attrs, **kwargs)


class Dataclass(metaclass=DataMeta):

    __slots__ = []
    __fields__ = {}

    def __init__(self, *args, **kwargs):
        pass

    def __postinit__(self, *args, **kwargs):
        pass

    def __iter__(self):
        for key in self.__fields__:
            yield key, getattr(self, key)
