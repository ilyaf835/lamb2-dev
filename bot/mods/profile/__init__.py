from __future__ import annotations
from typing import Type, Any, Optional

import time
import copy
from attrs import define

from ..spec import CommandSpec, FlagSpec, process_spec

from .groups import BaseGroup, GroupsManager
from .exceptions import TripcodeRequirementError


def process_settings(src: dict[str, Any],
                     default_settings: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    default_settings_copy = copy.deepcopy(default_settings)
    settings = {}
    for key, params in default_settings_copy.items():
        if key not in src:
            settings[key] = params
        else:
            settings[key] = {}
            for param, value in params.items():
                try:
                    settings[key][param] = src[key][param]
                except KeyError:
                    settings[key][param] = value

    return settings


@define
class DefaultGroup(BaseGroup):

    def __attrs_post_init__(self):
        self.info.setdefault('require_tripcode', True)

    def add_user(self, name: str, tripcode: Optional[str] = None):
        if self.info['require_tripcode'] and not tripcode:
            raise TripcodeRequirementError(format_args=(name, self.name))
        if name not in self.users:
            self.users[name] = [tripcode] if tripcode else []
        elif tripcode and tripcode not in self.users[name]:
            self.users[name].append(tripcode)

    def remove_user(self, name: str):
        return self.users.pop(name, None)


class Profile:

    command_spec = CommandSpec
    flag_spec = FlagSpec

    default_settings: dict[str, dict[str, str]]
    default_grouptypes: dict[str, Type[BaseGroup]]

    blacklist: dict[str, Any]
    whitelist: dict[str, Any]
    translations: dict[str, Any]
    permits: dict[str, int]

    def __init__(self):
        self.default_grouptypes = {'default': DefaultGroup}
        self.default_settings = {
            'general': {
                'language': 'EN',
                'command_prefix': '-'},
            'admin': {
                'name': '',
                'tripcode': ''},
            'bot': {
                'name': '',
                'passcode': '',
                'icon': ''}}

    def init(self, d: dict[str, Any]):
        self.blacklist = d['blacklist']
        self.whitelist = d['whitelist']
        self.translations = d['translations']
        self.permits = d['permits']

        self.groups_manager = GroupsManager(
            d['groups'], self.permits, self.default_grouptypes)
        self.commands = process_spec(
            d['commands'], self.command_spec, self.flag_spec)
        self.settings = process_settings(d['settings'], self.default_settings)

        self.command_prefix = self.settings['general']['command_prefix']
        self.language = self.settings['general']['language']
        self.admin = self.settings['admin']
        self.bot = self.settings['bot']

    def is_bot(self, name: str, tripcode: str):
        return name == self.bot['name'] and tripcode == self.bot['tripcode']

    def is_admin(self, name: str, tripcode: str):
        return name == self.admin['name'] and tripcode == self.admin['tripcode']

    def is_banned(self, name: str):
        return name in self.blacklist

    def ban_status(self, name: str) -> Optional[str]:
        ban = self.blacklist.get(name)
        if ban:
            return ban['status']
        return None

    def ban_reason(self, name: str) -> Optional[str]:
        ban = self.blacklist.get(name)
        if ban:
            return ban['reason']
        return None

    def add_to_whitelist(self, name: str):
        self.whitelist[name] = time.time()

    def remove_from_whitelist(self, name: str):
        self.whitelist.pop(name, None)

    def add_to_blacklist(self, name: str, reason: Optional[str] = None, permanent: bool = False):
        if permanent:
            self.blacklist[name] = {'status': 'permanent', 'reason': reason}
        else:
            self.blacklist[name] = {'status': 'commands', 'reason': reason}

    def remove_from_blacklist(self, name: str, full: bool = False):
        if name in self.blacklist:
            if full:
                self.blacklist.pop(name)
            else:
                self.blacklist[name]['status'] = 'commands'

    def user_groups(self, name: str, tripcode: str):
        for group in self.groups_manager.groups.values():
            if name in group.users:
                user_tripcodes = group.users[name]
                if not user_tripcodes or tripcode in user_tripcodes:
                    yield group

    def user_permit(self, name: str, tripcode: str):
        if self.is_admin(name, tripcode):
            permit = self.permits['admin']
        else:
            permit = self.permits['user']
            for group in self.user_groups(name, tripcode):
                group_permit = self.permits[group.permit]
                if group_permit < permit:
                    permit = group_permit

        return permit

    def check_permit(self, group: str, name: str, tripcode: str):
        return self.user_permit(name, tripcode) <= self.permits[self.groups_manager.get_group(group).permit]
