from .base import BaseSearcher
from six.moves import urllib_parse


class GDrive(BaseSearcher):
    def is_valid_url(self, url: str) -> bool:
        parsed = urllib_parse.urlparse(url)
        return parsed.hostname in ["drive.google.com", "docs.google.com"]
        