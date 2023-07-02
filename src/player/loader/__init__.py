from .drive import GDriveLoader
from .youtube import YouTubeLoader

SITE_MAPPING = {
    'BiliBili': YouTubeLoader,
    'Drive': GDriveLoader,
    'YouTube': YouTubeLoader
}