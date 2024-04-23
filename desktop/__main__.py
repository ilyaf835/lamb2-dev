from __future__ import annotations
from typing import TYPE_CHECKING

import signal
import datetime
from pathlib import Path
from pprint import pprint

from bot import Bot
from bot.mods.chat.exceptions import ChatApiError

from .extractor import connect_extractor_server
from .loader import ProfileLoader

if TYPE_CHECKING:
    from pathlib import PurePath


class SigtermException(SystemExit):
    pass


def sigterm_callback(*args):
    raise SigtermException(128 + signal.SIGTERM)


def save_cookie(profile_path: PurePath, cookie: str):
    with open(profile_path / 'cookies.txt', 'a') as f:
        f.write(f'{datetime.datetime.now()} | {cookie}\n')


def main(room_url: str, profile_name: str):
    signal.signal(signal.SIGTERM, sigterm_callback)

    profiles_path = Path(__file__).parent / 'profiles'
    profile_loader = ProfileLoader(profiles_path)
    profile_dict = profile_loader.load(profile_name)

    extractor_process, extractor_address = connect_extractor_server()
    bot = Bot(profile_dict, extractor_address)
    try:
        bot.login()
        bot.join_room(room_url)
        save_cookie(profiles_path / profile_name, bot.chat.session_cookie)
        bot.run()
        bot.logout()
    except ChatApiError as error:
        if error.response_json:
            pprint(error.response_json.get('error', 'Unknown error'))
        else:
            pprint(error.response.text)
    finally:
        bot.shutdown()
        profile_loader.save(profile_name, profile_dict)
        bot.extractor.shutdown()
        extractor_process.join()


if __name__ == '__main__':
    room_url = input('Room URL: ')
    profile_name = input('Profile name (leave empty to use default profile): ')
    if not profile_name:
        profile_name = 'default'
    main(room_url, profile_name)
