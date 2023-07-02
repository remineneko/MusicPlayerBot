from .bilibili import BiliBili
from .drive import GDrive
from .youtube import YouTube

SITE_MAPPING = {
    'bilibili': BiliBili,
    'drive': GDrive,
    'youtube': YouTube
}

SITE_CAMEL_MAPPING = {
    'bilibili': 'BiliBili',
    'drive': 'Drive',
    'youtube': 'YouTube'
}