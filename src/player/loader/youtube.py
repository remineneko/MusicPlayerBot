from .base import BaseLoader
from src.player.media_metadata import MediaMetadata
from typing import List, Dict
from yt_dlp import YoutubeDL
from constants import MAX_NUMBER_OF_FILES


class YouTubeLoader(BaseLoader):
    def load(self, url: str, **kwargs) -> List[MediaMetadata]:
        if "list" in url:
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

        work_type = kwargs['work_type']

        if url_type == 'video':
            obtained_data : Dict = inst.extract_info(url, download = False)
            if obtained_data is not None:
                return [MediaMetadata(obtained_data)]
            else:
                return []
        elif work_type == 'normal':
            obtained_data : Dict = inst.extract_info(url, download = False)
            try:
                return [MediaMetadata(i) for i in obtained_data['entries'] if i is not None]
            except KeyError: 
                # Occurs when yt_dlp cannot determine that it is a playlist, and decides to load it as a video midway.
                # This happened once somewhere...
                return [MediaMetadata(obtained_data)]
        else:
            raise ValueError("Cannot load playlist for this work type.")
