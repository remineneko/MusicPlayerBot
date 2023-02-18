import re
from urllib.parse import urlparse


class LinkIdentifier:
    YOUTUBE = "YouTube"
    BILIBILI = "Bibilili"
    SPOTIFY = 'Spotify'

    NORMAL_URL = "File"
    NON_URL = 0

    ALL_SITES = {
        'youtube': r'^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$',
        'bilibili': r'''(?x)
                    https?://
                        (?:(?:www|bangumi)\.)?
                        bilibili\.(?:tv|com)/
                        (?:
                            (?:
                                video/[aA][vV]|
                                anime/(?P<anime_id>\d+)/play\#
                            )(?P<id>\d+)|
                            (s/)?video/[bB][vV](?P<id_bv>[^/?#&]+)
                        )
                        (?:/?\?p=(?P<page>\d+))?
                    ''', 
        'spotify': r'^(spotify:|https://[a-z]+\.spotify\.com/)'
    }

    def __init__(self, url:str):
        self._url = url
        self.url_type = self._get_url_type()

    def _get_url_type(self):
        valid_link = lambda site, url: bool(re.search(self.ALL_SITES[site], url))

        for site in self.ALL_SITES:
            if valid_link(site, self._url):
                return getattr(self, site.upper())

        if self._is_valid_normal_link(self._url):
            return self.NORMAL_URL
        else:
            return self.NON_URL

    def _is_valid_youtube_link(self, link:str):
        return bool(re.search(self._YOUTUBE_VALID_LINK_REGEX, link))
    
    def _is_valid_normal_link(self, url:str):
        parsed_result = urlparse(url)
        return parsed_result.scheme and parsed_result.netloc

    def _is_valid_bilibili_link(self, url:str):
        return bool(re.search(self._BILIBILI_VALID_LINK_REGEX, url))