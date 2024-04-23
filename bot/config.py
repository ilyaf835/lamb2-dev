from typing import Any


class Config(dict):

    def __init__(self, *args, **kwargs):
        self.HELP_MESSAGE = (
            '-h to see this message\n'
            '-m <youtube link> to queue song\n'
            '-s <text> to search for song\n'
            '-c <№> to choose song')

        self.COMMANDS_THREADS = 2
        self.HOOKS_THREADS = 1
        self.PLAYER_THREADS = 1
        self.MESSAGES_THREADS = 1
        self.SEND_DELAY = 1

        self.DURATION_LIMIT = 12 * 60
        self.QUEUE_LIMIT = 20

        super().__init__(*args, **kwargs)

    def __getattr__(self, attr: Any):
        return self[attr]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value
