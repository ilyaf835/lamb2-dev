from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class context_descriptor:

    def __init__(self, context_func: Callable):
        self.context_func = context_func

    def __get__(self, obj, objtype=None):
        def context_proxy(func: Callable):
            def func_proxy(class_inst, *meth_args, **meth_kwargs):
                def func_wrapper(*args, **kwargs):
                    return func(class_inst, *args, **kwargs)
                return self.context_func(class_inst.context, func_wrapper, *meth_args, **meth_kwargs)
            return func_proxy
        return context_proxy


class States:

    flags: dict[str, bool]

    def __init__(self):
        self.flags = {}

    def __getattr__(self, name: str):
        return self.get(name)

    def __getitem__(self, name: str):
        return self.get(name)

    def get(self, name: str):
        if name in self.flags:
            status = self.flags[name]
        else:
            status = self.flags[name] = False

        return status

    def set(self, name: str, value: bool):
        self.flags[name] = value

    def switch(self, name: str):
        if name in self.flags:
            status = self.flags[name] = self.flags[name] ^ True
        else:
            status = self.flags[name] = True

        return status
