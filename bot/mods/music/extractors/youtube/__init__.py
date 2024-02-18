from __future__ import annotations
from typing import Any

import yt_dlp
from yt_dlp.utils import YoutubeDLError

from ..base import BaseExtractor
from ..exceptions import InfoExtractionError, InvalidUrlError

from .consts import BASE_URL, VIDEO_URL, VIDEO_ID


class YoutubeExtractor(BaseExtractor):

    def __init__(self):
        self.youtube_dl = yt_dlp.YoutubeDL({
            'format': 'bestaudio',
            'default_search': 'ytsearch',
            'nocheckcertificate': True,
            'noplaylist': True,
            'simulate': True,
            'quiet': False
        })

    def validate_url(self, url: str):
        if VIDEO_URL.match(url):
            return url
        if VIDEO_ID.match(url):
            return BASE_URL + url
        else:
            raise InvalidUrlError()

    def parse_info(self, info: dict[str, Any]):
        if 'entries' in info:
            info = info['entries'][0]

        return {'title': info['title'],
                'duration': info['duration'],
                'origin_id': info['id'],
                'origin_url': info['webpage_url'],
                'stream_url': info.get('fragment_base_url') or info['url']}

    def extract_info(self, url: str) -> Any:
        try:
            return self.youtube_dl.extract_info(url)
        except YoutubeDLError:
            raise InfoExtractionError()

    def search(self, text: str):
        return [self.parse_info(info) for info in self.extract_info(f'ytsearch3:{text}')['entries']]

    def extract(self, url: str):
        return self.parse_info(self.extract_info(self.validate_url(url)))
