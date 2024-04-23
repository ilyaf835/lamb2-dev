from __future__ import annotations
from typing import TYPE_CHECKING, Any

import json
import configparser
from pathlib import Path

if TYPE_CHECKING:
    from os import PathLike


def load_json(path: PathLike):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: PathLike, data: Any):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=4))


def load_ini(path: PathLike):
    with open(path, 'r', encoding='utf-8') as f:
        parser = configparser.ConfigParser()
        parser.read_file(f)
        return parser._sections  # type: ignore


class ProfileLoader:

    scheme: dict[str, Any]

    def __init__(self, profiles_path: PathLike):
        self.profiles_path = Path(profiles_path)
        self.scheme = {
            'settings': {
                'file_path': 'settings.ini',
                'load_func': load_ini},
            'permits': {
                'file_path': 'permits.json',
                'load_func': load_json},
            'commands': {
                'file_path': 'commands.json',
                'load_func': load_json},
            'whitelist': {
                'file_path': 'whitelist.json',
                'load_func': load_json,
                'save_func': save_json},
            'blacklist': {
                'file_path': 'blacklist.json',
                'load_func': load_json,
                'save_func': save_json},
            'groups': {
                'file_path': 'groups.json',
                'load_func': load_json,
                'save_func': save_json},
            'translations': {
                'file_path': 'translations.json',
                'load_func': load_json}}

    def load(self, profile_name: str):
        profile_dict = {}
        path = self.profiles_path / profile_name
        for key, params in self.scheme.items():
            file_path = path / params['file_path']
            load_func = params['load_func']
            load_args = params.get('load_args', ())
            load_kwargs = params.get('load_kwargs', {})
            profile_dict[key] = load_func(file_path, *load_args, **load_kwargs)

        return profile_dict

    def save(self, profile_name: str, profile_dict: dict[str, Any]):
        path = self.profiles_path / profile_name
        for key, params in self.scheme.items():
            file_path = path / params['file_path']
            save_func = params.get('save_func')
            if save_func:
                save_args = params.get('save_args', ())
                save_kwargs = params.get('save_kwargs', {})
                save_func(file_path, profile_dict[key], *save_args, **save_kwargs)
