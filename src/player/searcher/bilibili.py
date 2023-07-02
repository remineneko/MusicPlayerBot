from .base import BaseSearcher
import re


class BiliBili(BaseSearcher):
    BILIBILI_REGEX = r'''(?x)
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
    
    def is_valid_url(self, url: str) -> bool:
        return bool(re.search(self.BILIBILI_REGEX, url))