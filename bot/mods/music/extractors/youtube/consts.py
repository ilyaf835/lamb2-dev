import re


BASE_URL = 'https://www.youtube.com/watch?v='
VIDEO_ID = re.compile('(?P<video_id>{video_id})'.format(video_id='[0-9A-Za-z_-]{10}[048AEIMQUYcgkosw]'))
VIDEO_URL = re.compile(
    r"""
    ^
    (?:https?://)?
    (?:
        (?:
            (?:www\.)?
                (?:youtube\.com/)
                    (?:
                        (?:embed/)
                        |
                        (?:watch\?v=)
                    )
        )
        |
        (?:
            (?:
                (?:m\.)
                |
                (?:music\.)
            )
                    (?:youtube\.com/watch\?v=)
        )
        |
        (?:youtu\.be/)
    )
    (?P<video_id>{video_id})
    .*$
    """.format(video_id='[0-9A-Za-z_-]{10}[048AEIMQUYcgkosw]'), re.VERBOSE)
