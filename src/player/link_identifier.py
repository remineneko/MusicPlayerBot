from urllib.parse import urlparse
from src.player.searcher import SITE_MAPPING, SITE_CAMEL_MAPPING

class LinkIdentifier:
    NORMAL_URL = "File"
    NON_URL = 0

    def __init__(self, url:str):
        self._url = url
        self.url_type = self._get_url_type()

    def _get_url_type(self):
        for site in SITE_MAPPING:
            if SITE_MAPPING[site]().is_valid_url(self._url):
                return SITE_CAMEL_MAPPING[site]

        if self._is_valid_normal_link(self._url):
            return self.NORMAL_URL
        else:
            return self.NON_URL
    
    def _is_valid_normal_link(self, url:str):
        parsed_result = urlparse(url)
        return parsed_result.scheme and parsed_result.netloc