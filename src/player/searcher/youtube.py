from .base import BaseSearcher
import re


class YouTube(BaseSearcher):
    YOUTUBE_REGEX = r'^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$'

    def is_valid_url(self, url: str) -> bool:
        return bool(re.search(self.YOUTUBE_REGEX, url))