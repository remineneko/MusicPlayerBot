from constants import MUSIC_STORAGE
import os
import functools
from datetime import timedelta
from yt_dlp import YoutubeDL


YOUTUBEDL_PARAMS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': os.path.join(MUSIC_STORAGE, '%(id)s.%(ext)s'),
}

YT_DLP_SESH = YoutubeDL(YOUTUBEDL_PARAMS)

NO_LOOP = 0
LOOP = 1


async def run_blocker(client, func, *args, **kwargs):
    func_ = functools.partial(func, *args, **kwargs)
    return await client.loop.run_in_executor(None, func_)


def _time_split(time: int):
    return str(timedelta(seconds=time))