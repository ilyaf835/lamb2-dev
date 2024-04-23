from __future__ import annotations
from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    'help': {
        'permit': 'user',
        'require_value': None,
        'aliases': ['h'],
        'flags': {
            'public': {
                'permit': 'moder',
                'aliases': ['p']}}
    },
    'leave': {
        'permit': 'admin',
        'aliases': ['l'],
        'signal': 'TERMINATE',
        'threaded': False
    },
    'give_host': {
        'permit': 'admin',
        'require_value': None,
        'aliases': ['gh']
    },
    'add_moder': {
        'permit': 'admin',
        'require_value': True,
        'aliases': ['am']
    },
    'remove_moder': {
        'permit': 'admin',
        'require_value': True,
        'aliases': ['rm']
    },
    'add_dj': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['ad']
    },
    'remove_dj': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['rd']
    },
    'add_to_whitelist': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['aw']
    },
    'remove_from_whitelist': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['rw']
    },
    'whitelist': {
        'permit': 'admin',
        'aliases': ['wl']
    },
    'whitelist_status': {
        'permit': 'moder',
        'aliases': ['wls']
    },
    'block_commands': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['bc'],
        'flags': {
            'reason': {
                'permit': 'moder',
                'require_value': True,
                'aliases': ['r']}}
    },
    'kick': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['k'],
        'flags': {
            'block_commands': {
                'permit': 'moder',
                'aliases': ['bc']}}
    },
    'ban': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['b'],
        'flags': {
            'reason': {
                'permit': 'moder',
                'require_value': True,
                'aliases': ['r']},
            'permanent': {
                'permit': 'moder',
                'aliases': ['p']}}
    },
    'unban': {
        'permit': 'moder',
        'require_value': True,
        'aliases': ['u'],
        'flags': {
            'full': {
                'permit': 'moder',
                'aliases': ['f']}}
    },
    'dj_mode': {
        'permit': 'moder',
        'aliases': ['dm', 'dj']
    },
    'queue': {
        'permit': 'user',
        'require_value': None,
        'aliases': ['q']
    },
    'search_results': {
        'permit': 'user',
        'aliases': ['sr']
    },
    'play': {
        'permit': 'user',
        'require_value': True,
        'aliases': ['m', 'music'],
        'flags': {
            'force': {
                'permit': 'dj',
                'aliases': ['f']},
            'index': {
                'permit': 'dj',
                'require_value': True,
                'aliases': ['i']},
            'extend_queue': {
                'permit': 'dj',
                'aliases': ['eq']},
            'extend_duration': {
                'permit': 'dj',
                'aliases': ['ed']}}
    },
    'search': {
        'permit': 'user',
        'require_value': True,
        'multiple_values': True,
        'batch_values': True,
        'aliases': ['s']
    },
    'choose': {
        'permit': 'user',
        'require_value': None,
        'aliases': ['c'],
        'flags': {
            'force': {
                'permit': 'dj',
                'aliases': ['f']},
            'index': {
                'permit': 'dj',
                'require_value': True,
                'aliases': ['i']},
            'extend_queue': {
                'permit': 'dj',
                'aliases': ['eq']},
            'extend_duration': {
                'permit': 'dj',
                'aliases': ['ed']}}
    },
    'repeat': {
        'permit': 'dj',
        'aliases': ['r']
    },
    'next': {
        'permit': 'dj',
        'aliases': ['n']
    },
    'remove_song': {
        'permit': 'dj',
        'require_value': None,
        'aliases': ['rs']
    },
    'clear_queue': {
        'permit': 'dj',
        'aliases': ['cq']
    },
    'pause': {
        'permit': 'dj',
        'aliases': ['p']
    },
    'unpause': {
        'permit': 'dj',
        'aliases': ['up']
    }
}
