from src.player.observers import DownloaderObservable
from yt_dlp import YoutubeDL
from src.player.link_identifier import LinkIdentifier as LI
from urllib.request import urlopen, Request
from os.path import basename
from typing import Dict
from src.player.media_metadata import MediaMetadata
from typing import Union
from discord import Attachment


class LoadMedia(DownloaderObservable):
    def __init__(self, url, url_type: str, **kwargs):
        super().__init__()
        self._url = url
        self._base_url_type = url_type
        self._kwargs = kwargs

    def load_info(self):
        print(f"Loading info for {self._url}")
        if self._base_url_type == LI.YOUTUBE:
            return self._load_youtube()
        elif self._base_url_type == LI.NORMAL_URL:
            return self._load_file()

    def _load_youtube(self):
        if "list" in self._url:
            url_type = "playlist"
        else:
            url_type = "video"
        inst = YoutubeDL(
            {
                'format':'bestaudio',
                'ignoreerrors':'only_download'
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
            filename = basename(response.url)
            file_name, file_ext = filename.split('.')
            to_return = [MediaMetadata.from_title_extension(file_name, file_ext, self._url)]
        else:
            extension = self._url.filename.split(".")[-1]
            to_return = [MediaMetadata.from_title_extension(self._url.filename.replace(f".{extension}", ""), extension, self._url.url)]
        self.notify_observers()
        return to_return


# class LoadYouTube(BaseMediaLoader):
#     def __init__(self, url, work_type = 'normal'): # either normal or chapter
#         self._url = url
#         if "list" in self._url:
#             self._url_type = "playlist"
#         else:
#             self._url_type = "video"
#         self.inst = YoutubeDL(
#             {
#                 'format':'bestaudio',
#                 'ignoreerrors':'only_download'
#             }
#         )

#         self._work_type = work_type

#     def _extract(self):
#         if self._url_type == 'video':
#             obtained_data : Dict = self.inst.extract_info(self._url, download = False)
#             self.notify_observers() # im done mtfk
#             if obtained_data is not None:
#                 return [MediaMetadata(obtained_data)]
#             else:
#                 return []
#         elif self._work_type == 'normal':
#             obtained_data : Dict = self.inst.extract_info(self._url, download = False)
#             self.notify_observers() # im done mtfk
#             try:
#                 return [MediaMetadata(i) for i in obtained_data['entries'] if i is not None]
#             except KeyError: 
#                 # Occurs when yt_dlp cannot determine that it is a playlist, and decides to load it as a video midway.
#                 # This happened once somewhere...
#                 return [MediaMetadata(obtained_data)]
#         else:
#             raise ValueError("Cannot load playlist for this work type.")


# class LoadFile(BaseMediaLoader):
#     def __init__(self, file: Union[str, Attachment], **kwargs): # avoid TypeError only.
#         # Draft:
#         #   - The "file" will be processed into a proper file for the player to play.
#         #   - Then we setup a new player for the bot. 
#         # Note: should be asynchronous. If not, the bot might run into problems
#         self._file = file

#     def _extract(self):
#         if isinstance(self._file, str):
#             return [MediaMetadata.from_title("temp", self._file)]
#         else:
#             extension = self._file.filename.split(".")[-1]
#             return [MediaMetadata.from_title_extension(self._file.filename.replace(f".{extension}", ""), extension, self._file.url)]