from yt_dlp import YoutubeDL
from typing import List
import os
import asyncio
import librosa

from constants import MUSIC_STORAGE
from src.player.media_metadata import MediaMetadata
from src.player.timestamp_parser import parse_timestamp


class NoVideoInQueueError(Exception):
    """Error when there is no video in queue
    """
    pass


class SingleDownloader:
    """Downloads the audio from a single YouTube video.
    """
    def __init__(self, data:MediaMetadata, ydl_session:YoutubeDL):
        self._data = data
        self._ydl = ydl_session

    def download(self):
        if self._data is not None and not isExist(self._data):
            self._ydl.download([self._data.original_url])
            self._data.duration = int(librosa.get_duration(path=toPath(self._data)))


class Downloader:
    """Downloads the audio from a list of YouTube videos.
    """
    def __init__(self, data:List[MediaMetadata], ydl_sesh:YoutubeDL):
        self._data = data
        self._ydl = ydl_sesh
        self.playable = False

    def first_download(self):
        try:
            SingleDownloader(self._data[0], self._ydl).download()
            self.playable = True
        except IndexError:
            raise NoVideoInQueueError("There is no video currently in queue")

    async def _async_range_ft(self, from_point, to_point):
        for i in range(from_point, to_point):
            yield i
            await asyncio.sleep(0.0)

    def continue_download(self):
        if len(self._data) > 1:
            for sin_ind in range(1, len(self._data)):
                SingleDownloader(self._data[sin_ind], self._ydl).download()

def isExist(info_dict: MediaMetadata) -> bool:
    return get_path(info_dict)[0]

def get_path(info_dict: MediaMetadata):
    if hasattr(info_dict, 'id'):
        id_path = os.path.join(MUSIC_STORAGE, f'{info_dict.id}.{info_dict.ext}')
        name_path_3 = os.path.join(MUSIC_STORAGE, f'{info_dict.title} [{info_dict.id}].{info_dict.ext}')
    else:
        id_path = None
        name_path_3 = None
    
    name_path_1 = os.path.join(MUSIC_STORAGE, f'{info_dict.title}.{info_dict.ext}')
    name_path_2 = os.path.join(MUSIC_STORAGE, f'{info_dict.title} [{info_dict.title}].{info_dict.ext}')
    
    paths = [name_path_1, name_path_2]
    if id_path and name_path_3:
        paths.extend([id_path, name_path_3])

    for path in paths:
        if os.path.isfile(path):
            return True, path

    return False, None

def toPath(info_dict: MediaMetadata):
    return get_path(info_dict)[1]