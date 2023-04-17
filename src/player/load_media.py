from src.player.observers import DownloaderObservable
from yt_dlp import YoutubeDL
from src.player.link_identifier import LinkIdentifier as LI
from urllib.request import urlopen, Request
from os.path import basename
from typing import Dict
from src.player.media_metadata import MediaMetadata
from typing import Union
from discord import Attachment
from constants import MAX_NUMBER_OF_FILES
import re


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

        if self._base_url_type in [LI.YOUTUBE, LI.BILIBILI]:
            return self._load_supported()
        elif self._base_url_type == LI.NORMAL_URL:
            return self._load_file()
        elif self._base_url_type == LI.SPOTIFY:
            raise UnsupportedPlatformError("Spotify is not supported by the bot.")

    def _load_supported(self):
        if "list" in self._url:
            url_type = "playlist"
        else:
            url_type = "video"

        inst = YoutubeDL(
            {
                'format':'bestaudio/best',
                'ignoreerrors':'only_download',
                'playlist_items': f'1-{MAX_NUMBER_OF_FILES}'
            }
        )

        work_type = self._kwargs['work_type']

        if url_type == 'video':
            obtained_data : Dict = inst.extract_info(self._url, download = False)
            self.notify_observers() # im done mtfk
            if obtained_data is not None:
                return [MediaMetadata(obtained_data)]
            else:
                return []
        elif work_type == 'normal':
            obtained_data : Dict = inst.extract_info(self._url, download = False)
            self.notify_observers() # im done mtfk
            try:
                return [MediaMetadata(i) for i in obtained_data['entries'] if i is not None]
            except KeyError: 
                # Occurs when yt_dlp cannot determine that it is a playlist, and decides to load it as a video midway.
                # This happened once somewhere...
                return [MediaMetadata(obtained_data)]
        else:
            raise ValueError("Cannot load playlist for this work type.")

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
                return self._load_supported()
        else:
            extension = self._url.filename.split(".")[-1]
            to_return = [MediaMetadata.from_title_extension(self._url.filename.replace(f".{extension}", ""), extension, self._url.url)]
        self.notify_observers()
        return to_return