import re
from os.path import basename
from typing import Dict, Union
from urllib.request import Request, urlopen

from discord import Attachment
from typing import List
from yt_dlp import YoutubeDL

from constants import MAX_NUMBER_OF_FILES
from src.player.link_identifier import LinkIdentifier as LI
from src.player.media_metadata import MediaMetadata
from src.player.observers import DownloaderObservable
from src.player.searcher import SITE_CAMEL_MAPPING
from src.player.loader import SITE_MAPPING, YouTubeLoader

class UnsupportedPlatformError(Exception):
    pass


class LoadMedia(DownloaderObservable):

    YOUTUBE_WATCH_URL = 'https://youtube.com/watch?v={}'

    def __init__(self, url, url_type: str, **kwargs):
        super().__init__()
        self._url = url
        self._base_url_type = url_type
        self._kwargs = kwargs

    def load_info(self):
        print(f"Loading info for {self._url}")

        if self._base_url_type in list(SITE_CAMEL_MAPPING.values()):
            return self._load_supported()
        elif self._base_url_type == LI.NORMAL_URL:
            return self._load_file()
       
    def _load_supported(self):
        if self._base_url_type in SITE_MAPPING:
            data: List[MediaMetadata] = SITE_MAPPING[self._base_url_type]().load(self._url, **self._kwargs)
        self.notify_observers()
        return data

    def _load_file(self):
        if isinstance(self._url, str):
            request = Request(self._url, headers= {'User-Agent':"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"})
            response = urlopen(request)
            filename = response.headers.get_filename()
            if filename:
                file_name, file_ext = filename.split('.')
                to_return = [MediaMetadata.from_title_extension(file_name, file_ext, self._url)]
            else:
                # if somehow the link provided is not a legitimate download file link, just delegate that to yt-dlp to handle it instead
                to_return = YouTubeLoader().load(self._url, **self._kwargs)
        elif isinstance(self._url, Attachment):
            extension = self._url.filename.split(".")[-1]
            to_return = [MediaMetadata.from_title_extension(self._url.filename.replace(f".{extension}", ""), extension, self._url.url)]
        self.notify_observers()
        return to_return