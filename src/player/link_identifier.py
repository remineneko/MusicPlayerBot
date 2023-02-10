import re
from urllib.parse import urlparse


class LinkIdentifier:
    YOUTUBE = "YouTube"
    NORMAL_URL = "File"
    BILIBILI = "Bibilili"
    NON_URL = 0

    _YOUTUBE_VALID_LINK_REGEX = r'^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$'
    _BILIBILI_VALID_LINK_REGEX = r'''(?x)
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
                    '''

    def __init__(self, url:str):
        self._url = url
        self.url_type = self._get_url_type()

    def _get_url_type(self):
        if self._is_valid_bilibili_link(self._url):
            return self.BILIBILI
        elif self._is_valid_youtube_link(self._url):
            return self.YOUTUBE
        elif self._is_valid_normal_link(self._url):
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
