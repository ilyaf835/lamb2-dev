from __future__ import annotations
from typing import Any

import json

from bot.mods.spec import process_spec
from bot.mods.profile import Profile as DefaultProfile
from bot.mods.profile.groups import GroupsManager

from .commands import COMMANDS
from .translations import TRANSLATIONS


class Profile(DefaultProfile):

    def init(self, session: dict[str, Any]):
        self.admin = session['user']
        self.bot = session['bot']
        self.command_prefix = self.bot['command_prefix']
        self.language = self.bot['language']
        self.blacklist = self.bot['blacklist'] = json.loads(self.bot['blacklist'])
        self.whitelist = self.bot['whitelist'] = json.loads(self.bot['whitelist'])
        self.settings = {
            'general': {
                'language': self.language,
                'command_prefix': self.command_prefix},
            'admin': self.admin,
            'bot': self.bot
        }
        self.permits = {"admin": 0, "moder": 1, "dj": 50, "user": 100}
        groups = self.bot['groups'] = json.loads(self.bot['groups'])
        default_groups = {
            "moder": {
                "name": "moder",
                "permit": "moder",
                "type": "default",
                "info": {"require_tripcode": True},
                "users": {}},
            "dj": {
                "name": "dj",
                "permit": "dj",
                "type": "default",
                "info": {"require_tripcode": False},
                "users": {}}
        }
        for k, v in default_groups.items():
            groups.setdefault(k, v)
        self.groups_manager = GroupsManager(groups, self.permits, self.default_grouptypes)
        self.commands = process_spec(COMMANDS, self.command_spec, self.flag_spec)
        self.translations = TRANSLATIONS
